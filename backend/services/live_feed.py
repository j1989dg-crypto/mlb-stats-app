"""
Live Feed Service — polls the MLB Stats API live game endpoint.

Provides:
  - get_live_games()        : all games today with status/score
  - get_live_game_state()   : current at-bat situation (batter, pitcher, count, runners, score)
  - get_pitch_sequence()    : full pitch-by-pitch history for current at-bat + last few
"""
import asyncio
import logging
from datetime import datetime, date
from db.cache import get_cache, set_cache
from services.http_client import get_client

logger = logging.getLogger(__name__)

MLB_BASE    = "https://statsapi.mlb.com"
LIVE_FEED   = MLB_BASE + "/api/v1.1/game/{game_pk}/feed/live"
SCHEDULE    = MLB_BASE + "/api/v1/schedule?sportId=1&date={date}&hydrate=team,venue,linescore"

# Pitch type labels
PITCH_NAMES = {
    "FF": "4-Seam Fastball", "SI": "Sinker",      "FC": "Cutter",
    "SL": "Slider",          "ST": "Sweeper",      "CU": "Curveball",
    "CH": "Changeup",        "FS": "Splitter",     "KC": "Knuckle-Curve",
    "SV": "Slurve",          "KN": "Knuckleball",  "EP": "Eephus",
    "FO": "Forkball",        "SC": "Screwball",    "CS": "Slow Curve",
}

RESULT_LABELS = {
    "ball":                "Ball",
    "called_strike":       "Called Strike",
    "swinging_strike":     "Swinging Strike",
    "swinging_strike_blocked": "Swinging Strike",
    "foul":                "Foul",
    "foul_tip":            "Foul Tip",
    "hit_into_play":       "In Play",
    "hit_by_pitch":        "HBP",
    "blocked_ball":        "Blocked Ball",
}


async def get_live_games(for_date: str | None = None) -> list[dict]:
    """
    Return all games for `for_date` (YYYY-MM-DD) with live status and score.
    Defaults to today.
    """
    game_date = for_date or date.today().isoformat()
    cache_key = f"live:games:{game_date}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    try:
        client = get_client()
        url = SCHEDULE.format(date=game_date)
        r = await client.get(url, timeout=10)
        if r.status_code != 200:
            return []

        data   = r.json()
        dates  = data.get("dates", [])
        games  = []

        for d in dates:
            for g in d.get("games", []):
                status   = g.get("status", {})
                linescore = g.get("linescore", {})
                teams    = g.get("teams", {})

                away_team = teams.get("away", {}).get("team", {})
                home_team = teams.get("home", {}).get("team", {})
                away_score = linescore.get("teams", {}).get("away", {}).get("runs", 0)
                home_score = linescore.get("teams", {}).get("home", {}).get("runs", 0)

                state = status.get("abstractGameState", "")
                detail = status.get("detailedState", "")

                games.append({
                    "game_pk":    g.get("gamePk"),
                    "away_team":  away_team.get("abbreviation", "?"),
                    "away_name":  away_team.get("name", "?"),
                    "home_team":  home_team.get("abbreviation", "?"),
                    "home_name":  home_team.get("name", "?"),
                    "away_score": away_score,
                    "home_score": home_score,
                    "status":     state,
                    "detail":     detail,
                    "is_live":    state == "Live",
                    "is_final":   state == "Final",
                    "venue":      g.get("venue", {}).get("name", ""),
                    "game_date":  game_date,
                })

        # Cache 30s for live games, 5m for finished
        ttl = 30 if any(g["is_live"] for g in games) else 300
        await set_cache(cache_key, games, ttl)
        return games

    except Exception as e:
        logger.error("[LiveFeed] get_live_games error: %s", e)
        return []


