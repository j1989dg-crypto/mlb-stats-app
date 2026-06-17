"""
HR Probability Model — /api/hr-model/today
Aggregates all batters from today's posted lineups across all games.
Computes a multi-factor HR probability score for each batter.

Factors:
  - Batter Barrel%, Avg EV, Sweet Spot%, Hard-Hit% (Statcast)
  - Season HR/PA rate (MLB Stats API)
  - Park HR factor
  - Weather: temperature + humidity (dome = neutral)
  - Pitcher FB% (fastball usage — more FB = more HR chances)
  - Pitcher HR/BF (how often this pitcher gives up HRs)
  - Platoon advantage (batter hand vs pitcher throw hand)
"""
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Query
from services import mlb_api
from services.splits import get_batter_splits, get_pitcher_splits
from services.statcast import (
    get_batter_statcast, get_pitcher_arsenal, get_bvp_statcast,
    get_batter_savant_leaderboard,
)
from services.weather import get_weather_for_venue, get_park_factors
from services.fangraphs import get_pitcher_fangraphs   # pitcher FIP/HR9 only
from services import ml_engine
from db.cache import get_cache, set_cache
from db.history import log_prediction, log_predictions_bulk, get_prediction_count

router = APIRouter()

# Semaphore to limit concurrent network fetches (prevents rate limiting and connection pool timeouts)
FETCH_SEMAPHORE = asyncio.Semaphore(15)

# League-average benchmarks for context / color coding
LEAGUE_AVG = {
    "barrel_rate":    8.5,
    "avg_exit_velo":  88.5,
    "sweet_spot_rate": 34.0,
    "hard_hit_rate":  39.0,
    "hr_pa":          0.035,   # ~1 HR per 28 PA
}


def _safe(val, default=0.0):
    try:
        return float(val) if val not in (None, "", ".", ".---", "-.--") else default
    except (ValueError, TypeError):
        return default


