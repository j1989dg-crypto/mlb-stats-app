"""
Baseball Savant / Statcast service
Fetches advanced metrics directly from the Savant CSV endpoint
"""
import io
import csv
import asyncio
import httpx
from datetime import datetime
from collections import defaultdict
from db.cache import get_cache, set_cache
from services.http_client import get_client

SAVANT_BASE = "https://baseballsavant.mlb.com"
SEASON = datetime.now().year

PITCH_NAMES = {
    "FF": "4-Seam Fastball", "SI": "Sinker",    "FC": "Cutter",
    "SL": "Slider",          "ST": "Sweeper",    "CU": "Curveball",
    "CH": "Changeup",        "FS": "Splitter",   "KC": "Knuckle-Curve",
    "SV": "Slurve",          "KN": "Knuckleball","SC": "Screwball",
    "EP": "Eephus",          "FO": "Forkball",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _parse_savant_csv(raw_bytes: bytes) -> list[dict]:
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        clean = {k.strip().strip('"'): v.strip().strip('"') for k, v in row.items()}
        rows.append(clean)
    return rows


def _safe_float(val, default=None):
    try:
        return float(val) if val and val not in ("", "null", ".") else default
    except (ValueError, TypeError):
        return default


# ── Barrel definition ────────────────────────────────────────────────────────

def _is_barrel(launch_speed: float, launch_angle: float) -> bool:
    if launch_speed < 98:
        return False
    if launch_speed < 99:  return 26 <= launch_angle <= 30
    if launch_speed < 100: return 25 <= launch_angle <= 31
    if launch_speed < 101: return 24 <= launch_angle <= 33
    if launch_speed < 102: return 23 <= launch_angle <= 35
    if launch_speed < 103: return 22 <= launch_angle <= 37
    if launch_speed < 104: return 21 <= launch_angle <= 39
    if launch_speed < 105: return 20 <= launch_angle <= 41
    if launch_speed < 106: return 19 <= launch_angle <= 43
    if launch_speed < 107: return 18 <= launch_angle <= 45
    if launch_speed < 108: return 17 <= launch_angle <= 47
    return 16 <= launch_angle <= 50


_OUTSIDE_ZONE_DESC = {"ball", "blocked_ball"}
_SWING_DESC = {
    "swinging_strike", "swinging_strike_blocked", "foul_tip",
    "foul", "foul_bunt", "hit_into_play", "hit_into_play_no_out",
    "hit_into_play_score",
}
_WHIFF_DESC = {"swinging_strike", "swinging_strike_blocked", "foul_tip"}


def _pitch_verdict(whiff_pct: float, avg_ev: float | None) -> str:
    """Classify how a batter handles a pitch type."""
    ev = avg_ev or 85
    if whiff_pct >= 45:
        return "WEAK"
    if whiff_pct >= 30:
        return "STRUGGLES"
    if ev >= 94 and whiff_pct < 20:
        return "CRUSHES"
    if ev >= 90 and whiff_pct < 25:
        return "HANDLES WELL"
    return "NEUTRAL"


# ── Pitcher Arsenal (overall) ────────────────────────────────────────────────

async def get_pitcher_arsenal(pitcher_id: int, refresh: bool = False) -> dict:
    """Pitch mix, whiff rates, avg spin/velo for each pitch type"""
    cache_key = f"statcast:pitcher_arsenal:{pitcher_id}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    url = f"{SAVANT_BASE}/statcast_search/csv"
    params = {
        "all": "true",
        "player_type": "pitcher",
        "pitchers_lookup[]": pitcher_id,
        "hfSea": f"{SEASON}|",
        "type": "details",
        "min_pitches": 1,
    }

    try:
        client = get_client()
        r = await client.get(url, params=params, headers=HEADERS, timeout=25)
        if r.status_code != 200:
                return {"pitcher_id": pitcher_id, "error": f"HTTP {r.status_code}", "arsenal": []}

        rows = _parse_savant_csv(r.content)
        if not rows:
            return {"pitcher_id": pitcher_id, "arsenal": [], "total_pitches_sampled": 0}

        pitch_groups = defaultdict(list)
        for row in rows:
            pt = row.get("pitch_type", "")
            if pt and pt not in ("", "null", "UN"):
                pitch_groups[pt].append(row)

        total_pitches = sum(len(v) for v in pitch_groups.values())

        arsenal = []
        for pt, pitches in sorted(pitch_groups.items(), key=lambda x: -len(x[1])):
            n = len(pitches)
            desc = [p.get("description", "") for p in pitches]
            whiffs = sum(1 for d in desc if d in _WHIFF_DESC)
            swings = sum(1 for d in desc if d in _SWING_DESC)

            spin_rates = [_safe_float(p.get("release_spin_rate")) for p in pitches]
            spin_rates = [v for v in spin_rates if v and v > 0]
            velocities = [_safe_float(p.get("release_speed")) for p in pitches]
            velocities = [v for v in velocities if v and v > 0]
            xba_vals = [_safe_float(p.get("estimated_ba_using_speedangle")) for p in pitches]
            xba_vals = [v for v in xba_vals if v is not None]

            # Chase % (swings on balls outside zone)
            outside = [p for p in pitches if p.get("description", "") in _SWING_DESC and p.get("zone", "0") in ("11","12","13","14")]
            chase_pct = round(len(outside) / max(1, sum(1 for p in pitches if p.get("description","") not in _OUTSIDE_ZONE_DESC)) * 100, 1)

            arsenal.append({
                "pitch_type": pt,
                "pitch_name": PITCH_NAMES.get(pt, pt),
                "count": n,
                "usage_pct": round(n / total_pitches * 100, 1) if total_pitches else 0,
                "whiff_pct": round(whiffs / swings * 100, 1) if swings else 0,
                "chase_pct": chase_pct,
                "avg_spin": round(sum(spin_rates) / len(spin_rates)) if spin_rates else None,
                "avg_velo": round(sum(velocities) / len(velocities), 1) if velocities else None,
                "avg_xba": round(sum(xba_vals) / len(xba_vals), 3) if xba_vals else None,
            })

        result = {
            "pitcher_id": pitcher_id,
            "total_pitches_sampled": total_pitches,
            "arsenal": arsenal,
            "primary_pitch": arsenal[0]["pitch_name"] if arsenal else "Unknown",
        }
        await set_cache(cache_key, result, 3600 * 6)
        return result

    except Exception as e:
        return {"pitcher_id": pitcher_id, "error": str(e), "arsenal": []}


# ── Pitcher Arsenal by Batter Stance (LHB vs RHB) ───────────────────────────

async def get_pitcher_arsenal_by_stance(pitcher_id: int) -> dict:
    """
    Same Statcast data but split by batter stand (L vs R).
    Shows how usage/whiff rates differ vs lefties vs righties per pitch type.
    """
    cache_key = f"statcast:arsenal_by_stance:{pitcher_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    url = f"{SAVANT_BASE}/statcast_search/csv"
    params = {
        "all": "true",
        "player_type": "pitcher",
        "pitchers_lookup[]": pitcher_id,
        "hfSea": f"{SEASON}|",
        "type": "details",
        "min_pitches": 1,
    }

    try:
        client = get_client()
        r = await client.get(url, params=params, headers=HEADERS, timeout=25)
        if r.status_code != 200:
                return {"pitcher_id": pitcher_id, "error": f"HTTP {r.status_code}", "vs_lhb": [], "vs_rhb": []}

        rows = _parse_savant_csv(r.content)
        if not rows:
            return {"pitcher_id": pitcher_id, "vs_lhb": [], "vs_rhb": []}

        def _build_stance_arsenal(stance_rows: list) -> list:
            pitch_groups = defaultdict(list)
            for row in stance_rows:
                pt = row.get("pitch_type", "")
                if pt and pt not in ("", "null", "UN"):
                    pitch_groups[pt].append(row)
            total = sum(len(v) for v in pitch_groups.values())
            result = []
            for pt, pitches in sorted(pitch_groups.items(), key=lambda x: -len(x[1])):
                n = len(pitches)
                desc = [p.get("description", "") for p in pitches]
                whiffs = sum(1 for d in desc if d in _WHIFF_DESC)
                swings = sum(1 for d in desc if d in _SWING_DESC)
                velos = [_safe_float(p.get("release_speed")) for p in pitches]
                velos = [v for v in velos if v]
                result.append({
                    "pitch_type": pt,
                    "pitch_name": PITCH_NAMES.get(pt, pt),
                    "count": n,
                    "usage_pct": round(n / total * 100, 1) if total else 0,
                    "whiff_pct": round(whiffs / swings * 100, 1) if swings else 0,
                    "avg_velo": round(sum(velos) / len(velos), 1) if velos else None,
                })
            return result

        lhb_rows = [r for r in rows if r.get("stand", "") == "L"]
        rhb_rows = [r for r in rows if r.get("stand", "") == "R"]

        result = {
            "pitcher_id": pitcher_id,
            "vs_lhb": _build_stance_arsenal(lhb_rows),
            "vs_rhb": _build_stance_arsenal(rhb_rows),
            "lhb_pa": len(set(r.get("at_bat_number","") for r in lhb_rows)),
            "rhb_pa": len(set(r.get("at_bat_number","") for r in rhb_rows)),
        }
        await set_cache(cache_key, result, 3600 * 6)
        return result

    except Exception as e:
        return {"pitcher_id": pitcher_id, "error": str(e), "vs_lhb": [], "vs_rhb": []}


# ── Batter Season Statcast ───────────────────────────────────────────────────

async def get_batter_statcast(batter_id: int, refresh: bool = False) -> dict:
    """Exit velocity, barrel rate, xBA, xSLG, hard-hit rate, K%, BB%, ISO proxy"""
    cache_key = f"statcast:batter:{batter_id}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    url = f"{SAVANT_BASE}/statcast_search/csv"
    params = {
        "all": "true",
        "player_type": "batter",
        "batters_lookup[]": batter_id,
        "hfSea": f"{SEASON}|",
        "type": "details",
        "min_pitches": 1,
    }

    try:
        client = get_client()
        r = await client.get(url, params=params, headers=HEADERS, timeout=25)
        if r.status_code != 200:
                return {"batter_id": batter_id, "error": f"HTTP {r.status_code}"}

        rows = _parse_savant_csv(r.content)
        if not rows:
            return {"batter_id": batter_id, "batted_balls": 0}

        # Batted balls
        bip = [row for row in rows if _safe_float(row.get("launch_speed")) is not None]
        exit_velos = [_safe_float(row["launch_speed"]) for row in bip if _safe_float(row["launch_speed"])]
        barrels = [
            row for row in bip
            if _is_barrel(
                _safe_float(row.get("launch_speed"), 0),
                _safe_float(row.get("launch_angle"), -999),
            )
        ]
        hard_hit = [row for row in bip if (_safe_float(row.get("launch_speed")) or 0) >= 95]

        # Sweet spot: launch angle 8–32 degrees (ideal HR/XBH trajectory)
        sweet_spot = [
            row for row in bip
            if 8 <= (_safe_float(row.get("launch_angle")) or -999) <= 32
        ]

        xba_vals = [_safe_float(r.get("estimated_ba_using_speedangle")) for r in rows]
        xba_vals = [v for v in xba_vals if v is not None]
        xslg_vals = [_safe_float(r.get("estimated_slg_using_speedangle")) for r in rows]
        xslg_vals = [v for v in xslg_vals if v is not None]

        desc_list = [r.get("description", "") for r in rows]
        swings = [d for d in desc_list if d in _SWING_DESC]
        whiffs = [d for d in desc_list if d in _WHIFF_DESC]

        # Count PA-level events for K%, BB%, HR rate
        events = [r.get("events", "") for r in rows if r.get("events", "")]
        total_pa = len(set(
            (r.get("game_pk",""), r.get("at_bat_number",""))
            for r in rows if r.get("at_bat_number","")
        )) or max(1, len(rows) // 4)

        k_count = sum(1 for e in events if e in ("strikeout", "strikeout_double_play"))
        bb_count = sum(1 for e in events if e in ("walk", "intent_walk"))
        hr_count = sum(1 for e in events if e == "home_run")

        xba_avg = round(sum(xba_vals) / len(xba_vals), 3) if xba_vals else None
        xslg_avg = round(sum(xslg_vals) / len(xslg_vals), 3) if xslg_vals else None
        iso = round(xslg_avg - xba_avg, 3) if xba_avg and xslg_avg else None

        # Swing discipline computed from pitch-level data
        # Chase % = swings on pitches in outer zones (11-14 = outside strike zone)
        outside_pitches = [r for r in rows if r.get("zone", "0") in ("11","12","13","14")]
        outside_swings  = sum(1 for r in outside_pitches if r.get("description","") in _SWING_DESC)
        chase_pct = round(outside_swings / max(1, len(outside_pitches)) * 100, 1) if outside_pitches else 30.0

        # Z-Contact % = contact made on pitches inside zone (1-9)
        in_zone = [r for r in rows if r.get("zone", "0") in ("1","2","3","4","5","6","7","8","9")]
        in_zone_swings  = [r for r in in_zone if r.get("description","") in _SWING_DESC]
        in_zone_contact = [r for r in in_zone_swings if r.get("description","") not in _WHIFF_DESC]
        z_contact_pct = round(len(in_zone_contact) / max(1, len(in_zone_swings)) * 100, 1) if in_zone_swings else 85.0

        result = {
            "batter_id": batter_id,
            "pa_sampled": total_pa,
            "batted_balls": len(bip),
            "avg_exit_velo": round(sum(exit_velos) / len(exit_velos), 1) if exit_velos else None,
            "max_exit_velo": round(max(exit_velos), 1) if exit_velos else None,
            "barrel_rate": round(len(barrels) / len(bip) * 100, 1) if bip else 0,
            "hard_hit_rate": round(len(hard_hit) / len(bip) * 100, 1) if bip else 0,
            "sweet_spot_rate": round(len(sweet_spot) / len(bip) * 100, 1) if bip else 0,
            "xba": xba_avg,
            "xslg": xslg_avg,
            "iso": iso,
            "whiff_rate": round(len(whiffs) / len(swings) * 100, 1) if swings else 0,
            "k_rate": round(k_count / total_pa * 100, 1) if total_pa else 0,
            "bb_rate": round(bb_count / total_pa * 100, 1) if total_pa else 0,
            "hr_count": hr_count,
            # Discipline metrics computed from raw pitch data
            "chase_pct":     chase_pct,
            "z_contact_pct": z_contact_pct,
        }
        await set_cache(cache_key, result, 3600 * 6)
        return result

    except Exception as e:
        return {"batter_id": batter_id, "error": str(e)}


# ── Batter Savant Leaderboard (xwOBA, chase%, z-contact%) ───────────────────

async def get_batter_savant_leaderboard(batter_id: int, refresh: bool = False) -> dict:
    """
    Fetch advanced batter discipline metrics from Baseball Savant's leaderboard.
    Returns: xwoba, woba, chase_pct (o_swing_percent), z_contact_pct,
             xba, xslg (season-level expected stats from leaderboard).
    Falls back gracefully — never raises.
    """
    cache_key = f"statcast:leaderboard:{batter_id}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    url = f"{SAVANT_BASE}/leaderboard/expected_statistics"
    params = {
        "type": "batter",
        "year": SEASON,
        "position": "",
        "team": "",
        "min": "1",
        "csv": "true",
    }

    try:
        client = get_client()
        r = await client.get(url, params=params, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return {"batter_id": batter_id, "error": f"HTTP {r.status_code}"}

        rows = _parse_savant_csv(r.content)
        # Find this batter in the leaderboard
        player_row = None
        for row in rows:
            try:
                rid = int(row.get("player_id", 0) or 0)
                if rid == batter_id:
                    player_row = row
                    break
            except (ValueError, TypeError):
                continue

        if not player_row:
            # Try with min=1 PA (unqualified) if not found in qualified list
            params2 = {**params, "min": "1"}
            r2 = await client.get(url, params=params2, headers=HEADERS, timeout=25)
            if r2.status_code == 200:
                rows2 = _parse_savant_csv(r2.content)
                for row in rows2:
                    try:
                        if int(row.get("player_id", 0) or 0) == batter_id:
                            player_row = row
                            break
                    except (ValueError, TypeError):
                        continue

        if not player_row:
            return {"batter_id": batter_id, "error": "Not found in leaderboard"}

        result = {
            "batter_id":     batter_id,
            "xwoba":         _safe_float(player_row.get("est_woba")),
            "xba":           _safe_float(player_row.get("est_ba")),
            "xslg":          _safe_float(player_row.get("est_slg")),
            "woba":          _safe_float(player_row.get("woba")),
            "pa":            _safe_float(player_row.get("pa")),
            "abs_number":    _safe_float(player_row.get("ab")),
        }

        await set_cache(cache_key, result, 3600 * 6)
        return result

    except Exception as e:
        return {"batter_id": batter_id, "error": str(e)}


# ── Batter Swing Discipline (chase%, z-contact%) ─────────────────────────────

async def get_batter_discipline(batter_id: int, refresh: bool = False) -> dict:
    """
    Fetch swing discipline metrics from Baseball Savant's plate discipline leaderboard.
    Returns: o_swing_pct (chase%), z_contact_pct, swstr_pct (whiff%).
    Falls back gracefully.
    """
    cache_key = f"statcast:discipline:{batter_id}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    url = f"{SAVANT_BASE}/leaders/plate-discipline"
    params = {
        "type": "details",
        "year": SEASON,
        "team": "",
        "min": "1",
        "csv": "true",
    }

    try:
        client = get_client()
        r = await client.get(url, params=params, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return {"batter_id": batter_id, "error": f"HTTP {r.status_code}"}

        rows = _parse_savant_csv(r.content)
        player_row = None
        for row in rows:
            try:
                if int(row.get("player_id", 0) or 0) == batter_id:
                    player_row = row
                    break
            except (ValueError, TypeError):
                continue

        if not player_row:
            return {"batter_id": batter_id, "error": "Not in discipline leaderboard"}

        # o_swing_percent = chase%, z_contact_percent = zone contact%
        chase  = _safe_float(player_row.get("o_swing_percent"))
        zcon   = _safe_float(player_row.get("z_contact_percent"))
        swstr  = _safe_float(player_row.get("swstr_percent"))

        # Savant returns these as decimals (0.32) — convert to pct (32.0)
        def to_pct(v):
            if v is None:
                return None
            return round(v * 100, 1) if v < 1.0 else round(v, 1)

        result = {
            "batter_id":    batter_id,
            "chase_pct":    to_pct(chase),
            "z_contact_pct": to_pct(zcon),
            "swstr_pct":    to_pct(swstr),
        }
        await set_cache(cache_key, result, 3600 * 6)
        return result

    except Exception as e:
        return {"batter_id": batter_id, "error": str(e)}


# ── BvP Statcast (specific batter vs specific pitcher) ───────────────────────

async def get_bvp_statcast(batter_id: int, pitcher_id: int, refresh: bool = False) -> dict:
    """
    Pitch-level data for a specific batter vs pitcher pairing.
    Extended: adds avg_exit_velo, hr_count, chase_pct per pitch type.
    """
    cache_key = f"statcast:bvp:{batter_id}:{pitcher_id}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    url = f"{SAVANT_BASE}/statcast_search/csv"
    params = {
        "all": "true",
        "player_type": "batter",
        "batters_lookup[]": batter_id,
        "pitchers_lookup[]": pitcher_id,
        "hfSea": f"{SEASON}|2024|2023|",
        "type": "details",
    }

    try:
        client = get_client()
        r = await client.get(url, params=params, headers=HEADERS, timeout=25)

        rows = _parse_savant_csv(r.content)
        if not rows:
            return {"batter_id": batter_id, "pitcher_id": pitcher_id, "pa": 0, "pitch_breakdown": []}

        pitch_groups = defaultdict(list)
        for row in rows:
            pt = row.get("pitch_type", "")
            if pt and pt not in ("", "null", "UN"):
                pitch_groups[pt].append(row)

        total_pitches = len(rows)

        # Overall plate-level stats
        events = [r.get("events", "") for r in rows if r.get("events", "")]
        total_pa = len(set(
            (r.get("game_pk",""), r.get("at_bat_number",""))
            for r in rows if r.get("at_bat_number","")
        )) or 0
        hr_total = sum(1 for e in events if e == "home_run")
        k_total  = sum(1 for e in events if e in ("strikeout", "strikeout_double_play"))
        bb_total = sum(1 for e in events if e in ("walk", "intent_walk"))

        breakdown = []
        for pt, pitches in sorted(pitch_groups.items(), key=lambda x: -len(x[1])):
            n = len(pitches)
            desc = [p.get("description", "") for p in pitches]
            swings = [d for d in desc if d in _SWING_DESC]
            whiffs = [d for d in desc if d in _WHIFF_DESC]

            hits = [p for p in pitches if p.get("events", "") in ("single","double","triple","home_run")]
            hr_on_pitch = sum(1 for p in pitches if p.get("events","") == "home_run")

            xba_vals = [_safe_float(p.get("estimated_ba_using_speedangle")) for p in pitches]
            xba_vals = [v for v in xba_vals if v is not None]

            # Exit velocity on balls in play vs this pitch type
            bip = [p for p in pitches if _safe_float(p.get("launch_speed")) is not None]
            evs = [_safe_float(p.get("launch_speed")) for p in bip if _safe_float(p.get("launch_speed"))]
            avg_ev = round(sum(evs) / len(evs), 1) if evs else None

            # Chase % — swings on pitches in zone 11-14 (outside)
            outside_swings = sum(
                1 for p in pitches
                if p.get("description","") in _SWING_DESC
                and p.get("zone","0") in ("11","12","13","14")
            )
            non_ball = sum(1 for p in pitches if p.get("description","") not in _OUTSIDE_ZONE_DESC)
            chase_pct = round(outside_swings / max(1, non_ball) * 100, 1)

            whiff_pct = round(len(whiffs) / len(swings) * 100, 1) if swings else 0
            verdict = _pitch_verdict(whiff_pct, avg_ev)

            breakdown.append({
                "pitch_type": pt,
                "pitch_name": PITCH_NAMES.get(pt, pt),
                "seen": n,
                "usage_pct": round(n / total_pitches * 100, 1) if total_pitches else 0,
                "whiff_pct": whiff_pct,
                "chase_pct": chase_pct,
                "hits": len(hits),
                "hr_count": hr_on_pitch,
                "avg_exit_velo": avg_ev,
                "xba": round(sum(xba_vals) / len(xba_vals), 3) if xba_vals else None,
                "verdict": verdict,
            })

        # Determine key vulnerability / strength
        pitched_enough = [b for b in breakdown if b["seen"] >= 5]
        key_weakness = None
        key_strength = None
        if pitched_enough:
            weakest = max(pitched_enough, key=lambda b: b["whiff_pct"])
            strongest = min(pitched_enough, key=lambda b: b["whiff_pct"])
            if weakest["whiff_pct"] >= 30:
                key_weakness = f"Weak vs {weakest['pitch_name']} ({weakest['whiff_pct']}% whiff)"
            ev_best = max(pitched_enough, key=lambda b: b.get("avg_exit_velo") or 0)
            if (ev_best.get("avg_exit_velo") or 0) >= 90 and ev_best["whiff_pct"] < 25:
                key_strength = f"Crushes {ev_best['pitch_name']} ({ev_best.get('avg_exit_velo')} mph avg EV)"

        # Clean rows to only include fields needed by frontend/router
        bvp_rows_clean = []
        for r in rows:
            bvp_rows_clean.append({
                "pitch_type": r.get("pitch_type"),
                "launch_speed": r.get("launch_speed"),
                "description": r.get("description"),
                "hit_location": r.get("hit_location"),
                "events": r.get("events"),
                "zone": r.get("zone"),
            })

        result = {
            "batter_id": batter_id,
            "pitcher_id": pitcher_id,
            "total_pitches": total_pitches,
            "total_pa": total_pa,
            "hr_total": hr_total,
            "k_total": k_total,
            "bb_total": bb_total,
            "pitch_breakdown": breakdown,
            "bvp_rows": bvp_rows_clean,
            "key_weakness": key_weakness,
            "key_strength": key_strength,
        }
        await set_cache(cache_key, result, 3600 * 12)
        return result

    except Exception as e:
        return {"batter_id": batter_id, "pitcher_id": pitcher_id, "error": str(e), "pitch_breakdown": []}
