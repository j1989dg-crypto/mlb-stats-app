"""
Betting router — today's picks dashboard
"""
import asyncio
from fastapi import APIRouter
from services.odds_api import get_mlb_odds
from services import mlb_api
from db.cache import get_cache, set_cache
from datetime import datetime

router = APIRouter()

@router.get("/today")
async def get_todays_picks():
    """All today's games with odds summary — used for dashboard Best Bets banner"""
    cache_key = "betting:today_odds"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    odds = await get_mlb_odds()
    result = {"games": odds, "count": len(odds), "date": datetime.now().strftime("%Y-%m-%d")}
    await set_cache(cache_key, result, 1800)
    return result

@router.get("/remaining_requests")
async def get_remaining_requests():
    """Check how many Odds API requests remain this month"""
    from services.http_client import get_client
    import os
    try:
        client = get_client()
        r = await client.get(
            "https://api.the-odds-api.com/v4/sports",
            params={"apiKey": os.getenv("ODDS_API_KEY", "")},
            timeout=10
        )
        return {
            "requests_remaining": r.headers.get("x-requests-remaining"),
            "requests_used": r.headers.get("x-requests-used"),
        }
    except Exception as e:
        return {"error": str(e)}
