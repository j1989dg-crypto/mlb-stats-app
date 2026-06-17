"""
Live Home Runs Router — scans today's games for home run events in real time.

Endpoints:
  GET /api/live-hrs/today          — all HRs hit today across all games
  GET /api/live-hrs/game/{game_pk} — HRs for a specific game
"""
import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Query
from services.live_feed import get_live_games
from services.http_client import get_client
from db.cache import get_cache, set_cache

logger = logging.getLogger(__name__)
router = APIRouter()

MLB_BASE  = "https://statsapi.mlb.com"
LIVE_FEED = MLB_BASE + "/api/v1.1/game/{game_pk}/feed/live"


async def extract_hrs_from_game(game_pk: int, game_meta: dict) -> list[dict]:
    """
    Fetch the live feed for a game and extract all home run play events.
    Returns a list of HR dicts with player info, timing, hit data, etc.
    """
    try:
        client = get_client()
        url = LIVE_FEED.format(game_pk=game_pk)
        r = await client.get(url, timeout=15)
        if r.status_code != 200:
            return []

        feed = r.json()
        gd   = feed.get("gameData", {})
        ld   = feed.get("liveData", {})

        teams    = gd.get("teams", {})
        away_abbr = teams.get("away", {}).get("abbreviation", "?")
        home_abbr = teams.get("home", {}).get("abbreviation", "?")
        away_name = teams.get("away", {}).get("name", "?")
        home_name = teams.get("home", {}).get("name", "?")
        away_id   = teams.get("away", {}).get("id")
        home_id   = teams.get("home", {}).get("id")

        players_raw = gd.get("players", {})  # keyed as "ID123"
        venue_name  = gd.get("venue", {}).get("name", "")

        all_plays = ld.get("plays", {}).get("allPlays", [])
        hrs = []

        for play in all_plays:
            result = play.get("result", {})
            if result.get("event") != "Home Run":
                continue

            about     = play.get("about", {})
            matchup   = play.get("matchup", {})

            batter_id   = matchup.get("batter", {}).get("id")
            batter_name = matchup.get("batter", {}).get("fullName", "Unknown")
            pitcher_id  = matchup.get("pitcher", {}).get("id")
            pitcher_name = matchup.get("pitcher", {}).get("fullName", "Unknown")

            inning    = about.get("inning", 0)
            is_top    = about.get("isTopInning", True)
            half      = "Top" if is_top else "Bot"

            # Batting team — top of inning = away team batting
            if is_top:
                bat_team_abbr = away_abbr
                bat_team_name = away_name
                bat_team_id   = away_id
                pit_team_abbr = home_abbr
            else:
                bat_team_abbr = home_abbr
                bat_team_name = home_name
                bat_team_id   = home_id
                pit_team_abbr = away_abbr

            description = result.get("description", "")
            rbi         = result.get("rbi", 0)

            # HR number on the season — usually embedded in description like "(12)"
            hr_num = None
            import re
            m = re.search(r'\((\d+)\)', description)
            if m:
                hr_num = int(m.group(1))

            # Hit data — exit velo, launch angle, distance
            hit_data = {}
            play_events = play.get("playEvents", [])
            for ev in play_events:
                hd = ev.get("hitData", {})
                if hd:
                    hit_data = {
                        "exit_velo":    hd.get("launchSpeed"),
                        "launch_angle": hd.get("launchAngle"),
                        "distance":     hd.get("totalDistance"),
                        "hardness":     hd.get("hardness", ""),
                        "location":     hd.get("location", ""),
                        "trajectory":   hd.get("trajectory", ""),
                    }
                    break  # only need the hit event

            # Pitch info — what pitch was thrown for the HR
            pitch_info = {}
            for ev in reversed(play_events):
                if ev.get("type") == "pitch":
                    details = ev.get("details", {})
                    pt_obj     = details.get("type") or {}
                    pitch_type = pt_obj.get("code", "")
                    pitch_desc = pt_obj.get("description", "")
                    velocity   = ev.get("pitchData", {}).get("startSpeed")
                    pitch_info = {
                        "pitch_type": pitch_type,
                        "pitch_desc": pitch_desc,
                        "velocity":   velocity,
                    }
                    break

            # Score after the HR
            linescore = ld.get("linescore", {})
            away_runs = linescore.get("teams", {}).get("away", {}).get("runs", 0)
            home_runs = linescore.get("teams", {}).get("home", {}).get("runs", 0)

            hrs.append({
                "game_pk":       game_pk,
                "away_team":     away_abbr,
                "home_team":     home_abbr,
                "away_name":     away_name,
                "home_name":     home_name,
                "venue":         venue_name,
                "batter_id":     batter_id,
                "batter_name":   batter_name,
                "pitcher_id":    pitcher_id,
                "pitcher_name":  pitcher_name,
                "bat_team":      bat_team_abbr,
                "bat_team_name": bat_team_name,
                "bat_team_id":   bat_team_id,
                "pit_team":      pit_team_abbr,
                "inning":        inning,
                "half":          half,
                "inning_label":  f"{half} {inning}",
                "rbi":           rbi,
                "hr_number":     hr_num,
                "description":   description,
                "hit_data":      hit_data,
                "pitch_info":    pitch_info,
                "at_bat_index":  about.get("atBatIndex", 0),
                "game_status":   game_meta.get("detail", game_meta.get("status", "")),
                "is_live":       game_meta.get("is_live", False),
                "is_final":      game_meta.get("is_final", False),
                "away_score":    away_runs,
                "home_score":    home_runs,
            })

        return hrs

    except Exception as e:
        logger.error("[LiveHRs] extract_hrs_from_game(%s) error: %s", game_pk, e)
        return []


@router.get("/today")
async def get_todays_hrs(game_date: str = Query(default=None)):
    """
    Return all home runs hit today (or on game_date) across all games.
    Aggregates in parallel across every game on the schedule.
    Cached 45s while games are live, 10min when all finished.
    """
    target_date = game_date or date.today().isoformat()
    cache_key   = f"live_hrs:today:{target_date}"

    cached = await get_cache(cache_key)
    if cached:
        return cached

    games = await get_live_games(for_date=target_date)
    if not games:
        result = {"date": target_date, "home_runs": [], "total": 0, "games": []}
        await set_cache(cache_key, result, 60)
        return result

    # Fetch HRs for all games in parallel
    tasks = [extract_hrs_from_game(g["game_pk"], g) for g in games]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_hrs = []
    for hrs in results:
        if isinstance(hrs, list):
            all_hrs.extend(hrs)

    # Sort by inning, then at_bat_index
    all_hrs.sort(key=lambda h: (h["inning"], h["at_bat_index"]))

    any_live = any(g["is_live"] for g in games)
    ttl = 45 if any_live else 600

    response = {
        "date":       target_date,
        "home_runs":  all_hrs,
        "total":      len(all_hrs),
        "games":      games,
        "any_live":   any_live,
    }
    await set_cache(cache_key, response, ttl)
    return response


@router.get("/game/{game_pk}")
async def get_game_hrs(game_pk: int):
    """Return HRs for a single specific game."""
    cache_key = f"live_hrs:game:{game_pk}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    games = await get_live_games()
    meta  = next((g for g in games if g["game_pk"] == game_pk), {})
    hrs   = await extract_hrs_from_game(game_pk, meta)

    result = {"game_pk": game_pk, "home_runs": hrs, "total": len(hrs)}
    ttl = 45 if meta.get("is_live") else 600
    await set_cache(cache_key, result, ttl)
    return result
