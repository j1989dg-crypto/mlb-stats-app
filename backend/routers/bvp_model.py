"""
Batter vs. Pitcher (BvP) Model — /api/bvp
Provides:
  GET /api/bvp/games?game_date=YYYY-MM-DD  — today's games with full lineups
  GET /api/bvp/player/{batter_id}/vs/{pitcher_id}  — deep BvP matchup card
"""
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Query

from services import mlb_api
from services.statcast import (
    get_batter_statcast,
    get_pitcher_arsenal,
    get_bvp_statcast,
    get_batter_savant_leaderboard,
)
from services.splits import get_batter_splits, get_pitcher_splits
from services.fangraphs import get_batter_fangraphs, get_pitcher_fangraphs
from services.park_factors import get_park_factor
from db.cache import get_cache, set_cache

logger = logging.getLogger(__name__)
router = APIRouter()

FETCH_SEM = asyncio.Semaphore(12)

PITCH_NAMES = {
    "FF": "4-Seam FB", "SI": "Sinker", "FC": "Cutter",
    "SL": "Slider",    "ST": "Sweeper", "CU": "Curveball",
    "CH": "Changeup",  "FS": "Splitter", "KC": "Knuckle-Curve",
    "SV": "Slurve",    "KN": "Knuckleball",
}

_SWING_DESC = {
    "swinging_strike", "swinging_strike_blocked", "foul_tip",
    "foul", "foul_bunt", "hit_into_play", "hit_into_play_no_out",
    "hit_into_play_score",
}
_WHIFF_DESC = {"swinging_strike", "swinging_strike_blocked", "foul_tip"}


def _safe(val, default=0.0):
    try:
        return float(val) if val not in (None, "", ".", ".---", "-.--") else default
    except (ValueError, TypeError):
        return default


def _verdict(whiff_pct: float, avg_ev: float | None) -> str:
    ev = avg_ev or 85.0
    if whiff_pct >= 45:
        return "WEAK"
    if whiff_pct >= 30:
        return "STRUGGLES"
    if ev >= 94 and whiff_pct < 20:
        return "CRUSHES"
    if ev >= 90 and whiff_pct < 25:
        return "HANDLES WELL"
    return "NEUTRAL"


def _score_color(score: int) -> str:
    if score >= 75:
        return "#00e676"
    if score >= 50:
        return "#ffd600"
    if score >= 30:
        return "#ff9800"
    return "#ff1744"


# ─── /games ──────────────────────────────────────────────────────────────────