def _compute_hr_probability(
    barrel_rate: float,
    avg_exit_velo: float,
    sweet_spot_rate: float,
    hard_hit_rate: float,
    hr_pa: float,
    park_hr: int,
    temp_f: float | None,
    humidity: float | None,
    is_dome: bool,
    pitcher_fb_pct: float,
    pitcher_hr_bf: float,
    platoon_adv: bool,
    bvp_hr: int,
    bvp_pa: int,
    recent_hr: int,
    recent_pa: int,
    recent_iso: float,
    pitcher_opp_ops: float,
    weather_hr_factor: int,
    pitch_matchup_score: float = 0.0,
    # ── Advanced metrics v2 ─────────────────────────────────────────────
    xwoba: float = 0.320,           # expected wOBA (FanGraphs), league avg ~0.320
    iso: float = 0.160,             # Isolated Power (SLG - AVG), league avg ~0.160
    wrc_plus: float = 100.0,        # park-adj run creation, 100 = league avg
    chase_pct: float = 30.0,        # O-Swing% (outside zone swing), league avg ~30%
    z_contact_pct: float = 85.0,    # Zone Contact%, league avg ~85%
    pitcher_fip: float = 4.20,      # FIP, league avg ~4.20
    pitcher_hr9: float = 1.25,      # HR/9, league avg ~1.25
    xslg: float = 0.420,            # expected SLG (Statcast), league avg ~0.420
) -> tuple[float, str, list[str]]:
    """
    Returns (hr_pct, confidence_tier, positive_factors_list)
    """
    base = max(hr_pa, 0.01)  # floor at 1% base rate

    # ── Statcast power multipliers ─────────────────────────────────
    barrel_mult = 1.0 + (barrel_rate - LEAGUE_AVG["barrel_rate"]) * 0.028
    ev_mult     = 1.0 + (avg_exit_velo - LEAGUE_AVG["avg_exit_velo"]) * 0.012
    ss_mult     = 1.0 + (sweet_spot_rate - LEAGUE_AVG["sweet_spot_rate"]) * 0.008
    hh_mult     = 1.0 + (hard_hit_rate - LEAGUE_AVG["hard_hit_rate"]) * 0.006

    # ── Park factor ────────────────────────────────────────────────
    park_mult = park_hr / 100.0

    # ── Weather (dome = neutral 1.0) ───────────────────────────────
    if is_dome or temp_f is None:
        temp_mult = 1.0
        hum_mult  = 1.0
    else:
        temp_mult = 1.0 + (temp_f - 72) * 0.002   # warmer = more carry
        hum_mult  = 1.0 - ((humidity or 50) - 50) * 0.001  # drier = more carry

    # ── Pitcher tendencies ─────────────────────────────────────────
    fb_mult    = 1.0 + (pitcher_fb_pct - 35) * 0.004   # more FB = more HR opps
    hr_bf_mult = 1.0 + (pitcher_hr_bf - 0.030) * 8.0   # pitcher HR rate vs league

    # ── Platoon ────────────────────────────────────────────────────
    platoon_mult = 1.08 if platoon_adv else 1.0

    # ── BvP matchup ────────────────────────────────────────────────
    bvp_mult = 1.0
    if bvp_pa >= 5:
        bvp_mult = 1.0 + (bvp_hr * 0.12)
        if bvp_hr >= 1:
            bvp_mult += 0.05
    elif bvp_hr >= 1:
        bvp_mult = 1.0 + (bvp_hr * 0.08)

    # ── Recent form (last 30 days) ─────────────────────────────────
    recent_mult = 1.0
    if recent_pa >= 20:
        recent_rate = recent_hr / recent_pa
        recent_mult = 1.0 + (recent_rate - 0.035) * 4.0
        if recent_iso > 0.220:
            recent_mult += 0.08
        elif recent_iso < 0.100 and recent_hr == 0:
            recent_mult -= 0.10
    recent_mult = max(0.7, min(recent_mult, 1.4))

    # ── Pitcher platoon splits ─────────────────────────────────────
    pitcher_split_mult = 1.0 + (pitcher_opp_ops - 0.720) * 0.8
    pitcher_split_mult = max(0.8, min(pitcher_split_mult, 1.25))

    # ── Wind ───────────────────────────────────────────────────────
    wind_mult = 1.0 + weather_hr_factor * 0.04

    # ── Pitch-type matchup score ───────────────────────────────────
    # Positive when batter crushes the pitches this pitcher throws most
    pitch_mult = 1.0 + (pitch_matchup_score - 88.5) * 0.008
    pitch_mult = max(0.85, min(pitch_mult, 1.20))

    # ── Advanced metrics v2 ────────────────────────────────────────────
    # xwOBA: park-adjusted expected weighted OBP — strongest single power predictor
    xwoba_mult = 1.0 + (xwoba - 0.320) * 1.5
    xwoba_mult = max(0.75, min(xwoba_mult, 1.35))

    # ISO: Isolated Power = SLG - AVG — direct extra-base-hit ability
    iso_mult = 1.0 + (iso - 0.160) * 1.2
    iso_mult = max(0.80, min(iso_mult, 1.30))

    # wRC+: park-adjusted run creation (100 = avg; 130+ = elite)
    wrc_plus_mult = 1.0 + (wrc_plus - 100.0) * 0.003
    wrc_plus_mult = max(0.85, min(wrc_plus_mult, 1.20))

    # Chase %: high chaser = fewer hittable pitches, more swing-and-miss on bad balls
    chase_mult = 1.0 - (chase_pct - 30.0) * 0.004
    chase_mult = max(0.88, min(chase_mult, 1.08))

    # Z-Contact %: contact rate inside the zone — high = better quality swing
    z_contact_mult = 1.0 + (z_contact_pct - 85.0) * 0.005
    z_contact_mult = max(0.90, min(z_contact_mult, 1.10))

    # Pitcher FIP: higher FIP = more HR-prone pitcher
    fip_mult = 1.0 + (pitcher_fip - 4.20) * 0.05
    fip_mult = max(0.85, min(fip_mult, 1.20))

    # Pitcher HR/9: direct measure of how often this pitcher gets long-balled
    hr9_mult = 1.0 + (pitcher_hr9 - 1.25) * 0.15
    hr9_mult = max(0.80, min(hr9_mult, 1.30))

    # xSLG: expected slugging — contact quality without park/luck noise
    xslg_mult = 1.0 + (xslg - 0.420) * 0.8
    xslg_mult = max(0.82, min(xslg_mult, 1.25))

    raw = (base
           * max(0.5, barrel_mult)
           * max(0.7, ev_mult)
           * max(0.8, ss_mult)
           * max(0.8, hh_mult)
           * park_mult
           * max(0.8, temp_mult)
           * max(0.9, hum_mult)
           * max(0.7, fb_mult)
           * max(0.6, hr_bf_mult)
           * platoon_mult
           * bvp_mult
           * recent_mult
           * pitcher_split_mult
           * max(0.8, wind_mult)
           * pitch_mult
           # Advanced v2
           * xwoba_mult
           * iso_mult
           * wrc_plus_mult
           * chase_mult
           * z_contact_mult
           * fip_mult
           * hr9_mult
           * xslg_mult)

    hr_pct = round(min(raw * 100, 50.0), 1)

    # ── Positive factors for confidence ───────────────────────────
    pos = []
    if barrel_rate >= 12:    pos.append("elite barrel%")
    if avg_exit_velo >= 91:  pos.append("elite EV")
    if sweet_spot_rate >= 38: pos.append("elite sweet spot%")
    if hard_hit_rate >= 48:  pos.append("elite hard hit%")
    if park_hr >= 105:       pos.append("favorable park")
    if not is_dome and (temp_f or 70) >= 80: pos.append("warm weather")
    if pitcher_fb_pct >= 45: pos.append("fastball-heavy pitcher")
    if pitcher_hr_bf >= 0.04: pos.append("HR-prone pitcher")
    if platoon_adv:          pos.append("platoon advantage")
    if bvp_hr >= 1:           pos.append(f"career HR vs pitcher ({bvp_hr})")
    if recent_hr >= 2:        pos.append("hot recent form (last 30d)")
    if pitcher_opp_ops >= 0.800: pos.append("pitcher vulnerable vs stance")
    if weather_hr_factor >= 1: pos.append("favorable wind/air carry")
    if pitch_matchup_score >= 91: pos.append("crushes pitcher's primary pitches")
    # Advanced v2 badges
    if xwoba >= 0.380:       pos.append(f"elite xwOBA ({xwoba:.3f})")
    if iso >= 0.220:         pos.append(f"elite ISO ({iso:.3f})")
    if wrc_plus >= 130:      pos.append(f"elite wRC+ ({int(wrc_plus)})")
    if xslg >= 0.530:        pos.append(f"elite xSLG ({xslg:.3f})")
    if pitcher_fip >= 4.80:  pos.append(f"pitcher HR-prone (FIP {pitcher_fip:.2f})")
    if pitcher_hr9 >= 1.60:  pos.append(f"pitcher gives up HRs (HR/9 {pitcher_hr9:.2f})")
    if chase_pct <= 22.0:    pos.append("elite plate discipline (low chase%)")
    if z_contact_pct >= 90:  pos.append("elite zone contact%")

    if len(pos) >= 5:
        conf = "HIGH"
    elif len(pos) >= 2:
        conf = "MEDIUM"
    else:
        conf = "LOW"

    return hr_pct, conf, pos


