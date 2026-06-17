"""
FanGraphs scraper — advanced metrics not available from MLB Stats API
Scrapes public leaderboard pages (no API key needed)
"""
import asyncio
import httpx
from datetime import datetime
from db.cache import get_cache, set_cache
from services.http_client import get_client

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://www.fangraphs.com/",
}

FG_BASE = "https://www.fangraphs.com"
SEASON = datetime.now().year


def _safe(val, default=None):
    try:
        if val is None or val == "" or val == "-":
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


async def _resolve_fg_id(mlbam_id: int) -> str | None:
    """
    Resolve an MLBAM player ID to a FanGraphs player ID.
    Tries FanGraphs API first, falls back to Chadwick Bureau CSV.
    """
    cache_key = f"fangraphs:fg_id:{mlbam_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    # Try FanGraphs player search API first
    try:
        client = get_client()
        r = await client.get(
            f"{FG_BASE}/api/players",
            params={"mlbamid": mlbam_id},
            timeout=15,
            headers=HEADERS
        )
        if r.status_code == 200:
            data = r.json()
            players = data if isinstance(data, list) else data.get("players", [])
            if players:
                fg_id = str(players[0].get("playerid", "") or players[0].get("xMLBAMID", ""))
                if fg_id and fg_id not in ("0", ""):
                    await set_cache(cache_key, fg_id, 86400 * 7)
                    return fg_id
    except Exception:
        pass

    # Fallback: Chadwick Bureau CSV
    try:
        client = get_client()
        r = await client.get(
            "https://raw.githubusercontent.com/chadwickbureau/register/master/data/people.csv",
            timeout=20,
            headers=HEADERS
        )
        if r.status_code == 200:
            import io, csv
            reader = csv.DictReader(io.StringIO(r.text))
            for row in reader:
                if str(row.get("key_mlbam", "")) == str(mlbam_id):
                    fg_id = row.get("key_fangraphs", "")
                    if fg_id:
                        await set_cache(cache_key, fg_id, 86400 * 7)
                        return fg_id
    except Exception:
        pass

    return None


async def get_batter_fangraphs(player_id: int) -> dict:
    """
    Fetch advanced batter metrics from FanGraphs.
    Returns: wRC+, WAR, BB%, K%, BABIP, ISO, Hard%, Barrel%, Chase%, Whiff%, xwOBA
    Falls back gracefully — never raises, returns empty dict on failure.
    """
    cache_key = f"fangraphs:batter:{player_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    result = {"player_id": player_id, "source": "fangraphs"}

    try:
        fg_id = await _resolve_fg_id(player_id)
        if not fg_id:
            return {**result, "error": "FG ID not found"}

        client = get_client()
        r = await client.get(
            f"{FG_BASE}/api/leaders/major-league/data",
            params={
                "age": "", "pos": "all", "stats": "bat", "lg": "all",
                "qual": "0", "season": SEASON, "season1": SEASON,
                "ind": "0", "team": "0", "pageitems": "2000",
                "pagenum": "1", "sortdir": "default", "sortstat": "WAR",
                "playerid": fg_id,
            },
            timeout=20,
            headers=HEADERS
        )

        if r.status_code == 200:
            data = r.json()
            rows = data.get("data", [])
            if rows:
                row = rows[0]
                result.update({
                    "fg_id":          fg_id,
                    "wrc_plus":       _safe(row.get("wRC+")),
                    "war":            _safe(row.get("WAR")),
                    "bb_pct":         _safe(row.get("BB%")),
                    "k_pct":          _safe(row.get("K%")),
                    "babip":          _safe(row.get("BABIP")),
                    "iso":            _safe(row.get("ISO")),
                    "hard_pct":       _safe(row.get("Hard%")),
                    "barrel_pct":     _safe(row.get("Barrel%")),
                    "chase_pct":      _safe(row.get("O-Swing%")),
                    "z_contact_pct":  _safe(row.get("Z-Contact%")),
                    "whiff_pct":      _safe(row.get("SwStr%")),
                    "xwoba":          _safe(row.get("xwOBA")),
                    "obp":            _safe(row.get("OBP")),
                    "slg":            _safe(row.get("SLG")),
                    "avg":            _safe(row.get("AVG")),
                    "hr":             _safe(row.get("HR")),
                    "pa":             _safe(row.get("PA")),
                })

        await set_cache(cache_key, result, 3600 * 6)
        return result

    except Exception as e:
        return {**result, "error": str(e)}


async def get_pitcher_fangraphs(player_id: int) -> dict:
    """
    Fetch advanced pitcher metrics from FanGraphs.
    Returns: ERA-, FIP, xFIP, SIERA, WAR, K%, BB%, K-BB%, HR/9, GB%, Chase%, Whiff%
    Falls back gracefully — never raises, returns empty dict on failure.
    """
    cache_key = f"fangraphs:pitcher:{player_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    result = {"player_id": player_id, "source": "fangraphs"}

    try:
        fg_id = await _resolve_fg_id(player_id)
        if not fg_id:
            return {**result, "error": "FG ID not found"}

        client = get_client()
        r = await client.get(
            f"{FG_BASE}/api/leaders/major-league/data",
            params={
                "age": "", "pos": "all", "stats": "pit", "lg": "all",
                "qual": "0", "season": SEASON, "season1": SEASON,
                "ind": "0", "team": "0", "pageitems": "2000",
                "pagenum": "1", "sortdir": "default", "sortstat": "WAR",
                "playerid": fg_id,
            },
            timeout=20,
            headers=HEADERS
        )

        if r.status_code == 200:
            data = r.json()
            rows = data.get("data", [])
            if rows:
                row = rows[0]
                result.update({
                    "fg_id":      fg_id,
                    "era_minus":  _safe(row.get("ERA-")),
                    "fip":        _safe(row.get("FIP")),
                    "xfip":       _safe(row.get("xFIP")),
                    "siera":      _safe(row.get("SIERA")),
                    "war":        _safe(row.get("WAR")),
                    "k_pct":      _safe(row.get("K%")),
                    "bb_pct":     _safe(row.get("BB%")),
                    "k_bb_pct":   _safe(row.get("K-BB%")),
                    "hr9":        _safe(row.get("HR/9")),
                    "gb_pct":     _safe(row.get("GB%")),
                    "chase_pct":  _safe(row.get("O-Swing%")),
                    "whiff_pct":  _safe(row.get("SwStr%")),
                    "lob_pct":    _safe(row.get("LOB%")),
                    "era":        _safe(row.get("ERA")),
                    "ip":         _safe(row.get("IP")),
                })

        await set_cache(cache_key, result, 3600 * 6)
        return result

    except Exception as e:
        return {**result, "error": str(e)}
