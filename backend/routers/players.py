"""
Players router — stats, streaks, batter vs pitcher matchups
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from services import mlb_api
from services.streak_calculator import calculate_streak, calculate_pitcher_streak

router = APIRouter()

@router.get("/{player_id}/stats")
async def get_player_stats(player_id: int, group: str = Query(default="hitting"), season: int = Query(default=None)):
    """Get season stats for a player"""
    try:
        if not season:
            season = datetime.now().year
        data = await mlb_api.get_player_stats(player_id, group, season)
        people = data.get("people", [])
        if not people:
            raise HTTPException(status_code=404, detail="Player not found")
        person = people[0]
        stats_list = person.get("stats", [])
        season_stats = {}
        for s in stats_list:
            if s.get("type", {}).get("displayName") == "season":
                splits = s.get("splits", [])
                if splits:
                    season_stats = splits[0].get("stat", {})
        return {
            "player_id": player_id,
            "name": person.get("fullName"),
            "position": person.get("primaryPosition", {}).get("abbreviation"),
            "team": person.get("currentTeam", {}).get("name"),
            "group": group,
            "season": season,
            "stats": season_stats,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{player_id}/streak")
async def get_player_streak(player_id: int, group: str = Query(default="hitting"), n_games: int = Query(default=15)):
    """Calculate hot/cold streak for a player"""
    try:
        game_log = await mlb_api.get_player_game_log(player_id, group)
        if group == "pitching":
            streak = calculate_pitcher_streak(game_log, n_games)
        else:
            streak = calculate_streak(game_log, n_games)
        return {"player_id": player_id, "group": group, "streak": streak}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{batter_id}/vs/{pitcher_id}")
async def get_bvp_stats(batter_id: int, pitcher_id: int):
    """Career batter vs. pitcher matchup stats"""
    try:
        data = await mlb_api.get_batter_vs_pitcher(batter_id, pitcher_id)
        stats = {}
        for s in data.get("stats", []):
            splits = s.get("splits", [])
            if splits:
                stats = splits[0].get("stat", {})
                break
        return {
            "batter_id": batter_id,
            "pitcher_id": pitcher_id,
            "career_stats": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{player_id}/gamelog")
async def get_game_log(player_id: int, group: str = Query(default="hitting")):
    """Full season game log for a player"""
    try:
        log = await mlb_api.get_player_game_log(player_id, group)
        return {"player_id": player_id, "group": group, "game_log": log[-30:]}  # Last 30 games
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