async def _get_pitcher_fb_and_hr_bf(pitcher_id: int, refresh: bool = False) -> tuple[float, float, str]:
    """Returns (fb_pct, hr_per_bf, pitcher_hand)"""
    if not pitcher_id:
        return 35.0, 0.030, "R"
    try:
        arsenal_task = get_pitcher_arsenal(pitcher_id, refresh=refresh)
        stats_task   = mlb_api.get_player_stats(pitcher_id, "pitching", refresh=refresh)
        arsenal, stats_data = await asyncio.gather(arsenal_task, stats_task, return_exceptions=True)

        # FB% = sum of 4-seam (FF), sinker (SI), cutter (FC) usage
        fb_pct = 35.0
        if isinstance(arsenal, dict) and arsenal.get("arsenal"):
            fb_types = {"FF", "SI", "FC"}
            fb_pct = sum(
                p["usage_pct"] for p in arsenal["arsenal"]
                if p["pitch_type"] in fb_types
            )

        # HR/BF from season stats
        hr_bf = 0.030
        hand  = "R"
        if isinstance(stats_data, dict):
            people = stats_data.get("people", [{}])
            hand = people[0].get("pitchHand", {}).get("code", "R") if people else "R"
            for s in (people[0].get("stats", []) if people else []):
                if s.get("type", {}).get("displayName") == "season":
                    splits = s.get("splits", [])
                    if splits:
                        stat = splits[0].get("stat", {})
                        hr_allowed = int(stat.get("homeRuns", 0) or 0)
                        bf = int(stat.get("battersFaced", 0) or 1)
                        hr_bf = hr_allowed / max(bf, 1)
                    break

        return round(fb_pct, 1), round(hr_bf, 4), hand
    except Exception:
        return 35.0, 0.030, "R"


