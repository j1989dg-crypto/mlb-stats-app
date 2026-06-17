import asyncio
import sys
sys.path.append("D:\\mlb-stats-app\\backend")
from routers import hr_model

async def main():
    # Force a cache refresh by calling get_hr_model_today(refresh=True)
    payload = await hr_model.get_hr_model_today(refresh=True)
    batters = payload.get("batters", [])
    if batters:
        b = batters[0]
        print("FIRST BATTER INFO (REFRESHED):")
        print(f"Name: {b.get('name')}")
        print(f"pitcher_opp_ops: {b.get('pitcher_opp_ops')}")
        print(f"bvp_hr: {b.get('bvp_hr')}")
        print(f"recent_hr: {b.get('recent_hr')}")
        print(f"Keys: {list(b.keys())}")

if __name__ == "__main__":
    asyncio.run(main())
