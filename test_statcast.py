"""Quick standalone test for Statcast CSV parsing"""
import asyncio
import sys
import os

sys.path.insert(0, "D:/mlb-stats-app/site-packages")
sys.path.insert(0, "D:/mlb-stats-app/backend")

# Patch cache for standalone
import db.cache as cache_mod
async def fake_get(k): return None
async def fake_set(k, v, t=0): pass
cache_mod.get_cache = fake_get
cache_mod.set_cache = fake_set

async def test():
    from services.statcast import get_pitcher_arsenal, get_batter_statcast
    
    print("=== Pitcher Arsenal: Gerrit Cole (543243) ===")
    r = await get_pitcher_arsenal(543243)
    ar = r.get("arsenal", [])
    print(f"Total pitches sampled: {r.get('total_pitches_sampled', 0)}")
    print(f"Primary pitch: {r.get('primary_pitch')}")
    for p in ar[:6]:
        velo = f"{p['avg_velo']} mph" if p.get('avg_velo') else "N/A"
        spin = f"{p['avg_spin']} rpm" if p.get('avg_spin') else "N/A"
        print(f"  {p['pitch_name']:20s} {p['usage_pct']:5.1f}% usage | {p['whiff_pct']:5.1f}% whiff | {velo} | {spin}")
    if r.get("error"):
        print(f"Error: {r['error']}")
    
    print("")
    print("=== Batter Statcast: Aaron Judge (592450) ===")
    b = await get_batter_statcast(592450)
    print(f"PAs sampled: {b.get('pa_sampled')}")
    print(f"Avg Exit Velo: {b.get('avg_exit_velo')} mph")
    print(f"Barrel Rate:   {b.get('barrel_rate')}%")
    print(f"Hard-Hit Rate: {b.get('hard_hit_rate')}%")
    print(f"xBA:           {b.get('xba')}")
    print(f"xSLG:          {b.get('xslg')}")
    if b.get("error"):
        print(f"Error: {b['error']}")

asyncio.run(test())