async def _get_batter_hr_pa(batter_id: int, refresh: bool = False) -> tuple[float, int, int, str]:
    """Returns (hr_pa_rate, hr_count, pa_count, bat_side)"""
    try:
        stats_data = await mlb_api.get_player_stats(batter_id, "hitting", refresh=refresh)
        people = stats_data.get("people", [{}])
        person = people[0] if people else {}
        bat_side = person.get("batSide", {}).get("code", "R") if isinstance(person.get("batSide"), dict) else "R"
        for s in person.get("stats", []):
            if s.get("type", {}).get("displayName") == "season":
                splits = s.get("splits", [])
                if splits:
                    stat = splits[0].get("stat", {})
                    hr  = int(stat.get("homeRuns", 0) or 0)
                    pa  = int(stat.get("plateAppearances", 0) or 0)
                    return (hr / max(pa, 1), hr, pa, bat_side)
        return 0.03, 0, 0, bat_side
    except Exception:
        return 0.03, 0, 0, "R"


@router.get("/today")
async def get_hr_model_today(game_date: str = Query(default=None), refresh: bool = False):
    """
    Return HR probability scores for all batters in starting/expected lineups for a date.
    Sorted by hr_pct descending.
    """
    if not game_date:
        game_date = datetime.now().strftime("%Y-%m-%d")
        
    cache_key = f"hr_model:today:{game_date}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    today = game_date
    games = await mlb_api.get_schedule(today)

    results = []
    confirmed_lineups = 0
    predictions_to_log = []

    # Gather per-game data concurrently
    async def process_game(game: dict):
        nonlocal confirmed_lineups
        game_pk    = game.get("gamePk")
        venue_id   = game.get("venue", {}).get("id")
        away_team  = game.get("teams", {}).get("away", {}).get("team", {})
        home_team  = game.get("teams", {}).get("home", {}).get("team", {})
        away_pp    = game.get("teams", {}).get("away", {}).get("probablePitcher", {})
        home_pp    = game.get("teams", {}).get("home", {}).get("probablePitcher", {})
        game_label = f"{away_team.get('abbreviation','?')} @ {home_team.get('abbreviation','?')}"

        # Park + Weather
        park   = get_park_factors(venue_id) if venue_id else {}
        park_hr = int(park.get("hr", 100))
        is_dome = park.get("dome", False)

        weather     = {}
        temp_f      = None
        humidity    = None
        wind_mph    = 0.0
        wind_dir    = "N/A"
        weather_hr_factor = 0
        if venue_id and not is_dome:
            try:
                weather  = await get_weather_for_venue(venue_id)
                temp_f   = weather.get("temp_f")
                humidity = weather.get("humidity")
                wind_mph = weather.get("wind_mph", 0.0)
                wind_dir = weather.get("wind_dir", "N/A")
                weather_hr_factor = weather.get("hr_factor", 0)
            except Exception:
                pass

        # Lineup
        try:
            lineup = await mlb_api.get_lineup(game_pk)
        except Exception:
            return

        away_batters = lineup.get("away", {}).get("batters", [])[:9]
        home_batters = lineup.get("home", {}).get("batters", [])[:9]

        if away_batters or home_batters:
            confirmed_lineups += 1

        # Pitcher data - use schedule probable pitchers, fall back to lineup pitchers if needed
        away_pid = away_pp.get("id")
        if not away_pid:
            away_l_pitchers = lineup.get("away", {}).get("pitchers", [])
            if away_l_pitchers:
                away_pid = away_l_pitchers[0].get("person", {}).get("id")

        home_pid = home_pp.get("id")
        if not home_pid:
            home_l_pitchers = lineup.get("home", {}).get("pitchers", [])
            if home_l_pitchers:
                home_pid = home_l_pitchers[0].get("person", {}).get("id")

        away_fb, away_hr_bf, away_hand = await _get_pitcher_fb_and_hr_bf(away_pid, refresh=refresh)
        home_fb, home_hr_bf, home_hand = await _get_pitcher_fb_and_hr_bf(home_pid, refresh=refresh)

        async def process_batter(batter_raw: dict, opp_pitcher_hand: str,
                                  opp_fb: float, opp_hr_bf: float,
                                  batting_team: dict, opp_pid: int):
            person = batter_raw.get("person", {})
            bid    = person.get("id")
            name   = person.get("fullName", "Unknown")
            # batSide can come from boxscore player dict OR from stats API
            bat_side_obj = person.get("batSide") or batter_raw.get("batSide") or {}
            if isinstance(bat_side_obj, dict):
                bat_side = bat_side_obj.get("code", "R")
            else:
                bat_side = str(bat_side_obj) or "R"
            team_abbr = batting_team.get("abbreviation", "?")
            order = int(batter_raw.get("battingOrder", 0) or 0) // 100

            if not bid:
                return None

            # Fetch all data concurrently — Savant leaderboard for xwOBA, statcast for everything else
            async with FETCH_SEMAPHORE:
                (
                    sc, hrpa_result, splits_data, bvp_data,
                    pitcher_splits, arsenal_data,
                    savant_lb, fg_pitcher,
                ) = await asyncio.gather(
                    get_batter_statcast(bid, refresh=refresh),
                    _get_batter_hr_pa(bid, refresh=refresh),
                    get_batter_splits(bid, refresh=refresh),
                    get_bvp_statcast(bid, opp_pid, refresh=refresh) if opp_pid else asyncio.sleep(0),
                    get_pitcher_splits(opp_pid, refresh=refresh) if opp_pid else asyncio.sleep(0),
                    get_pitcher_arsenal(opp_pid, refresh=refresh) if opp_pid else asyncio.sleep(0),
                    get_batter_savant_leaderboard(bid, refresh=refresh),
                    get_pitcher_fangraphs(opp_pid) if opp_pid else asyncio.sleep(0),
                )
            hr_pa_rate, hr_count, pa_count, api_bat_side = hrpa_result

            # Prefer boxscore bat_side if available, fall back to stats API
            if bat_side == "R" and api_bat_side in ("L", "S"):
                bat_side = api_bat_side

            if not isinstance(splits_data, dict): splits_data = {}
            if not isinstance(bvp_data, dict): bvp_data = {}
            if not isinstance(pitcher_splits, dict): pitcher_splits = {}
            if not isinstance(arsenal_data, dict): arsenal_data = {}
            if not isinstance(savant_lb, dict): savant_lb = {}
            if not isinstance(fg_pitcher, dict): fg_pitcher = {}

            # ── Extract advanced batter metrics from Baseball Savant ───────────
            sc_iso  = float(sc.get("iso") or 0.160)  if isinstance(sc, dict) else 0.160
            sc_xslg = float(sc.get("xslg") or 0.420) if isinstance(sc, dict) else 0.420

            # xwOBA from Savant leaderboard; fall back to wOBA proxy
            adv_xwoba = float(savant_lb.get("xwoba") or 0.320)
            # xSLG: leaderboard est_slg preferred over pitch-level xslg
            adv_xslg  = float(savant_lb.get("xslg") or sc_xslg)
            adv_iso   = sc_iso   # Statcast (xSLG - xBA) per pitch
            adv_wrc_plus = 100.0  # neutral (no open Savant source)

            # chase% and z-contact% computed inside get_batter_statcast() from raw pitch data
            adv_chase_pct = float(sc.get("chase_pct")     or 30.0) if isinstance(sc, dict) else 30.0
            adv_z_contact = float(sc.get("z_contact_pct") or 85.0) if isinstance(sc, dict) else 85.0

            # ── Pitcher advanced metrics (FanGraphs best-effort) ────────────────
            def _fgp(key, default):
                v = fg_pitcher.get(key) if isinstance(fg_pitcher, dict) else None
                return float(v) if v is not None else default

            adv_pitcher_fip = _fgp("fip",  4.20)
            adv_pitcher_hr9 = _fgp("hr9",  1.25)

            # Recent splits (last 30 days)
            last30 = splits_data.get("last_30", {})
            recent_hr = int(last30.get("hr", 0) or 0)
            recent_pa = int(last30.get("pa", 0) or 0)
            recent_iso = _safe(last30.get("iso", 0.0))

            # BvP Matchup
            bvp_hr = int(bvp_data.get("hr_total", 0) or 0)
            bvp_pa = int(bvp_data.get("total_pa", 0) or 0)

            # ── Pitch-type matchup score ───────────────────────────────────────
            # For each pitch in the pitcher's arsenal, weight batter's avg EV
            # vs that pitch type by the pitcher's usage %, then sum.
            # This rewards batters who crush pitches the opposing pitcher leans on.
            pitch_matchup_score = 0.0
            pitcher_arsenal = arsenal_data.get("arsenal", [])
            bvp_breakdown   = {b["pitch_type"]: b for b in bvp_data.get("pitch_breakdown", [])}
            if pitcher_arsenal:
                weighted_ev_sum = 0.0
                total_usage     = 0.0
                for pitch in pitcher_arsenal:
                    pt      = pitch.get("pitch_type", "")
                    usage   = float(pitch.get("usage_pct", 0) or 0)
                    bvp_pt  = bvp_breakdown.get(pt, {})
                    batter_ev = float(bvp_pt.get("avg_exit_velo") or 88.5)
                    weighted_ev_sum += usage * batter_ev
                    total_usage     += usage
                if total_usage > 0:
                    pitch_matchup_score = round(weighted_ev_sum / total_usage, 1)
                else:
                    pitch_matchup_score = 88.5  # league average fallback
            else:
                pitch_matchup_score = 88.5

            # Pitcher splits vs Hand (Switch hitter opposite of throw hand)
            active_side = "L" if opp_pitcher_hand == "R" else "R"
            if bat_side in ("L", "R"):
                active_side = bat_side
            opp_hand_key = "vs_lhb" if active_side == "L" else "vs_rhb"
            pitcher_vs_hand = pitcher_splits.get(opp_hand_key, {})
            pitcher_opp_ops = _safe(pitcher_vs_hand.get("ops", 0.720), 0.720)

            barrel_rate    = _safe(sc.get("barrel_rate"), 8.5)
            avg_ev         = _safe(sc.get("avg_exit_velo"), 88.5)
            sweet_spot     = _safe(sc.get("sweet_spot_rate"), 34.0)
            hard_hit       = _safe(sc.get("hard_hit_rate"), 39.0)

            platoon_adv = (
                (bat_side == "L" and opp_pitcher_hand == "R") or
                (bat_side == "R" and opp_pitcher_hand == "L") or
                bat_side == "S"
            )

            # Build the feature dict used by both the heuristic and ML model
            features = {
                "barrel_rate":         barrel_rate,
                "avg_exit_velo":       avg_ev,
                "sweet_spot_rate":     sweet_spot,
                "hard_hit_rate":       hard_hit,
                "hr_pa":               hr_pa_rate,
                "park_hr":             park_hr,
                "temp_f":              temp_f if temp_f is not None else (0.0 if is_dome else 72.0),
                "humidity":            humidity if humidity is not None else 50.0,
                "pitcher_fb_pct":      opp_fb,
                "pitcher_hr_bf":       opp_hr_bf,
                "platoon_adv":         1.0 if platoon_adv else 0.0,
                "bvp_hr":              bvp_hr,
                "bvp_pa":              bvp_pa,
                "recent_hr":           recent_hr,
                "recent_pa":           recent_pa,
                "recent_iso":          recent_iso,
                "pitcher_opp_ops":     pitcher_opp_ops,
                "weather_hr_factor":   weather_hr_factor,
                "pitch_matchup_score": pitch_matchup_score,
                # Advanced metrics v2
                "xwoba":               adv_xwoba,
                "iso":                 adv_iso,
                "wrc_plus":            adv_wrc_plus,
                "chase_pct":           adv_chase_pct,
                "z_contact_pct":       adv_z_contact,
                "pitcher_fip":         adv_pitcher_fip,
                "pitcher_hr9":         adv_pitcher_hr9,
                "xslg":                adv_xslg,
            }

            # Heuristic probability (always computed as baseline / fallback)
            hr_pct, conf, factors = _compute_hr_probability(
                barrel_rate=barrel_rate,
                avg_exit_velo=avg_ev,
                sweet_spot_rate=sweet_spot,
                hard_hit_rate=hard_hit,
                hr_pa=hr_pa_rate,
                park_hr=park_hr,
                temp_f=temp_f,
                humidity=humidity,
                is_dome=is_dome,
                pitcher_fb_pct=opp_fb,
                pitcher_hr_bf=opp_hr_bf,
                platoon_adv=platoon_adv,
                bvp_hr=bvp_hr,
                bvp_pa=bvp_pa,
                recent_hr=recent_hr,
                recent_pa=recent_pa,
                recent_iso=recent_iso,
                pitcher_opp_ops=pitcher_opp_ops,
                weather_hr_factor=weather_hr_factor,
                pitch_matchup_score=pitch_matchup_score,
                xwoba=adv_xwoba,
                iso=adv_iso,
                wrc_plus=adv_wrc_plus,
                chase_pct=adv_chase_pct,
                z_contact_pct=adv_z_contact,
                pitcher_fip=adv_pitcher_fip,
                pitcher_hr9=adv_pitcher_hr9,
                xslg=adv_xslg,
            )

            # ML model inference (if model is trained and ready)
            ml_prob_raw = ml_engine.predict(features)  # None if cold-start
            ml_pct      = round(ml_prob_raw * 100, 1) if ml_prob_raw is not None else None
            using_ml    = ml_prob_raw is not None

            predictions_to_log.append({
                "game_date": today,
                "batter_id": bid,
                "batter_name": name,
                "pitcher_id": opp_pid,
                "game_pk": game_pk,
                "features": features,
                "heuristic_prob": hr_pct / 100.0,
                "ml_prob": ml_prob_raw,
            })

            return {
                "batter_id":    bid,
                "name":         name,
                "team":         team_abbr,
                "bat_side":     bat_side,
                "batting_order": order,
                "game":         game_label,
                "game_pk":      game_pk,
                # Statcast
                "barrel_pct":   barrel_rate,
                "ev":           avg_ev,
                "swspot_pct":   sweet_spot,
                "hardhit_pct":  hard_hit,
                # Batter season
                "hr_pa":        round(hr_pa_rate * 100, 2),  # as pct
                "hr":           hr_count,
                "pa":           pa_count,
                # Venue
                "park":         park_hr,
                "temp":         round(temp_f, 0) if temp_f else None,
                "humidity":     round(humidity, 0) if humidity else None,
                "dome":         is_dome,
                "wind_speed":   round(wind_mph, 1),
                "wind_dir":     wind_dir,
                "weather_impact": weather.get("baseball_impact", ""),
                # Pitcher
                "fb_pct":       round(opp_fb, 1),
                "p_hr_bf":      round(opp_hr_bf * 100, 2),  # as pct
                "pitcher_opp_ops": round(pitcher_opp_ops, 3),
                # Matchup
                "platoon_adv":  platoon_adv,
                "opp_hand":     opp_pitcher_hand,
                "bvp_hr":       bvp_hr,
                "bvp_pa":       bvp_pa,
                # Recent form
                "recent_hr":    recent_hr,
                "recent_pa":    recent_pa,
                "recent_iso":   recent_iso,
                # Pitch matchup
                "pitch_matchup_score": pitch_matchup_score,
                # Advanced metrics v2
                "xwoba":          round(adv_xwoba, 3),
                "iso":            round(adv_iso, 3),
                "wrc_plus":       int(adv_wrc_plus) if adv_wrc_plus else None,
                "chase_pct":      round(adv_chase_pct, 1),
                "z_contact_pct":  round(adv_z_contact, 1),
                "xslg":           round(adv_xslg, 3),
                "pitcher_fip":    round(adv_pitcher_fip, 2),
                "pitcher_hr9":    round(adv_pitcher_hr9, 2),
                # Result
                "hr_pct":       ml_pct if using_ml else hr_pct,
                "heuristic_pct": hr_pct,
                "ml_pct":       ml_pct,
                "using_ml":     using_ml,
                "confidence":   conf,
                "pos_factors":  factors,
            }

        # Process all batters in this game concurrently
        away_tasks = [
            process_batter(b, home_hand, home_fb, home_hr_bf, away_team, home_pid)
            for b in away_batters
        ]
        home_tasks = [
            process_batter(b, away_hand, away_fb, away_hr_bf, home_team, away_pid)
            for b in home_batters
        ]
        all_results = await asyncio.gather(*away_tasks, *home_tasks)
        for r in all_results:
            if r:
                results.append(r)

    # Process all games concurrently
    await asyncio.gather(*[process_game(g) for g in games])

    if predictions_to_log:
        await log_predictions_bulk(predictions_to_log)

    # Sort by HR% descending
    results.sort(key=lambda x: -x["hr_pct"])

    payload = {
        "date":               today,
        "total_batters":      len(results),
        "confirmed_lineups":  confirmed_lineups,
        "total_games":        len(games),
        "statcast_active":    True,
        "weather_active":     True,
        "batters":            results,
    }

    await set_cache(cache_key, payload, 1200)  # 20 min cache
    return payload


