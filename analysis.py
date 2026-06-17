"""
Full game analysis orchestrator — Deep BvP + FanGraphs + 3-call AI pipeline
"""
import asyncio
from fastapi import APIRouter, HTTPException
from datetime import datetime
from services import mlb_api
from services.weather import get_weather_for_venue, get_park_factors
from services.streak_calculator import calculate_streak, calculate_pitcher_streak
from services.ai_analysis import analyze_game, analyze_betting, analyze_pitch_matchups, analyze_player_spotlight
from services.statcast import get_pitcher_arsenal, get_batter_statcast, get_bvp_statcast, get_pitcher_arsenal_by_stance
from services.odds_api import match_game_odds, get_game_props
from services.splits import get_batter_splits, get_pitcher_splits
from services.matchup_ranker import rank_lineup_vs_pitcher, _safe_float
from services.fangraphs import get_batter_fangraphs, get_pitcher_fangraphs
from db.cache import get_cache, set_cache

router = APIRouter()


async def _build_pitcher_profile(pitcher: dict) -> dict:
    if not pitcher or not pitcher.get("id"):
        return {"name": "TBD", "era": "-.--", "whip": "-.--", "k9": "-.--", "streak_label": "Unknown", "hand": "R"}
    pid = pitcher["id"]
    try:
        stats_data, log, splits, fg = await asyncio.gather(
            mlb_api.get_player_stats(pid, "pitching"),
            mlb_api.get_player_game_log(pid, "pitching"),
            get_pitcher_splits(pid),
            get_pitcher_fangraphs(pid),
        )
        people = stats_data.get("people", [{}])
        season_stats = {}
        for s in people[0].get("stats", []):
            if s.get("type", {}).get("displayName") == "season":
                spl = s.get("splits", [])
                if spl:
                    season_stats = spl[0].get("stat", {})
        hand = people[0].get("pitchHand", {}).get("code", "R")
        streak = calculate_pitcher_streak(log, 5)
        return {
            "id": pid,
            "name": pitcher.get("fullName", "Unknown"),
            "era":   season_stats.get("era", "-.--"),
            "whip":  season_stats.get("whip", "-.--"),
            "k9":    season_stats.get("strikeoutsPer9Inn", "-.--"),
            "wins":  season_stats.get("wins", 0),
            "losses": season_stats.get("losses", 0),
            "innings": season_stats.get("inningsPitched", "0.0"),
            "hand": hand,
            "streak_status": streak.get("status"),
            "streak_label":  streak.get("label"),
            "streak_era":    streak.get("era"),
            "splits": splits,
            "streak": streak,
            # FanGraphs advanced
            "fip":       fg.get("fip"),
            "xfip":      fg.get("xfip"),
            "siera":     fg.get("siera"),
            "war":       fg.get("war"),
            "k_pct":     fg.get("k_pct"),
            "bb_pct":    fg.get("bb_pct"),
            "k_bb_pct":  fg.get("k_bb_pct"),
            "gb_pct":    fg.get("gb_pct"),
            "whiff_pct": fg.get("whiff_pct"),
            "chase_pct": fg.get("chase_pct"),
        }
    except Exception as e:
        return {"id": pid, "name": pitcher.get("fullName", "Unknown"), "era": "-.--", "whip": "-.--", "k9": "-.--", "streak_label": "Unknown", "hand": "R"}


async def _build_batter_profile(batter: dict) -> dict:
    pid  = batter.get("person", {}).get("id")
    name = batter.get("person", {}).get("fullName", "Unknown")
    batting_order = batter.get("battingOrder")
    bat_side = batter.get("person", {}).get("batSide", {}).get("code", "R")

    if not pid:
        return {"name": name, "id": None}
    try:
        log, stats_data, splits, statcast, fg = await asyncio.gather(
            mlb_api.get_player_game_log(pid, "hitting"),
            mlb_api.get_player_stats(pid, "hitting"),
            get_batter_splits(pid),
            get_batter_statcast(pid),
            get_batter_fangraphs(pid),
        )
        streak = calculate_streak(log, 15)
        people = stats_data.get("people", [{}])
        season_stats = {}
        for s in people[0].get("stats", []):
            if s.get("type", {}).get("displayName") == "season":
                spl = s.get("splits", [])
                if spl:
                    season_stats = spl[0].get("stat", {})
        return {
            "id": pid, "name": name, "batting_order": batting_order,
            "bat_side": bat_side,
            "season_avg": season_stats.get("avg", ".---"),
            "season_obp": season_stats.get("obp", ".---"),
            "season_slg": season_stats.get("slg", ".---"),
            "season_ops": season_stats.get("ops", ".---"),
            "season_hr":  season_stats.get("homeRuns", 0),
            "streak": streak,
            "streak_status": streak.get("status"),
            "streak_label":  streak.get("label"),
            "streak_avg":    streak.get("avg"),
            "streak_ops":    streak.get("ops"),
            "game_trend":    streak.get("game_trend", []),
            "hit_streak":    streak.get("hit_streak", 0),
            "splits":   splits,
            "statcast": statcast,
            "fangraphs": fg,
        }
    except:
        return {"id": pid, "name": name, "streak_status": "unknown", "bat_side": bat_side}


