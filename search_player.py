import asyncio
import httpx
import json
import sys
sys.path.append("D:\\mlb-stats-app\\backend")
from services import mlb_api

async def main():
    # Search for "Murakami" in MLB Stats API
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://statsapi.mlb.com/api/v1/sports/1/players",
            params={"season": 2026}
        )
        data = r.json()
        players = data.get("people", [])
        matched = [p for p in players if "murakami" in p.get("fullName", "").lower()]
        print(f"Matched players count: {len(matched)}")
        for p in matched:
            pid = p.get("id")
            name = p.get("fullName")
            print(f"\nPlayer: {name} (ID: {pid})")
            
            # Fetch stats for 2025 and 2026
            for season in [2025, 2026]:
                stats = await mlb_api.get_player_stats(pid, "hitting", season=season)
                people = stats.get("people", [{}])
                person = people[0] if people else {}
                print(f"Season {season} stats:")
                found = False
                for s in person.get("stats", []):
                    if s.get("type", {}).get("displayName") == "season":
                        splits = s.get("splits", [])
                        if splits:
                            found = True
                            stat = splits[0].get("stat", {})
                            print(f"  HR: {stat.get('homeRuns')}, PA: {stat.get('plateAppearances')}, G: {stat.get('gamesPlayed')}")
                if not found:
                    print("  No season stats found.")

if __name__ == "__main__":
    asyncio.run(main())