@router.get("/ml-status")
async def get_ml_status():
    """Return the current state of the ML model and training data."""
    resolved = await get_prediction_count()
    return {
        "model_active":    ml_engine.model_exists(),
        "model_trained_at": ml_engine.model_trained_at(),
        "resolved_predictions": resolved,
        "min_samples_needed": ml_engine.MIN_SAMPLES,
        "cold_start":      resolved < ml_engine.MIN_SAMPLES,
        "progress_pct":    round(min(resolved / ml_engine.MIN_SAMPLES * 100, 100), 1),
    }


@router.post("/test-sync")
async def test_sync_yesterday():
    """Manually trigger the nightly sync for yesterday (dev/debug endpoint)."""
    from services.nightly_sync import sync_yesterday_results
    try:
        await sync_yesterday_results()
        resolved = await get_prediction_count()
        return {"status": "ok", "resolved_predictions": resolved}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/test-train")
async def test_train_model():
    """Manually trigger model retraining on all resolved data (dev/debug endpoint)."""
    from db.history import get_training_data
    from services.ml_engine import train_model
    from db.cache import set_cache
    from datetime import date
    training_data = await get_training_data()
    success = train_model(training_data)
    resolved = await get_prediction_count()
    # Bust today's HR model cache so next call gets fresh ML predictions
    if success:
        today_str = date.today().isoformat()
        await set_cache(f"hr_model:today:{today_str}", None, 1)
    return {
        "status":        "trained" if success else "skipped",
        "training_rows": len(training_data),
        "resolved_predictions": resolved,
        "model_active":  ml_engine.model_exists(),
        "model_trained_at": ml_engine.model_trained_at(),
    }


@router.get("/debug-predict")
async def debug_predict():
    """Test ML predict() live from within the running server process."""
    import traceback
    test_features = {k: 0.0 for k in ml_engine.FEATURE_KEYS}
    test_features.update({
        "barrel_rate": 14.0, "avg_exit_velo": 93.0, "hr_pa": 0.06,
        "xwoba": 0.390, "iso": 0.250, "chase_pct": 24.0, "z_contact_pct": 80.0,
    })
    try:
        result = ml_engine.predict(test_features)
        return {
            "model_exists": ml_engine.model_exists(),
            "model_trained_at": ml_engine.model_trained_at(),
            "feature_count": len(ml_engine.FEATURE_KEYS),
            "predict_result": result,
            "error": None,
        }
    except Exception as e:
        return {
            "model_exists": ml_engine.model_exists(),
            "error": str(e),
            "traceback": traceback.format_exc(),
        }

