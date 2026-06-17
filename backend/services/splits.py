"""
MLB splits service — platoon, home/away, last N game splits
Uses the MLB Stats API expanded stats endpoints
"""
import asyncio
from datetime import datetime, timedelta
import httpx
from db.cache import get_cache, set_cache
from services.http_client import get_client

MLB_BASE = "https://statsapi.mlb.com/api/v1"


def _pct(num, denom, decimals=1):
    try:
        return round(float(num) / float(denom) * 100, decimals) if float(denom) > 0 else 0.0
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _safe_float(val, default=0.0):
    try:
        return float(val) if val not in (None, "", ".", ".---", "-.--") else default
    except (ValueError, TypeError):
        return default


def _enrich_split(stat: dict) -> dict:
    """Take raw MLB API stat dict and compute derived metrics."""
    pa  = int(stat.get("plateAppearances", 0) or 0)
    ab  = int(stat.get("atBats", 0) or 0)
    so  = int(stat.get("strikeOuts", 0) or 0)
    bb  = int(stat.get("baseOnBalls", 0) or 0)
    hr  = int(stat.get("homeRuns", 0) or 0)
    h   = int(stat.get("hits", 0) or 0)
    sf  = int(stat.get("sacFlies", 0) or 0)
    hbp = int(stat.get("hitByPitch", 0) or 0)

    avg  = stat.get("avg", ".---")
    ops  = stat.get("ops", ".---")
    obp  = stat.get("obp", ".---")
    slg  = stat.get("slg", ".---")

    # Computed rates
    bb_pct = _pct(bb, pa)
    k_pct  = _pct(so, pa)
    hr_rate = _pct(hr, ab)

    # BABIP = (H - HR) / (AB - K - HR + SF)
    babip_denom = ab - so - hr + sf
    babip = round((h - hr) / babip_denom, 3) if babip_denom > 0 else None

    # ISO = SLG - AVG
    try:
        iso = round(float(slg) - float(avg), 3) if slg != ".---" and avg != ".---" else None
    except (ValueError, TypeError):
        iso = None

    return {
        "avg": avg, "ops": ops, "obp": obp, "slg": slg,
        "hr": hr, "ab": ab, "hits": h, "pa": pa,
        "so": so, "bb": bb,
        "bb_pct": bb_pct,
        "k_pct": k_pct,
        "hr_rate": hr_rate,
        "babip": babip,
        "iso": iso,
    }


async def get_batter_splits(player_id: int, season: int = None, refresh: bool = False) -> dict:
    """
    Fetch batter splits:
      - vs LHP / vs RHP
      - Home / Away
      - Last 7 / Last 30 days
    All splits now include BB%, K%, HR rate, ISO, BABIP.
    """
    if not season:
        season = datetime.now().year
    cache_key = f"splits:batter:{player_id}:{season}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    # We will do a single concurrent fetch list.
    # The first 4 are using statSplits, the last 2 are using byDateRange
    today_dt = datetime.now()
    start_30 = (today_dt - timedelta(days=30)).strftime("%Y-%m-%d")
    end_30 = today_dt.strftime("%Y-%m-%d")
    start_14 = (today_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    end_14 = today_dt.strftime("%Y-%m-%d")
    start_7 = (today_dt - timedelta(days=7)).strftime("%Y-%m-%d")
    end_7 = today_dt.strftime("%Y-%m-%d")

    SPLITS_CFG = [
        # (key, stats_type, params)
        ("vs_lhp", "statSplits", {"season": season, "sitCodes": "vl"}),
        ("vs_rhp", "statSplits", {"season": season, "sitCodes": "vr"}),
        ("home", "statSplits", {"season": season, "sitCodes": "h"}),
        ("away", "statSplits", {"season": season, "sitCodes": "a"}),
        ("last_7",  "byDateRange", {"startDate": start_7,  "endDate": end_7}),
        ("last_14", "byDateRange", {"startDate": start_14, "endDate": end_14}),
        ("last_30", "byDateRange", {"startDate": start_30, "endDate": end_30}),
    ]

    result = {"player_id": player_id}
    try:
        client = get_client()
        tasks = [
            client.get(
                f"{MLB_BASE}/people/{player_id}/stats",
                params={
                    "stats": stats_type,
                    "group": "hitting",
                    **params
                }
            )
            for _, stats_type, params in SPLITS_CFG
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for (key, _, _), resp in zip(SPLITS_CFG, responses):
            if isinstance(resp, Exception) or resp.status_code != 200:
                result[key] = {}
                continue
            data = resp.json()
            splits = data.get("stats", [{}])[0].get("splits", [])
            stat = splits[0].get("stat", {}) if splits else {}
            result[key] = _enrich_split(stat)

        # Platoon advantage summary
        vs_lhp_avg = _safe_float(result.get("vs_lhp", {}).get("avg", 0))
        vs_rhp_avg = _safe_float(result.get("vs_rhp", {}).get("avg", 0))
        result["platoon_split"] = round(vs_rhp_avg - vs_lhp_avg, 3)
        result["better_vs"] = "RHP" if vs_rhp_avg >= vs_lhp_avg else "LHP"

        await set_cache(cache_key, result, 3600)
        return result

    except Exception as e:
        return {"player_id": player_id, "error": str(e)}


async def get_pitcher_splits(player_id: int, season: int = None, refresh: bool = False) -> dict:
    """Pitcher splits: vs LHB, vs RHB, home, away, and batting order slots b1-b9"""
    if not season:
        season = datetime.now().year
    cache_key = f"splits:pitcher:{player_id}:{season}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached

    result = {
        "player_id": player_id,
        "vs_lhb": {}, "vs_rhb": {}, "home": {}, "away": {},
        "order_splits": {}
    }
    
    # Map sitCodes to output keys
    CODE_MAP = {
        "vl": "vs_lhb",
        "vr": "vs_rhb",
        "h": "home",
        "a": "away"
    }

    try:
        client = get_client()
        sit_codes = "vl,vr,h,a,b1,b2,b3,b4,b5,b6,b7,b8,b9"
        resp = await client.get(
            f"{MLB_BASE}/people/{player_id}/stats",
            params={
                "stats": "statSplits",
                "group": "pitching",
                "season": season,
                "sitCodes": sit_codes,
            }
        )
        if resp.status_code == 200:
            data = resp.json()
            splits = data.get("stats", [{}])[0].get("splits", [])
            for s in splits:
                split_code = s.get("split", {}).get("code")
                stat = s.get("stat", {})
                pa  = int(stat.get("battersFaced", 0) or 0)
                so  = int(stat.get("strikeOuts", 0) or 0)
                bb  = int(stat.get("baseOnBalls", 0) or 0)
                
                enriched = {
                    "era":   stat.get("era", "-.--"),
                    "whip":  stat.get("whip", "-.--"),
                    "avg":   stat.get("avg", ".---"),
                    "ops":   stat.get("ops", ".---"),
                    "so":    so,
                    "bb":    bb,
                    "ip":    stat.get("inningsPitched", "0.0"),
                    "pa":    pa,
                    "k_pct": _pct(so, pa),
                    "bb_pct": _pct(bb, pa),
                }
                
                if split_code in CODE_MAP:
                    result[CODE_MAP[split_code]] = enriched
                elif split_code and split_code.startswith("b") and len(split_code) == 2:
                    try:
                        slot_num = int(split_code[1])
                        result["order_splits"][str(slot_num)] = enriched
                    except ValueError:
                        pass
        
        await set_cache(cache_key, result, 3600)
        return result

    except Exception as e:
        return {"player_id": player_id, "error": str(e)}
