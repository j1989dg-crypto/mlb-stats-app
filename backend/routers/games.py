"""
Games router — schedule, game details, lineups
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import date
from services import mlb_api
from services.weather import get_weather_for_venue, get_park_factors, get_stadium, MLB_STADIUMS

router = APIRouter()

@router.get("/today")
async def get_today_games(game_date: str = Query(default=None)):
    """Get all games for today (or a specified date)"""
    if not game_date:
        game_date = date.today().strftime("%Y-%m-%d")
    try:
        games = await mlb_api.get_schedule(game_date)
        enriched = []
        for g in games:
            venue_id = g.get("venue", {}).get("id")
            stadium = get_stadium(venue_id) if venue_id else None
            park = get_park_factors(venue_id) if venue_id else {}
            enriched.append({
                "game_pk": g.get("gamePk"),
                "game_date": game_date,
                "status": g.get("status", {}).get("detailedState", "Scheduled"),
                "status_code": g.get("status", {}).get("statusCode", "S"),
                "away_team": {
                    "id": g.get("teams", {}).get("away", {}).get("team", {}).get("id"),
                    "name": g.get("teams", {}).get("away", {}).get("team", {}).get("name"),
                    "abbreviation": g.get("teams", {}).get("away", {}).get("team", {}).get("abbreviation"),
                    "score": g.get("teams", {}).get("away", {}).get("score"),
                    "wins": g.get("teams", {}).get("away", {}).get("leagueRecord", {}).get("wins"),
                    "losses": g.get("teams", {}).get("away", {}).get("leagueRecord", {}).get("losses"),
                },
                "home_team": {
                    "id": g.get("teams", {}).get("home", {}).get("team", {}).get("id"),
                    "name": g.get("teams", {}).get("home", {}).get("team", {}).get("name"),
                    "abbreviation": g.get("teams", {}).get("home", {}).get("team", {}).get("abbreviation"),
                    "score": g.get("teams", {}).get("home", {}).get("score"),
                    "wins": g.get("teams", {}).get("home", {}).get("leagueRecord", {}).get("wins"),
                    "losses": g.get("teams", {}).get("home", {}).get("leagueRecord", {}).get("losses"),
                },
                "away_probable_pitcher": _extract_pitcher(g, "away"),
                "home_probable_pitcher": _extract_pitcher(g, "home"),
                "venue": {
                    "id": venue_id,
                    "name": g.get("venue", {}).get("name"),
                    "stadium_info": stadium,
                },
                "park_factors": park,
                "game_time": g.get("gameDate"),
                "inning": g.get("linescore", {}).get("currentInning"),
                "inning_state": g.get("linescore", {}).get("inningState"),
                "linescore": g.get("linescore"),
            })
        return {"date": game_date, "total_games": len(enriched), "games": enriched}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _extract_pitcher(game: dict, side: str) -> dict:
    pp = game.get("teams", {}).get(side, {}).get("probablePitcher", {})
    if not pp:
        return None
    return {
        "id": pp.get("id"),
        "name": pp.get("fullName"),
        "note": pp.get("note"),
    }

@router.get("/{game_pk}")
async def get_game(game_pk: int):
    """Get full live game feed"""
    try:
        return await mlb_api.get_game_detail(game_pk)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{game_pk}/boxscore")
async def get_boxscore(game_pk: int):
    try:
        return await mlb_api.get_boxscore(game_pk)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{game_pk}/lineup")
async def get_lineup(game_pk: int):
    try:
        return await mlb_api.get_lineup(game_pk)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