async def get_live_game_state(game_pk: int) -> dict:
    """
    Fetch full live feed for a game and extract the current situation:
    batter, pitcher, count, runners, score, inning, outs.
    """
    try:
        client = get_client()
        url = LIVE_FEED.format(game_pk=game_pk)
        r = await client.get(url, timeout=15)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}

        feed = r.json()
        gd   = feed.get("gameData", {})
        ld   = feed.get("liveData", {})

        # Teams
        teams = gd.get("teams", {})
        away  = teams.get("away", {})
        home  = teams.get("home", {})

        # Players dict (id → name/position)
        players_raw = gd.get("players", {})

        # Current play / at-bat
        plays       = ld.get("plays", {})
        current     = plays.get("currentPlay", {})
        matchup     = current.get("matchup", {})
        count_data  = current.get("count", {})
        about       = current.get("about", {})

        batter_id   = matchup.get("batter",  {}).get("id")
        batter_name = matchup.get("batter",  {}).get("fullName", "?")
        batter_hand = matchup.get("batSide", {}).get("code", "R")

        pitcher_id   = matchup.get("pitcher",  {}).get("id")
        pitcher_name = matchup.get("pitcher",  {}).get("fullName", "?")
        pitcher_hand = matchup.get("pitchHand", {}).get("code", "R")

        balls   = count_data.get("balls",   0)
        strikes = count_data.get("strikes", 0)
        outs    = count_data.get("outs",    0)
        inning  = about.get("inning",  1)
        is_top  = about.get("isTopInning", True)

        # Score
        linescore = ld.get("linescore", {})
        teams_ls  = linescore.get("teams", {})
        away_score = teams_ls.get("away", {}).get("runs", 0)
        home_score = teams_ls.get("home", {}).get("runs", 0)

        # Runners on base
        offense   = linescore.get("offense", {})
        runner_1b = bool(offense.get("first"))
        runner_2b = bool(offense.get("second"))
        runner_3b = bool(offense.get("third"))

        runners_on = sum([runner_1b, runner_2b, runner_3b])

        # Batting team vs pitching team
        if is_top:
            bat_team  = away.get("abbreviation", "?")
            pit_team  = home.get("abbreviation", "?")
            score_diff = away_score - home_score  # positive = batting team winning
        else:
            bat_team  = home.get("abbreviation", "?")
            pit_team  = away.get("abbreviation", "?")
            score_diff = home_score - away_score

        game_status = gd.get("status", {}).get("abstractGameState", "Unknown")

        return {
            "game_pk":      game_pk,
            "status":       game_status,
            "inning":       inning,
            "is_top":       is_top,
            "half":         "Top" if is_top else "Bot",
            "balls":        balls,
            "strikes":      strikes,
            "outs":         outs,
            "batter_id":    batter_id,
            "batter_name":  batter_name,
            "batter_hand":  batter_hand,
            "pitcher_id":   pitcher_id,
            "pitcher_name": pitcher_name,
            "pitcher_hand": pitcher_hand,
            "away_team":    away.get("abbreviation", "?"),
            "home_team":    home.get("abbreviation", "?"),
            "away_score":   away_score,
            "home_score":   home_score,
            "score_diff":   score_diff,
            "runner_1b":    runner_1b,
            "runner_2b":    runner_2b,
            "runner_3b":    runner_3b,
            "runners_on":   runners_on,
            "bat_team":     bat_team,
            "pit_team":     pit_team,
            "at_bat_number": about.get("atBatIndex", about.get("atBatNumber", 0)),
        }

    except Exception as e:
        logger.error("[LiveFeed] get_live_game_state(%s) error: %s", game_pk, e)
        return {"error": str(e)}


async def get_pitch_sequence(game_pk: int) -> dict:
    """
    Return the pitch-by-pitch sequence for the current at-bat and last at-bat.
    Each pitch includes type, velocity, result, count at time of pitch.
    """
    try:
        client = get_client()
        url = LIVE_FEED.format(game_pk=game_pk)
        r = await client.get(url, timeout=15)
        if r.status_code != 200:
            return {"pitches": [], "last_pitch": None}

        feed  = r.json()
        ld    = feed.get("liveData", {})
        plays = ld.get("plays", {})

        current_play  = plays.get("currentPlay", {})
        all_plays     = plays.get("allPlays", [])

        def extract_pitches(play: dict) -> list[dict]:
            pitches = []
            events  = play.get("playEvents", [])
            for ev in events:
                if ev.get("type") != "pitch":
                    continue
                pitch_data  = ev.get("pitchData", {})
                details     = ev.get("details",   {})
                count_at    = ev.get("count",      {})
                pitch_type  = details.get("type", {}).get("code", "")
                result_code = details.get("code", "")

                pitches.append({
                    "pitch_type":   pitch_type,
                    "pitch_name":   PITCH_NAMES.get(pitch_type, pitch_type),
                    "result":       RESULT_LABELS.get(result_code, result_code),
                    "result_code":  result_code,
                    "velocity":     pitch_data.get("startSpeed"),
                    "spin_rate":    pitch_data.get("extension"),
                    "balls_before": count_at.get("balls",   0),
                    "strikes_before": count_at.get("strikes", 0),
                    "outs_before":  count_at.get("outs",    0),
                    "pitch_num":    ev.get("pitchNumber", len(pitches) + 1),
                })
            return pitches

        current_pitches = extract_pitches(current_play)
        last_pitch      = current_pitches[-1] if current_pitches else None

        # Previous completed at-bat pitches (for context)
        prev_pitches = []
        if len(all_plays) >= 2:
            prev_pitches = extract_pitches(all_plays[-2])

        return {
            "current_ab_pitches": current_pitches,
            "prev_ab_pitches":    prev_pitches,
            "last_pitch":         last_pitch,
            "pitches_in_ab":      len(current_pitches),
        }

    except Exception as e:
        logger.error("[LiveFeed] get_pitch_sequence(%s) error: %s", game_pk, e)
        return {"pitches": [], "last_pitch": None, "error": str(e)}
