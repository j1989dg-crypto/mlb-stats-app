"""Check barrel column values in Savant CSV"""
import sys, asyncio
sys.path.insert(0, "D:/mlb-stats-app/site-packages")
sys.path.insert(0, "D:/mlb-stats-app/backend")
import httpx
from services.statcast import _parse_savant_csv, SAVANT_BASE, HEADERS

async def check():
    url = f"{SAVANT_BASE}/statcast_search/csv"
    params = {"all":"true","player_type":"batter","batters_lookup[]":592450,"hfSea":"2025|","type":"details","min_pitches":1}
    async with httpx.AsyncClient(timeout=25, headers=HEADERS) as c:
        r = await c.get(url, params=params)
    rows = _parse_savant_csv(r.content)
    barrel_vals = set(row.get("barrel","?") for row in rows[:300])
    print("Barrel column values seen:", barrel_vals)
    # show bip rows
    bip = [row for row in rows if row.get("launch_speed","") not in ("","null")][:3]
    for row in bip:
        ls = row.get("launch_speed")
        brl = row.get("barrel")
        la = row.get("launch_angle")
        ev = row.get("events","")
        print(f"  ls={ls} la={la} barrel={repr(brl)} event={ev}")

asyncio.run(check())
