"""
Weather router
"""
from fastapi import APIRouter, HTTPException, Query
from services.weather import get_weather_for_venue, get_park_factors, MLB_STADIUMS

router = APIRouter()

@router.get("/venue/{venue_id}")
async def get_venue_weather(venue_id: int, game_hour: int = Query(default=19)):
    """Get weather forecast for a specific ballpark at game time"""
    try:
        weather = await get_weather_for_venue(venue_id, game_hour)
        park = get_park_factors(venue_id)
        return {
            "weather": weather,
            "park_factors": park,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stadiums")
async def list_stadiums():
    """List all 30 MLB stadiums with coordinates"""
    return {"stadiums": [
        {"venue_id": k, **v} for k, v in MLB_STADIUMS.items()
    ]}