@router.get("/games")
async def get_bvp_games(
    game_date: str = Query(default=None),
    refresh: bool = False,
):
    """
    Returns all games for a date, with full batting lineups and probable pitchers.
    Lineup order, hand, position, and basic season stats included.
    """
    if not game_date:
        game_date = datetime.now().strftime("%Y-%m-%d")

    cache_key = f"bvp:games:{game_date}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    games = await mlb_api.get_schedule(game_date)
    results = []

    async def process_game(game: dict):
        game_pk   = game.get("gamePk")
        away_team = game.get("teams", {}).get("away", {}).get("team", {})
        home_team = game.get("teams", {}).get("home", {}).get("team", {})
        away_pp   = game.get("teams", {}).get("away", {}).get("probablePitcher", {})
        home_pp   = game.get("teams", {}).get("home", {}).get("probablePitcher", {})
        status    = game.get("status", {}).get("detailedState", "Scheduled")

        # Game time
        game_dt = game.get("gameDate", "")
        try:
            dt_obj = datetime.fromisoformat(game_dt.replace("Z", "+00:00"))
            # Convert UTC to ET (UTC-4 in summer)
            from datetime import timezone, timedelta
            et = dt_obj.astimezone(timezone(timedelta(hours=-4)))
            game_time = et.strftime("%-I:%M %p ET")
        except Exception:
            game_time = "TBD"

        # Probable pitcher ERA strings
        def _pp_note(pp: dict) -> str:
            return pp.get("note", "") or ""

        away_pp_info = {
            "id":     away_pp.get("id"),
            "name":   away_pp.get("fullName", "TBD"),
            "throws": "?",
            "note":   _pp_note(away_pp),
        } if away_pp else {"id": None, "name": "TBD", "throws": "?", "note": ""}

        home_pp_info = {
            "id":     home_pp.get("id"),
            "name":   home_pp.get("fullName", "TBD"),
            "throws": "?",
            "note":   _pp_note(home_pp),
        } if home_pp else {"id": None, "name": "TBD", "throws": "?", "note": ""}

        # Lineup
        try:
            async with FETCH_SEM:
                lineup = await mlb_api.get_lineup(game_pk)
        except Exception:
            lineup = {"away": {"batters": []}, "home": {"batters": []}}

        def _extract_batters(side_data: dict) -> list:
            batters = []
            for b in side_data.get("batters", [])[:9]:
                person = b.get("person", {})
                bat_side_obj = person.get("batSide") or b.get("batSide") or {}
                bats = bat_side_obj.get("code", "R") if isinstance(bat_side_obj, dict) else str(bat_side_obj or "R")
                pos  = b.get("position", {})
                pos_abbr = pos.get("abbreviation", "?") if isinstance(pos, dict) else "?"
                order = int(b.get("battingOrder", 0) or 0) // 100 or (len(batters) + 1)
                pid  = person.get("id")
                if not pid:
                    continue
                batters.append({
                    "id":       pid,
                    "name":     person.get("fullName", "Unknown"),
                    "bats":     bats,
                    "position": pos_abbr,
                    "order":    order,
                })
            return batters

        away_lineup = _extract_batters(lineup.get("away", {}))
        home_lineup = _extract_batters(lineup.get("home", {}))

        # Pitcher hand from lineup pitchers (probable pitcher may lack it)
        def _pitcher_hand(side_data: dict, pp: dict) -> str:
            pitchers = side_data.get("pitchers", [])
            for p in pitchers:
                h = (p.get("person", {}).get("pitchHand") or {}).get("code")
                if h:
                    return h
            return pp.get("pitchHand", {}).get("code", "R") if isinstance(pp.get("pitchHand"), dict) else "R"

        away_pp_info["throws"] = _pitcher_hand(lineup.get("away", {}), away_pp)
        home_pp_info["throws"] = _pitcher_hand(lineup.get("home", {}), home_pp)

        results.append({
            "game_pk":        game_pk,
            "away_abbr":      away_team.get("abbreviation", "?"),
            "away_name":      away_team.get("name", ""),
            "home_abbr":      home_team.get("abbreviation", "?"),
            "home_name":      home_team.get("name", ""),
            "game_time":      game_time,
            "status":         status,
            "away_pitcher":   away_pp_info,
            "home_pitcher":   home_pp_info,
            "away_lineup":    away_lineup,
            "home_lineup":    home_lineup,
            "lineup_source":  lineup.get("source", "unknown"),
        })

    await asyncio.gather(*[process_game(g) for g in games], return_exceptions=True)

    # Sort by game time
    results.sort(key=lambda x: x.get("game_time", ""))

    payload = {
        "game_date": game_date,
        "total_games": len(results),
        "games": results,
    }
    await set_cache(cache_key, payload, 300)  # 5 min cache
    return payload


# ─── /player/{batter_id}/vs/{pitcher_id} ─────────────────────────────────────