@router.get("/game/{game_pk}")
async def get_game_analysis(game_pk: int, refresh: bool = False):
    """
    Full AI-powered game analysis including:
    - Starting pitcher matchup + Statcast arsenal + FanGraphs FIP/xFIP/SIERA
    - Full lineup BvP ranked with K%/BB%/pitch-type matchup data + FanGraphs wRC+
    - Per-pitch BvP Statcast (whiff%, exit velo, HR count, chase% per pitch type)
    - Pitcher arsenal by batter stance (vs LHB vs RHB)
    - Platoon splits with BB%, K%, ISO, BABIP
    - Weather & ballpark factors
    - Real betting odds (moneyline, run line, total, player props)
    - Gemini AI Call 1: Pitch matchup analyzer (runs first, feeds later calls)
    - Gemini AI Call 2: Game narrative with full Statcast context
    - Gemini AI Call 3: Value betting picks with K projections
    """
    cache_key = f"full_analysis:{game_pk}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    # 1. Get game schedule info
    today = datetime.now().strftime("%Y-%m-%d")
    games = await mlb_api.get_schedule(today)
    game_info = next((g for g in games if g.get("gamePk") == game_pk), None)

    if not game_info:
        try:
            live = await mlb_api.get_game_detail(game_pk)
            gd = live.get("gameData", {})
            game_info = {
                "gamePk": game_pk,
                "venue": gd.get("venue", {}),
                "teams": {
                    "away": {"team": gd.get("teams", {}).get("away", {})},
                    "home": {"team": gd.get("teams", {}).get("home", {})},
                }
            }
        except:
            raise HTTPException(status_code=404, detail="Game not found")

    venue_id   = game_info.get("venue", {}).get("id")
    away_team  = game_info.get("teams", {}).get("away", {}).get("team", {})
    home_team  = game_info.get("teams", {}).get("home", {}).get("team", {})
    away_pp    = game_info.get("teams", {}).get("away", {}).get("probablePitcher", {})
    home_pp    = game_info.get("teams", {}).get("home", {}).get("probablePitcher", {})

    # 2. Base data concurrently
    weather_coro = get_weather_for_venue(venue_id) if venue_id else asyncio.sleep(0)
    weather, away_pitcher_profile, home_pitcher_profile = await asyncio.gather(
        weather_coro,
        _build_pitcher_profile(away_pp),
        _build_pitcher_profile(home_pp),
    )
    if not venue_id:
        weather = {}
    park_factors = get_park_factors(venue_id) if venue_id else {}

    # 3. Statcast arsenals + arsenal by stance + odds
    away_pid = away_pitcher_profile.get("id")
    home_pid = home_pitcher_profile.get("id")

    arsenal_away, arsenal_home, stance_away, stance_home, odds = await asyncio.gather(
        get_pitcher_arsenal(away_pid) if away_pid else asyncio.sleep(0),
        get_pitcher_arsenal(home_pid) if home_pid else asyncio.sleep(0),
        get_pitcher_arsenal_by_stance(away_pid) if away_pid else asyncio.sleep(0),
        get_pitcher_arsenal_by_stance(home_pid) if home_pid else asyncio.sleep(0),
        match_game_odds(home_team.get("name", ""), away_team.get("name", "")),
    )
    if not away_pid: arsenal_away = {}; stance_away = {}
    if not home_pid: arsenal_home = {}; stance_home = {}
    if not isinstance(arsenal_away, dict): arsenal_away = {}
    if not isinstance(arsenal_home, dict): arsenal_home = {}
    if not isinstance(stance_away, dict): stance_away = {}
    if not isinstance(stance_home, dict): stance_home = {}

    # 4. Lineup + BvP
    bvp_matchups = []
    home_lineup_streaks = []
    away_lineup_streaks = []
    bvp_ranked_away = []
    bvp_ranked_home = []

    try:
        lineup = await mlb_api.get_lineup(game_pk)
        away_batters = lineup.get("away", {}).get("batters", [])[:9]
        home_batters = lineup.get("home", {}).get("batters", [])[:9]

        away_profiles, home_profiles = await asyncio.gather(
            asyncio.gather(*[_build_batter_profile(b) for b in away_batters]),
            asyncio.gather(*[_build_batter_profile(b) for b in home_batters]),
        )
        away_lineup_streaks = list(away_profiles)
        home_lineup_streaks = list(home_profiles)

        # Career BvP + Statcast BvP (pitch-level)
        async def get_bvp_full(batter: dict, pitcher_id: int, pitcher_name: str):
            bid   = batter.get("person", {}).get("id")
            bname = batter.get("person", {}).get("fullName", "?")
            if not bid or not pitcher_id:
                return None, None
            career_data, statcast_bvp = await asyncio.gather(
                mlb_api.get_batter_vs_pitcher(bid, pitcher_id),
                get_bvp_statcast(bid, pitcher_id),
            )
            stats = {}
            for s in career_data.get("stats", []):
                spl = s.get("splits", [])
                if spl:
                    stats = spl[0].get("stat", {})
                    break
            career = {
                "batter_id": bid, "batter_name": bname,
                "pitcher_id": pitcher_id, "pitcher_name": pitcher_name,
                "pa":  stats.get("plateAppearances", 0),
                "avg": stats.get("avg", ".---"),
                "ops": stats.get("ops", ".---"),
                "hr":  stats.get("homeRuns", 0),
                "so":  stats.get("strikeOuts", 0),
                "bb":  stats.get("baseOnBalls", 0),
            }
            return career, statcast_bvp

        bvp_tasks = []
        if home_pid:
            for b in away_batters:
                bvp_tasks.append(get_bvp_full(b, home_pid, home_pitcher_profile["name"]))
        if away_pid:
            for b in home_batters:
                bvp_tasks.append(get_bvp_full(b, away_pid, away_pitcher_profile["name"]))

        bvp_results = await asyncio.gather(*bvp_tasks)

        career_bvp_map  = {}  # (batter_id, pitcher_id) -> career dict
        statcast_bvp_map = {}  # (batter_id, pitcher_id) -> statcast bvp dict
        for career, sc_bvp in bvp_results:
            if career:
                bvp_matchups.append(career)
                career_bvp_map[(career["batter_id"], career["pitcher_id"])] = career
            if sc_bvp and sc_bvp.get("total_pitches", 0) > 0:
                statcast_bvp_map[(sc_bvp["batter_id"], sc_bvp["pitcher_id"])] = sc_bvp

        def _enrich_for_ranking(profiles, pitcher_id, pitcher_name):
            enriched = []
            for p in profiles:
                if not p.get("id"):
                    continue
                bid = p["id"]
                career = career_bvp_map.get((bid, pitcher_id), {})
                sc_bvp = statcast_bvp_map.get((bid, pitcher_id), {})
                enriched.append({
                    "id":   bid,
                    "name": p.get("name", "Unknown"),
                    "batting_order": p.get("batting_order"),
                    "bat_side":      p.get("bat_side", "R"),
                    "season_avg":    p.get("season_avg", ".---"),
                    "season_obp":    p.get("season_obp", ".---"),
                    "season_slg":    p.get("season_slg", ".---"),
                    "season_ops":    p.get("season_ops", ".---"),
                    "season_hr":     p.get("season_hr", 0),
                    "career_bvp": {
                        "pa":  career.get("pa", 0),
                        "avg": _safe_float(career.get("avg")),
                        "ops": _safe_float(career.get("ops")),
                        "hr":  career.get("hr", 0),
                    },
                    "streak":    p.get("streak", {}),
                    "splits":    p.get("splits", {}),
                    "statcast":  p.get("statcast", {}),
                    "fangraphs": p.get("fangraphs", {}),
                    "bvp_statcast": sc_bvp,
                })
            return enriched

        away_enriched = _enrich_for_ranking(away_profiles, home_pid, home_pitcher_profile["name"])
        home_enriched = _enrich_for_ranking(home_profiles, away_pid, away_pitcher_profile["name"])

        away_era = _safe_float(away_pitcher_profile.get("streak", {}).get("era", away_pitcher_profile.get("era", 4.0)), 4.0)
        home_era = _safe_float(home_pitcher_profile.get("streak", {}).get("era", home_pitcher_profile.get("era", 4.0)), 4.0)

        home_arsenal_list = arsenal_home.get("arsenal", [])
        away_arsenal_list = arsenal_away.get("arsenal", [])

        bvp_ranked_away = rank_lineup_vs_pitcher(away_enriched, home_pitcher_profile.get("hand","R"), home_era, home_arsenal_list)
        bvp_ranked_home = rank_lineup_vs_pitcher(home_enriched, away_pitcher_profile.get("hand","R"), away_era, away_arsenal_list)

    except Exception as e:
        print(f"Lineup/BvP error: {e}")

    # 5. Player props
    props = []
    if odds and odds.get("event_id"):
        try:
            props = await get_game_props(odds["event_id"])
        except:
            pass

    # 6. Build shared AI payload
    game_date = game_info.get("gameDate", datetime.now().strftime("%Y-%m-%d"))[:10]
    shared_payload = {
        "game_date":            game_date,
        "home_team":            home_team.get("name", "Home"),
        "away_team":            away_team.get("name", "Away"),
        "venue":                game_info.get("venue", {}).get("name", ""),
        "home_pitcher":         home_pitcher_profile,
        "away_pitcher":         away_pitcher_profile,
        "weather":              weather,
        "park_factors":         park_factors,
        "bvp_matchups":         bvp_matchups,
        "home_lineup_streaks":  list(home_lineup_streaks),
        "away_lineup_streaks":  list(away_lineup_streaks),
        "away_arsenal":         arsenal_away,
        "home_arsenal":         arsenal_home,
        "stance_arsenal_away":  stance_away,
        "stance_arsenal_home":  stance_home,
        "bvp_ranked_away":      bvp_ranked_away,
        "bvp_ranked_home":      bvp_ranked_home,
        "odds":                 odds or {},
        "props":                props,
    }

    # 7. AI pipeline: pitch matchup runs first, feeds narrative + betting
    pitch_matchup_ai = await analyze_pitch_matchups(game_pk, shared_payload)
    shared_payload["pitch_matchup_analysis"] = pitch_matchup_ai

    # 8. Narrative + betting run concurrently (staggered internally)
    ai_analysis, ai_betting = await asyncio.gather(
        analyze_game(game_pk, shared_payload),
        analyze_betting(game_pk, shared_payload),
    )

    result = {
        "game_pk":              game_pk,
        "away_team":            away_team,
        "home_team":            home_team,
        "venue":                game_info.get("venue", {}),
        "away_pitcher":         away_pitcher_profile,
        "home_pitcher":         home_pitcher_profile,
        "away_arsenal":         arsenal_away,
        "home_arsenal":         arsenal_home,
        "stance_arsenal_away":  stance_away,
        "stance_arsenal_home":  stance_home,
        "weather":              weather,
        "park_factors":         park_factors,
        "odds":                 odds,
        "bvp_matchups":         bvp_matchups,
        "bvp_ranked_away":      bvp_ranked_away,
        "bvp_ranked_home":      bvp_ranked_home,
        "away_lineup_streaks":  list(away_lineup_streaks),
        "home_lineup_streaks":  list(home_lineup_streaks),
        "ai_pitch_matchups":    pitch_matchup_ai,
        "ai_analysis":          ai_analysis,
        "ai_betting":           ai_betting,
    }

    from datetime import date
    today = date.today().isoformat()
    if game_date < today:
        outer_ttl = 86400 * 7   # completed game — never changes
    elif game_date == today:
        outer_ttl = 7200        # today — refresh every 2hrs
    else:
        outer_ttl = 14400       # future game — 4hrs

    await set_cache(cache_key, result, outer_ttl)
    return result


@router.get("/player/{player_id}/spotlight")
async def get_player_spotlight(player_id: int):
    try:
        stats_data = await mlb_api.get_player_stats(player_id, "hitting")
        log = await mlb_api.get_player_game_log(player_id, "hitting")
        people = stats_data.get("people", [{}])
        name = people[0].get("fullName", "Player")
        season_stats = {}
        for s in people[0].get("stats", []):
            if s.get("type", {}).get("displayName") == "season":
                spl = s.get("splits", [])
                if spl:
                    season_stats = spl[0].get("stat", {})
        streak = calculate_streak(log, 15)
        spotlight = await analyze_player_spotlight(name, season_stats, streak)
        return {"player_id": player_id, "name": name, "spotlight": spotlight, "streak": streak}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/game/{game_pk}/cache")
async def clear_game_cache(game_pk: int):
    import aiosqlite
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "data" / "cache.db"
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM cache WHERE key LIKE ?", (f"%{game_pk}%",))
        await db.commit()
    return {"cleared": True, "game_pk": game_pk}