@router.get("/player/{batter_id}/vs/{pitcher_id}")
async def get_bvp_player(
    batter_id: int,
    pitcher_id: int,
    order: int = Query(default=None),
    home_team: str = Query(default=None),
    refresh: bool = False
):
    """
    Deep BvP matchup card for one batter vs. one pitcher.
    Returns: career BvP stats, Statcast power metrics, pitch-type matchup,
             platoon edge, recent form, and composite scores.
    """
    # Sanitize inputs in case they are FastAPI Query/default objects when called programmatically
    if not isinstance(order, int):
        try:
            order = int(order)
        except (ValueError, TypeError):
            order = None

    if not isinstance(home_team, str):
        home_team = None

    if not isinstance(refresh, bool):
        refresh = False

    cache_key = f"bvp:player:{batter_id}:vs:{pitcher_id}:order:{order}:home:{home_team}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    # Parallel fetch all data
    async with FETCH_SEM:
        (
            batter_stats_raw,
            pitcher_stats_raw,
            batter_sc,
            pitcher_arsenal,
            bvp_sc,
            batter_savant,
            batter_splits_raw,
            pitcher_splits_raw,
            bvp_mlb,
            fg_batter,
            fg_pitcher,
        ) = await asyncio.gather(
            mlb_api.get_player_stats(batter_id,  "hitting",  refresh=refresh),
            mlb_api.get_player_stats(pitcher_id, "pitching", refresh=refresh),
            get_batter_statcast(batter_id,  refresh=refresh),
            get_pitcher_arsenal(pitcher_id, refresh=refresh),
            get_bvp_statcast(batter_id, pitcher_id, refresh=refresh),
            get_batter_savant_leaderboard(batter_id, refresh=refresh),
            get_batter_splits(batter_id,  refresh=refresh),
            get_pitcher_splits(pitcher_id, refresh=refresh),
            mlb_api.get_batter_vs_pitcher(batter_id, pitcher_id),
            get_batter_fangraphs(batter_id),
            get_pitcher_fangraphs(pitcher_id),
            return_exceptions=True,
        )

    # Convert Exceptions to dicts
    fg_batter_data = fg_batter if isinstance(fg_batter, dict) else {}
    fg_pitcher_data = fg_pitcher if isinstance(fg_pitcher, dict) else {}
    b_splits = batter_splits_raw if isinstance(batter_splits_raw, dict) else {}
    p_splits = pitcher_splits_raw if isinstance(pitcher_splits_raw, dict) else {}

    # ── Batter info ────────────────────────────────────────────────────────
    batter_info = {"id": batter_id, "name": "Unknown", "bats": "R", "team": "?"}
    try:
        b_people = batter_stats_raw.get("people", [{}])
        b_person = b_people[0] if b_people else {}
        batter_info["name"]  = b_person.get("fullName", "Unknown")
        batter_info["team"]  = b_person.get("currentTeam", {}).get("abbreviation", "?")
        batter_info["bats"]  = b_person.get("batSide", {}).get("code", "R")
        batter_info["pos"]   = b_person.get("primaryPosition", {}).get("abbreviation", "?")
    except Exception:
        pass

    # ── Pitcher info ───────────────────────────────────────────────────────
    pitcher_info = {"id": pitcher_id, "name": "Unknown", "throws": "R", "team": "?"}
    try:
        p_people = pitcher_stats_raw.get("people", [{}])
        p_person = p_people[0] if p_people else {}
        pitcher_info["name"]   = p_person.get("fullName", "Unknown")
        pitcher_info["team"]   = p_person.get("currentTeam", {}).get("abbreviation", "?")
        pitcher_info["throws"] = p_person.get("pitchHand", {}).get("code", "R")
        # ERA from season stats
        for s in p_person.get("stats", []):
            if s.get("type", {}).get("displayName") == "season":
                splits = s.get("splits", [])
                if splits:
                    st = splits[0].get("stat", {})
                    pitcher_info["era"]  = st.get("era", "--")
                    pitcher_info["whip"] = st.get("whip", "--")
                    pitcher_info["ip"]   = st.get("inningsPitched", "--")
                    pitcher_info["so"]   = st.get("strikeOuts", 0)
                break
    except Exception:
        pass

    # ── Platoon advantage ──────────────────────────────────────────────────
    bats   = batter_info.get("bats", "R")
    throws = pitcher_info.get("throws", "R")
    # Platoon advantage: batter opposite hand vs pitcher  (L batter vs R pitcher, R batter vs L pitcher)
    platoon_adv = (bats == "L" and throws == "R") or (bats == "R" and throws == "L")
    platoon_label = "Platoon Edge ✓" if platoon_adv else "Same Handedness"

    # ── Career BvP (MLB stats API) ─────────────────────────────────────────
    career_bvp = {"pa": 0, "ab": 0, "hits": 0, "hr": 0, "avg": ".---", "ops": ".---", "slg": ".---", "obp": ".---", "doubles": 0, "triples": 0, "bb": 0, "so": 0}
    try:
        if isinstance(bvp_mlb, dict):
            for stat_block in bvp_mlb.get("stats", []):
                splits = stat_block.get("splits", [])
                if splits:
                    st = splits[0].get("stat", {})
                    career_bvp = {
                        "pa":   int(st.get("plateAppearances", 0) or 0),
                        "ab":   int(st.get("atBats", 0) or 0),
                        "hits": int(st.get("hits", 0) or 0),
                        "hr":   int(st.get("homeRuns", 0) or 0),
                        "avg":  st.get("avg", ".---"),
                        "ops":  st.get("ops", ".---"),
                        "slg":  st.get("slg", ".---"),
                        "obp":  st.get("obp", ".---"),
                        "doubles": int(st.get("doubles", 0) or 0),
                        "triples": int(st.get("triples", 0) or 0),
                        "bb":   int(st.get("baseOnBalls", 0) or 0),
                        "so":   int(st.get("strikeOuts", 0) or 0),
                    }
                    break
    except Exception:
        pass

    # ── Statcast power (batter season) ────────────────────────────────────
    sc = batter_sc if isinstance(batter_sc, dict) else {}
    savant = batter_savant if isinstance(batter_savant, dict) else {}

    xwoba        = _safe(savant.get("xwoba"), 0.320)
    xba          = _safe(sc.get("xba") or savant.get("xba"), 0.250)
    xslg         = _safe(sc.get("xslg") or savant.get("xslg"), 0.420)
    iso          = _safe(sc.get("iso") or savant.get("iso"), 0.160)
    barrel_rate  = _safe(sc.get("barrel_rate"), 8.5)
    avg_ev       = _safe(sc.get("avg_exit_velo"), 88.5)
    hard_hit     = _safe(sc.get("hard_hit_rate"), 39.0)
    sweet_spot   = _safe(sc.get("sweet_spot_rate"), 34.0)
    whiff_rate   = _safe(sc.get("whiff_rate"), 24.0)
    chase_pct    = _safe(sc.get("chase_pct") or savant.get("chase_pct"), 30.0)
    z_contact    = _safe(sc.get("z_contact_pct") or savant.get("z_contact_pct"), 85.0)
    k_rate       = _safe(sc.get("k_rate"), 22.0)
    bb_rate      = _safe(sc.get("bb_rate"), 8.5)

    # Pull% from BvP statcast if available
    pull_pct = 0.0
    try:
        if isinstance(bvp_sc, dict) and bvp_sc.get("bvp_rows"):
            pull_hits = sum(1 for r in bvp_sc["bvp_rows"] if r.get("hit_location", "") in ("1", "2", "3"))
            total_bip = len([r for r in bvp_sc["bvp_rows"] if r.get("launch_speed")])
            pull_pct  = round(pull_hits / max(1, total_bip) * 100, 1) if total_bip else 0.0
    except Exception:
        pass

    # Batter season HR/PA
    hr_count = _safe(sc.get("hr_count"), 0)
    pa_count = _safe(sc.get("pa_sampled"), 100)
    hr_pa    = round(hr_count / max(1, pa_count) * 100, 2)

    statcast_block = {
        "barrel_rate":   round(barrel_rate, 1),
        "avg_exit_velo": round(avg_ev, 1),
        "hard_hit_rate": round(hard_hit, 1),
        "sweet_spot":    round(sweet_spot, 1),
        "xwoba":         round(xwoba, 3),
        "xba":           round(xba, 3),
        "xslg":          round(xslg, 3),
        "iso":           round(iso, 3),
        "whiff_rate":    round(whiff_rate, 1),
        "chase_pct":     round(chase_pct, 1),
        "z_contact":     round(z_contact, 1),
        "k_rate":        round(k_rate, 1),
        "bb_rate":       round(bb_rate, 1),
        "pull_pct":      pull_pct,
        "hr_pa":         hr_pa,
    }

    # ── Zone stats from BvP rows ──────────────────────────────────────────
    bvp_rows = bvp_sc.get("bvp_rows", []) if isinstance(bvp_sc, dict) else []
    in_zone_swings = 0
    in_zone_whiffs = 0
    out_zone_swings = 0
    out_zone_whiffs = 0
    
    for r in bvp_rows:
        desc = r.get("description", "")
        # zone code <= 9 is typically strike zone
        zone_val = None
        try:
            zone_val = int(r.get("zone"))
        except (ValueError, TypeError):
            pass
            
        if zone_val is not None:
            is_in_zone = zone_val <= 9
            is_swing = desc in _SWING_DESC
            is_whiff = desc in _WHIFF_DESC
            
            if is_in_zone:
                if is_swing:
                    in_zone_swings += 1
                    if is_whiff:
                        in_zone_whiffs += 1
            else:
                if is_swing:
                    out_zone_swings += 1
                    if is_whiff:
                        out_zone_whiffs += 1

    zone_stats = {
        "in_zone_whiff_pct": round(in_zone_whiffs / max(1, in_zone_swings) * 100, 1) if in_zone_swings else whiff_rate,
        "out_zone_whiff_pct": round(out_zone_whiffs / max(1, out_zone_swings) * 100, 1) if out_zone_swings else whiff_rate,
        "in_zone_sample": in_zone_swings,
        "out_zone_sample": out_zone_swings,
    }

    # ── Pitch-type matchup ────────────────────────────────────────────────
    pitch_matchup = []
    try:
        arsenal = pitcher_arsenal if isinstance(pitcher_arsenal, dict) else {}
        pitches = arsenal.get("arsenal", [])

        for pitch in pitches:
            pt = pitch.get("pitch_type", "")
            usage = pitch.get("usage_pct", 0)
            pitcher_whiff = pitch.get("whiff_pct", 0)
            avg_velo = pitch.get("avg_velo")

            # Batter EV vs this pitch type from BvP statcast rows
            bvp_pitch_rows = [r for r in bvp_rows if r.get("pitch_type") == pt]
            bvp_ev_vals = [
                float(r["launch_speed"]) for r in bvp_pitch_rows
                if r.get("launch_speed") and r["launch_speed"] not in ("", "null")
            ]
            bvp_swings = sum(1 for r in bvp_pitch_rows if r.get("description", "") in _SWING_DESC)
            bvp_whiffs  = sum(1 for r in bvp_pitch_rows if r.get("description", "") in _WHIFF_DESC)
            bvp_whiff_pct = round(bvp_whiffs / bvp_swings * 100, 1) if bvp_swings else pitcher_whiff
            bvp_avg_ev    = round(sum(bvp_ev_vals) / len(bvp_ev_vals), 1) if bvp_ev_vals else avg_ev

            verdict = _verdict(bvp_whiff_pct, bvp_avg_ev)

            pitch_matchup.append({
                "pitch_type":      pt,
                "pitch_name":      PITCH_NAMES.get(pt, pitch.get("pitch_name", pt)),
                "usage_pct":       usage,
                "pitcher_whiff":   pitcher_whiff,
                "batter_whiff":    bvp_whiff_pct,
                "batter_avg_ev":   bvp_avg_ev,
                "avg_velo":        avg_velo,
                "bvp_sample_size": len(bvp_pitch_rows),
                "verdict":         verdict,
            })

        # Sort by usage descending
        pitch_matchup.sort(key=lambda x: -x["usage_pct"])
    except Exception as e:
        logger.warning(f"pitch_matchup error: {e}")

    # ── Recent form (last 30 game log entries) ────────────────────────────
    recent_form = {"pa": 0, "hr": 0, "avg": ".---", "iso": None, "hot": False}
    try:
        game_log = await mlb_api.get_player_game_log(batter_id, "hitting")
        recent   = game_log[-30:] if len(game_log) >= 30 else game_log
        r_hits = r_hr = r_pa = r_ab = r_slg_num = 0
        for g in recent:
            st = g.get("stat", {})
            r_pa   += int(st.get("plateAppearances", 0) or 0)
            r_ab   += int(st.get("atBats", 0) or 0)
            r_hits += int(st.get("hits", 0) or 0)
            r_hr   += int(st.get("homeRuns", 0) or 0)
            r_slg_num += (
                int(st.get("singles", 0) or 0)
                + 2 * int(st.get("doubles", 0) or 0)
                + 3 * int(st.get("triples", 0) or 0)
                + 4 * int(st.get("homeRuns", 0) or 0)
            )
        r_avg  = round(r_hits / max(1, r_ab), 3) if r_ab else 0
        r_slg  = round(r_slg_num / max(1, r_ab), 3) if r_ab else 0
        r_iso  = round(r_slg - r_avg, 3) if r_ab else 0
        recent_form = {
            "pa":    r_pa,
            "hr":    r_hr,
            "avg":   f".{int(r_avg * 1000):03d}" if r_ab else ".---",
            "slg":   f".{int(r_slg * 1000):03d}" if r_ab else ".---",
            "iso":   round(r_iso, 3),
            "hot":   r_avg >= 0.280 and r_hr >= 1,
        }
    except Exception:
        pass

    # ── Pitcher Recent Form (last 5 starts) + Days Rest ──────────────────
    pitcher_recent = {"games": 0, "era": "-.--", "whip": "-.--", "k_rate": 0.0, "ip": "0.0", "bb": 0, "so": 0, "days_rest": None, "pitch_count_last": None}
    try:
        p_game_log = await mlb_api.get_player_game_log(pitcher_id, "pitching")
        p_recent = p_game_log[-5:] if len(p_game_log) >= 5 else p_game_log
        pr_er = pr_h = pr_bb = pr_so = pr_bf = 0
        pr_ip_total = 0.0
        for g in p_recent:
            st = g.get("stat", {})
            pr_er += int(st.get("earnedRuns", 0) or 0)
            pr_h  += int(st.get("hits", 0) or 0)
            pr_bb += int(st.get("baseOnBalls", 0) or 0)
            pr_so += int(st.get("strikeOuts", 0) or 0)
            pr_bf += int(st.get("battersFaced", 0) or 0)
            ip_str = str(st.get("inningsPitched", "0.0"))
            pr_ip_total += float(ip_str.replace(".1", ".333").replace(".2", ".667")) if ip_str else 0.0

        # Days rest + last-start pitch count
        days_rest = None
        pitch_count_last = None
        if p_game_log:
            last_game = p_game_log[-1]
            last_date_str = last_game.get("date", "")
            last_st = last_game.get("stat", {})
            pitch_count_last = int(last_st.get("numberOfPitches", 0) or 0) or None
            if last_date_str:
                try:
                    from datetime import date as _date
                    last_dt = datetime.strptime(last_date_str[:10], "%Y-%m-%d").date()
                    days_rest = (_date.today() - last_dt).days
                except Exception:
                    pass

        if pr_ip_total > 0:
            pr_era = (pr_er * 9) / pr_ip_total
            pr_whip = (pr_h + pr_bb) / pr_ip_total
            pitcher_recent = {
                "games": len(p_recent),
                "era": f"{pr_era:.2f}",
                "whip": f"{pr_whip:.2f}",
                "k_rate": round((pr_so / max(1, pr_bf)) * 100, 1),
                "ip": f"{pr_ip_total:.1f}",
                "bb": pr_bb,
                "so": pr_so,
                "days_rest": days_rest,
                "pitch_count_last": pitch_count_last,
            }
    except Exception:
        pass

    # ── Park factor ────────────────────────────────────────────────────────
    park_factor = get_park_factor(home_team) if home_team else None

    # ── Batter L7 / L14 hot-streak analysis ────────────────────────────────
    l7_trend = None
    try:
        l7  = b_splits.get("last_7", {})
        l14 = b_splits.get("last_14", {})
        l30 = b_splits.get("last_30", {})
        l7_ops  = _safe(l7.get("ops"),  0.0)
        l14_ops = _safe(l14.get("ops"), 0.0)
        l30_ops = _safe(l30.get("ops"), 0.0)
        # Trend direction: compare L7 to L30 baseline
        if l7_ops > 0 and l30_ops > 0:
            diff = round(l7_ops - l30_ops, 3)
            if diff >= 0.100:
                trend_label = "🔥 Scorching (L7)"
                trend_color = "#00e676"
            elif diff >= 0.040:
                trend_label = "↑ Heating Up"
                trend_color = "#69f0ae"
            elif diff <= -0.100:
                trend_label = "🧊 Ice Cold (L7)"
                trend_color = "#ff1744"
            elif diff <= -0.040:
                trend_label = "↓ Cooling Off"
                trend_color = "#ff9800"
            else:
                trend_label = "→ Stable"
                trend_color = "#90a4ae"
            l7_trend = {
                "l7_ops":  round(l7_ops, 3),
                "l14_ops": round(l14_ops, 3),
                "l30_ops": round(l30_ops, 3),
                "l7_avg":  l7.get("avg", ".---"),
                "l14_avg": l14.get("avg", ".---"),
                "l7_hr":   int(l7.get("hr", 0) or 0),
                "l14_hr":  int(l14.get("hr", 0) or 0),
                "diff":    diff,
                "trend_label": trend_label,
                "trend_color": trend_color,
            }
    except Exception:
        pass

    # ── Batter splits vs this pitcher's hand ─────────────────────────────
    batter_ops_vs_hand = 0.720
    try:
        hand   = throws
        key    = "vs_rhp" if hand == "R" else "vs_lhp"
        st     = b_splits.get(key, {})
        ops    = _safe(st.get("ops"), 0.720)
        batter_ops_vs_hand = ops
    except Exception:
        pass

    # ── Pitcher HR/BF ─────────────────────────────────────────────────────
    pitcher_hr_bf = 0.030
    pitcher_hr9   = 1.25
    try:
        p_people = pitcher_stats_raw.get("people", [{}]) if isinstance(pitcher_stats_raw, dict) else [{}]
        p_person = p_people[0] if p_people else {}
        for s in p_person.get("stats", []):
            if s.get("type", {}).get("displayName") == "season":
                splits = s.get("splits", [])
                if splits:
                    st  = splits[0].get("stat", {})
                    hr_a = int(st.get("homeRuns", 0) or 0)
                    bf   = int(st.get("battersFaced", 1) or 1)
                    ip_s = str(st.get("inningsPitched", "0") or "0")
                    ip_f = float(ip_s.replace(".1", ".333").replace(".2", ".667")) if ip_s else 1.0
                    pitcher_hr_bf = hr_a / max(bf, 1)
                    pitcher_hr9   = round(hr_a / max(ip_f, 1) * 9, 2)
                break
    except Exception:
        pass

    # ── Pitcher performance vs this batter's lineup slot ───────────────────
    slot_split = None
    slot_label = None
    if order:
        try:
            order_splits = p_splits.get("order_splits", {})
            slot_data = order_splits.get(str(order))
            if slot_data and slot_data.get("pa", 0) > 0:
                slot_split = slot_data
                slot_label = f"Allows {slot_data.get('ops', '.---')} OPS vs Lineup Slot {order}"
        except Exception:
            pass

    # ── Composite scores — Power + Matchup + Park + Trend + Rest ──────────
    # Power score (0-100) — Statcast & FanGraphs wRC+ based offensive power
    wrc_val = _safe(fg_batter_data.get("wrc_plus"), 100.0)
    wrc_pts = min(40, max(0, int((wrc_val / 160.0) * 40)))  # wRC+ up to 160 = 40pts

    power_score = min(100, max(0, int(
        wrc_pts +
        (barrel_rate  / 25.0  * 20) +   # barrel up to 25 = 20pts
        (avg_ev       / 115.0 * 15) +   # EV up to 115 = 15pts
        (hard_hit     / 65.0  * 15) +   # HH up to 65 = 15pts
        (xwoba        / 0.500 * 10)     # xwOBA up to .500 = 10pts
    )))

    # Matchup score (0-100)
    bvp_boost   = min(30, career_bvp["hr"] * 10 + min(10, career_bvp["pa"] // 5))
    platoon_pts = 15 if platoon_adv else 0

    xfip_val = _safe(fg_pitcher_data.get("xfip") or fg_pitcher_data.get("fip"), 4.20)
    pitcher_vuln_pts = int((xfip_val - 4.20) * 10)
    pitcher_vuln = min(15, max(-10, pitcher_vuln_pts)) + 5

    ops_pts    = min(20, int((batter_ops_vs_hand - 0.600) / 0.400 * 20))
    recent_pts = min(15, recent_form["hr"] * 5 if recent_form["hot"] else 5)

    slot_pts = 0
    if slot_split:
        slot_ops = _safe(slot_split.get("ops"), 0.720)
        slot_pts = int((slot_ops - 0.720) * 40)
        slot_pts = max(-10, min(10, slot_pts))

    # ── Park factor adjustment (±5 pts max) ────────────────────────────────
    park_pts = 0
    if park_factor:
        hr_f = park_factor.get("hr_factor", 100)
        # Scale: factor 122 (Coors) → +5, factor 88 (Oracle) → -5
        park_pts = max(-5, min(5, round((hr_f - 100) / 4.4)))

    # ── L7 hot streak adjustment (±8 pts max) ──────────────────────────────
    streak_pts = 0
    if l7_trend:
        diff = l7_trend.get("diff", 0.0)
        # +/- 8 pts scaled to OPS diff of ±0.200
        streak_pts = max(-8, min(8, round(diff / 0.025)))

    # ── Pitcher days rest adjustment (±5 pts) ──────────────────────────────
    rest_pts = 0
    dr = pitcher_recent.get("days_rest")
    if dr is not None:
        if dr <= 3:     # Short rest — pitcher likely fatigued → batter edge +4
            rest_pts = 4
        elif dr >= 8:   # Extra rest — pitcher fresher → slight pitcher edge -2
            rest_pts = -2
        elif dr == 4:   # Normal 4-day rest → neutral
            rest_pts = 0
        # 5-7 days = slight freshness → -1
        else:
            rest_pts = -1

    matchup_score = min(100, max(0,
        35 + bvp_boost + platoon_pts + pitcher_vuln + ops_pts + recent_pts
        + slot_pts + park_pts + streak_pts + rest_pts
    ))

    # Overall BvP edge (0-100)
    overall = min(100, max(0, int(power_score * 0.40 + matchup_score * 0.60)))

    scores = {
        "power_score":    power_score,
        "matchup_score":  matchup_score,
        "overall":        overall,
        "color":          _score_color(overall),
        "power_color":    _score_color(power_score),
        "matchup_color":  _score_color(matchup_score),
    }

    payload = {
        "batter":        batter_info,
        "pitcher":       pitcher_info,
        "platoon_adv":   platoon_adv,
        "platoon_label": platoon_label,
        "career_bvp":    career_bvp,
        "statcast":      statcast_block,
        "pitch_matchup": pitch_matchup[:6],
        "recent_form":   recent_form,
        "scores":        scores,
        "slot_label":    slot_label,
        "slot_ops":      slot_split.get("ops") if slot_split else None,
        # New: Park Factor, L7/L14 Trend, Pitcher Rest
        "park_factor":   park_factor,
        "l7_trend":      l7_trend,
        # FanGraphs
        "fg_batter": {
            "wrc_plus": fg_batter_data.get("wrc_plus"),
            "war": fg_batter_data.get("war"),
            "babip": fg_batter_data.get("babip"),
        },
        "fg_pitcher": {
            "era_minus": fg_pitcher_data.get("era_minus"),
            "fip": fg_pitcher_data.get("fip"),
            "xfip": fg_pitcher_data.get("xfip"),
            "siera": fg_pitcher_data.get("siera"),
            "k_bb_pct": fg_pitcher_data.get("k_bb_pct"),
            "lob_pct": fg_pitcher_data.get("lob_pct"),
            "gb_pct": fg_pitcher_data.get("gb_pct"),
        },
        "batter_splits": {
            "home":   b_splits.get("home", {}),
            "away":   b_splits.get("away", {}),
            "last_7": b_splits.get("last_7", {}),
            "last_14": b_splits.get("last_14", {}),
            "last_30": b_splits.get("last_30", {}),
            "vs_rhp": b_splits.get("vs_rhp", {}),
            "vs_lhp": b_splits.get("vs_lhp", {}),
        },
        "pitcher_splits": {
            "home":   p_splits.get("home", {}),
            "away":   p_splits.get("away", {}),
            "vs_lhb": p_splits.get("vs_lhb", {}),
            "vs_rhb": p_splits.get("vs_rhb", {}),
        },
        "pitcher_recent": pitcher_recent,
        "zone_stats":     zone_stats,
    }

    await set_cache(cache_key, payload, 600)  # 10 min cache
    return payload


@router.get("/game/{game_pk}/predictions")
async def get_game_predictions(game_pk: int):
    # Try to find game in schedule for today (or surrounding days)
    from datetime import date, timedelta
    found_game = None
    for offset in [0, -1, 1, -2, 2]:
        dt = (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")
        try:
            games = await mlb_api.get_schedule(dt)
            g = next((x for x in games if x.get("gamePk") == game_pk), None)
            if g:
                found_game = g
                break
        except Exception:
            pass

    away_pitcher_name = "Away Pitcher"
    home_pitcher_name = "Home Pitcher"

    if found_game:
        away_pp = found_game.get("teams", {}).get("away", {}).get("probablePitcher", {})
        home_pp = found_game.get("teams", {}).get("home", {}).get("probablePitcher", {})
        away_pitcher_id = away_pp.get("id") if away_pp else None
        home_pitcher_id = home_pp.get("id") if home_pp else None
        
        if away_pp:
            away_pitcher_name = away_pp.get("fullName", "Away Pitcher")
        if home_pp:
            home_pitcher_name = home_pp.get("fullName", "Home Pitcher")
    else:
        try:
            detail = await mlb_api.get_game_detail(game_pk)
            game_data = detail.get("gameData", {})
            away_pitcher_id = game_data.get("probablePitchers", {}).get("away", {}).get("id")
            home_pitcher_id = game_data.get("probablePitchers", {}).get("home", {}).get("id")
        except Exception:
            away_pitcher_id = None
            home_pitcher_id = None

    try:
        lineup = await mlb_api.get_lineup(game_pk)
    except Exception:
        return {"predictions": [], "away_lineup_splits": None, "home_lineup_splits": None}

    away_batters = lineup.get("away", {}).get("batters", [])[:9]
    home_batters = lineup.get("home", {}).get("batters", [])[:9]

    # Fallback pitcher IDs and names from lineup if TBD
    if not away_pitcher_id and lineup.get("away", {}).get("pitchers"):
        away_pitcher_id = lineup["away"]["pitchers"][0].get("person", {}).get("id")
        away_pitcher_name = lineup["away"]["pitchers"][0].get("person", {}).get("fullName", "Away Pitcher")
    if not home_pitcher_id and lineup.get("home", {}).get("pitchers"):
        home_pitcher_id = lineup["home"]["pitchers"][0].get("person", {}).get("id")
        home_pitcher_name = lineup["home"]["pitchers"][0].get("person", {}).get("fullName", "Home Pitcher")

    predictions = []

    async def get_batter_score(batter_raw: dict, opp_pitcher_id: int, array_index: int):
        person = batter_raw.get("person", {})
        bid = person.get("id")
        if not bid or not opp_pitcher_id:
            return
        order = int(batter_raw.get("battingOrder", 0) or 0) // 100 or (array_index + 1)
        try:
            res = await get_bvp_player(bid, opp_pitcher_id, order=order)
            if isinstance(res, dict) and "scores" in res:
                predictions.append({
                    "batter_id": bid,
                    "score": res["scores"]["overall"]
                })
        except Exception:
            pass

    tasks = []
    for idx, b in enumerate(away_batters):
        if home_pitcher_id:
            tasks.append(get_batter_score(b, home_pitcher_id, idx))
    for idx, b in enumerate(home_batters):
        if away_pitcher_id:
            tasks.append(get_batter_score(b, away_pitcher_id, idx))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    # Fetch and format pitcher splits vs lineup slots
    from services.splits import get_pitcher_splits
    away_splits_raw = await get_pitcher_splits(away_pitcher_id) if away_pitcher_id else {}
    home_splits_raw = await get_pitcher_splits(home_pitcher_id) if home_pitcher_id else {}

    def _format_pitcher_slot_splits(splits_raw: dict, pitcher_name: str):
        if not splits_raw or not isinstance(splits_raw, dict):
            return None
        order_splits = splits_raw.get("order_splits", {})
        slots_data = {}
        
        valid_slots = []
        for slot_str in map(str, range(1, 10)):
            slot_data = order_splits.get(slot_str, {})
            ops_val = _safe(slot_data.get("ops"), 0.000)
            hr_val = int(slot_data.get("hr", 0) or 0)
            
            slots_data[slot_str] = {
                "ops": f"{ops_val:.3f}" if slot_data.get("ops") not in (None, "", ".---") else "0.000",
                "hr": hr_val
            }
            
            if slot_data.get("pa", 0) > 0:
                valid_slots.append((int(slot_str), ops_val))
                
        # Find top 3 weakest slots (highest OPS allowed)
        valid_slots.sort(key=lambda x: -x[1])
        weak_slots = [slot for slot, _ in valid_slots[:3]]
        
        return {
            "name": pitcher_name,
            "weak_slots": weak_slots,
            "slots": slots_data
        }

    away_lineup_splits = _format_pitcher_slot_splits(home_splits_raw, home_pitcher_name)
    home_lineup_splits = _format_pitcher_slot_splits(away_splits_raw, away_pitcher_name)

    return {
        "predictions": predictions,
        "away_lineup_splits": away_lineup_splits,
        "home_lineup_splits": home_lineup_splits
    }

