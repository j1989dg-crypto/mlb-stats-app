"""
MLB Stats API service — wraps statsapi.mlb.com
"""
import httpx
import asyncio
import re
import unicodedata
from datetime import datetime, date
from bs4 import BeautifulSoup
from db.cache import get_cache, set_cache
from services.http_client import get_client

TEAM_ABBR_MAP = {
    "WAS": "WSH",
    "WSH": "WSH",
    "SFG": "SF",
    "SF": "SF",
    "SDG": "SD",
    "SD": "SD",
    "ANA": "LAA",
    "LAA": "LAA",
    "ARI": "ARI",
    "AZ": "ARI",
    "TBR": "TB",
    "TB": "TB",
    "KCR": "KC",
    "KC": "KC",
    "CHW": "CWS",
    "CWS": "CWS",
    "CHC": "CHC",
    "STL": "STL",
    "NYM": "NYM",
    "NYY": "NYY",
    "BOS": "BOS",
    "TOR": "TOR",
    "BAL": "BAL",
    "CLE": "CLE",
    "MIN": "MIN",
    "DET": "DET",
    "HOU": "HOU",
    "SEA": "SEA",
    "TEX": "TEX",
    "OAK": "OAK",
    "ATL": "ATL",
    "PHI": "PHI",
    "MIA": "MIA",
    "MIL": "MIL",
    "PIT": "PIT",
    "CIN": "CIN",
    "LAD": "LAD",
    "COL": "COL",
}

def normalize_abbr(abbr: str) -> str:
    if not abbr:
        return ""
    abbr = abbr.upper().strip()
    return TEAM_ABBR_MAP.get(abbr, abbr)

def normalize_name(name: str) -> str:
    if not name:
        return ""
    # Strip accents
    name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    name = name.lower()
    # Remove punctuation
    name = re.sub(r"[.'\-\,]", " ", name)
    # Remove suffixes
    name = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", name)
    return " ".join(name.split())

def match_player(scraped_name: str, players_dict: dict) -> dict | None:
    if not scraped_name or not players_dict:
        return None
    scraped_norm = normalize_name(scraped_name)
    scraped_clean = scraped_norm.replace(" ", "")
    
    # 1. Exact or normalized full match
    for pid, p in players_dict.items():
        p_name = p.get("fullName", "")
        p_norm = normalize_name(p_name)
        if scraped_norm == p_norm:
            return p
        if scraped_clean == p_norm.replace(" ", ""):
            return p
            
    # 2. Check if scraped_name has initials like 'B. Leibrandt' or 'T. J. Friedl'
    # Try match by last name and first initial
    parts = scraped_norm.split()
    if len(parts) >= 2:
        scraped_last = parts[-1]
        scraped_first_init = parts[0][0]
        
        for pid, p in players_dict.items():
            p_last_norm = normalize_name(p.get("lastName", ""))
            p_first_norm = normalize_name(p.get("firstName", ""))
            if p_last_norm == scraped_last and p_first_norm.startswith(scraped_first_init):
                return p
                
    return None

async def _get_rotowire_lineups(target_date: str = "today") -> list:
    cache_key = f"rotowire:lineups:{target_date}"
    cached = await get_cache(cache_key)
    if cached is not None:
        return cached

    url = "https://www.rotowire.com/baseball/daily-lineups.php"
    if target_date == "tomorrow":
        url += "?date=tomorrow"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        client = get_client()
        r = await client.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        boxes = soup.select(".lineup__box")
        
        lineups = []
        for box in boxes:
            teams = box.select(".lineup__abbr")
            if len(teams) < 2:
                continue
            away_team = normalize_abbr(teams[0].text.strip())
            home_team = normalize_abbr(teams[1].text.strip())
            
            # Away Lineup
            away_batters = []
            away_list = box.select(".lineup__list.is-visit")
            if away_list:
                for b in away_list[0].select(".lineup__player"):
                    a = b.find("a")
                    bats_span = b.select_one(".lineup__bats")
                    bats = bats_span.text.strip() if bats_span else "R"
                    name = a["title"].strip() if (a and a.has_attr("title")) else b.text.strip()
                    away_batters.append({"name": name, "bats": bats})
                
                # Pitcher
                p_div = away_list[0].select_one(".lineup__player-highlight-name")
                away_pitcher = None
                if p_div:
                    p_anchor = p_div.find("a")
                    p_throws = p_div.select_one(".lineup__throws")
                    throws = p_throws.text.strip() if p_throws else "R"
                    p_name = p_anchor.text.strip() if p_anchor else p_div.text.strip()
                    away_pitcher = {"name": p_name, "throws": throws}
            else:
                away_pitcher = None
                
            # Home Lineup
            home_batters = []
            home_list = box.select(".lineup__list.is-home")
            if home_list:
                for b in home_list[0].select(".lineup__player"):
                    a = b.find("a")
                    bats_span = b.select_one(".lineup__bats")
                    bats = bats_span.text.strip() if bats_span else "R"
                    name = a["title"].strip() if (a and a.has_attr("title")) else b.text.strip()
                    home_batters.append({"name": name, "bats": bats})
                
                p_div = home_list[0].select_one(".lineup__player-highlight-name")
                home_pitcher = None
                if p_div:
                    p_anchor = p_div.find("a")
                    p_throws = p_div.select_one(".lineup__throws")
                    throws = p_throws.text.strip() if p_throws else "R"
                    p_name = p_anchor.text.strip() if p_anchor else p_div.text.strip()
                    home_pitcher = {"name": p_name, "throws": throws}
            else:
                home_pitcher = None
                
            lineups.append({
                "away_team": away_team,
                "home_team": home_team,
                "away_batters": away_batters,
                "away_pitcher": away_pitcher,
                "home_batters": home_batters,
                "home_pitcher": home_pitcher
            })
        
        await set_cache(cache_key, lineups, 600)  # 10 minutes cache
        return lineups
    except Exception as e:
        print(f"RotoWire Scraper Error: {e}")
        return []


MLB_BASE = "https://statsapi.mlb.com/api/v1"
CACHE_TTL = 300  # 5 minutes for live game data

async def fetch(url: str, params: dict = None) -> dict:
    client = get_client()
    r = await client.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

async def get_schedule(game_date: str = None) -> list:
    if not game_date:
        game_date = date.today().strftime("%Y-%m-%d")
    cache_key = f"schedule:{game_date}"
    cached = await get_cache(cache_key)
    if cached:
        return cached
    data = await fetch(f"{MLB_BASE}/schedule", {
        "sportId": 1,
        "date": game_date,
        "hydrate": "team,venue,weather,probablePitcher(note),linescore,broadcasts"
    })
    games = []
    for date_obj in data.get("dates", []):
        for game in date_obj.get("games", []):
            games.append(game)
    await set_cache(cache_key, games, CACHE_TTL)
    return games

_GAME_DETAIL_MEM_CACHE = {}  # In-memory cache for game detail JSONs (which are huge, up to 10MB)

async def get_game_detail(game_pk: int) -> dict:
    import time
    now = time.time()
    if game_pk in _GAME_DETAIL_MEM_CACHE:
        data, expires_at = _GAME_DETAIL_MEM_CACHE[game_pk]
        if now < expires_at:
            return data
            
    data = await fetch(f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live")
    _GAME_DETAIL_MEM_CACHE[game_pk] = (data, now + 60)  # Cache in-memory for 60 seconds
    return data

async def get_boxscore(game_pk: int) -> dict:
    cache_key = f"boxscore:{game_pk}"
    cached = await get_cache(cache_key)
    if cached:
        return cached
    data = await fetch(f"{MLB_BASE}/game/{game_pk}/boxscore")
    await set_cache(cache_key, data, 60)
    return data

async def get_player_stats(player_id: int, group: str = "hitting", season: int = None, refresh: bool = False) -> dict:
    if not season:
        season = datetime.now().year
    cache_key = f"player_stats:{player_id}:{group}:{season}"
    if not refresh:
        cached = await get_cache(cache_key)
        if cached:
            return cached
    data = await fetch(f"{MLB_BASE}/people/{player_id}", {
        "hydrate": f"stats(group=[{group}],type=season,season={season}),currentTeam"
    })
    await set_cache(cache_key, data, 3600)  # 1hr
    return data

async def get_player_game_log(player_id: int, group: str = "hitting", season: int = None) -> list:
    if not season:
        season = datetime.now().year
    cache_key = f"game_log:{player_id}:{group}:{season}"
    cached = await get_cache(cache_key)
    if cached:
        return cached
    data = await fetch(f"{MLB_BASE}/people/{player_id}", {
        "hydrate": f"stats(group=[{group}],type=gameLog,season={season})"
    })
    splits = []
    for stat_block in data.get("people", [{}])[0].get("stats", []):
        if stat_block.get("type", {}).get("displayName") == "gameLog":
            splits = stat_block.get("splits", [])
            break
    await set_cache(cache_key, splits, 3600)
    return splits

async def get_batter_vs_pitcher(batter_id: int, pitcher_id: int) -> dict:
    cache_key = f"bvp:{batter_id}:{pitcher_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached
    data = await fetch(f"{MLB_BASE}/people/{batter_id}/stats", {
        "stats": "vsPlayerTotal",
        "opposingPlayerId": pitcher_id,
        "group": "hitting"
    })
    await set_cache(cache_key, data, 86400)  # 24hrs (historical)
    return data

async def get_lineup(game_pk: int) -> dict:
    """Get starting lineups and probable pitchers for a game"""
    cache_key = f"lineup:processed:{game_pk}"
    cached = await get_cache(cache_key)
    if cached is not None:
        return cached

    detail = await get_game_detail(game_pk)
    live = detail.get("liveData", {})
    boxscore = live.get("boxscore", {})
    teams = boxscore.get("teams", {})
    
    # Check if official starting lineups exist
    has_official = False
    for side in ["away", "home"]:
        team_data = teams.get(side, {})
        if team_data.get("batters"):
            has_official = True
            break
            
    if has_official:
        result = {"away": {}, "home": {}, "source": "official"}
        for side in ["away", "home"]:
            team_data = teams.get(side, {})
            batters = team_data.get("batters", [])
            pitchers = team_data.get("pitchers", [])
            players = team_data.get("players", {})
            result[side] = {
                "team": team_data.get("team", {}),
                "batters": [players.get(f"ID{pid}", {}) for pid in batters],
                "pitchers": [players.get(f"ID{pid}", {}) for pid in pitchers],
            }
        await set_cache(cache_key, result, 60)
        return result
    else:
        # Fallback to RotoWire expected lineups
        game_data = detail.get("gameData", {})
        gd_teams = game_data.get("teams", {})
        away_team_obj = gd_teams.get("away", {})
        home_team_obj = gd_teams.get("home", {})
        
        away_abbr = normalize_abbr(away_team_obj.get("abbreviation"))
        home_abbr = normalize_abbr(home_team_obj.get("abbreviation"))
        
        # Determine RotoWire target date based on game official date
        game_date_str = detail.get("gameData", {}).get("datetime", {}).get("officialDate")
        today_str = date.today().strftime("%Y-%m-%d")
        target_date = "today"
        if game_date_str and game_date_str > today_str:
            target_date = "tomorrow"
            
        rotowire_list = await _get_rotowire_lineups(target_date)
        
        # Find matching game in RotoWire
        matched_rw = None
        for rw in rotowire_list:
            if rw["away_team"] == away_abbr and rw["home_team"] == home_abbr:
                matched_rw = rw
                break
                
        result = {"away": {}, "home": {}, "source": "rotowire"}
        gd_players = game_data.get("players", {})
        
        if matched_rw:
            # Map away batters
            away_batters = []
            for idx, rw_b in enumerate(matched_rw["away_batters"]):
                matched_player = match_player(rw_b["name"], gd_players)
                if matched_player:
                    player_dict = {
                        "person": {
                            "id": matched_player.get("id"),
                            "fullName": matched_player.get("fullName"),
                            "link": matched_player.get("link"),
                            "batSide": {"code": rw_b["bats"]}
                        },
                        "jerseyNumber": matched_player.get("primaryNumber", ""),
                        "position": matched_player.get("primaryPosition", {}),
                        "battingOrder": str((idx + 1) * 100)
                    }
                    away_batters.append(player_dict)
                    
            # Map away pitcher
            away_pitchers = []
            if matched_rw["away_pitcher"]:
                rw_p = matched_rw["away_pitcher"]
                matched_player = match_player(rw_p["name"], gd_players)
                if matched_player:
                    player_dict = {
                        "person": {
                            "id": matched_player.get("id"),
                            "fullName": matched_player.get("fullName"),
                            "link": matched_player.get("link"),
                            "pitchHand": {"code": rw_p["throws"]}
                        },
                        "position": matched_player.get("primaryPosition", {})
                    }
                    away_pitchers.append(player_dict)
                    
            # Map home batters
            home_batters = []
            for idx, rw_b in enumerate(matched_rw["home_batters"]):
                matched_player = match_player(rw_b["name"], gd_players)
                if matched_player:
                    player_dict = {
                        "person": {
                            "id": matched_player.get("id"),
                            "fullName": matched_player.get("fullName"),
                            "link": matched_player.get("link"),
                            "batSide": {"code": rw_b["bats"]}
                        },
                        "jerseyNumber": matched_player.get("primaryNumber", ""),
                        "position": matched_player.get("primaryPosition", {}),
                        "battingOrder": str((idx + 1) * 100)
                    }
                    home_batters.append(player_dict)
                    
            # Map home pitcher
            home_pitchers = []
            if matched_rw["home_pitcher"]:
                rw_p = matched_rw["home_pitcher"]
                matched_player = match_player(rw_p["name"], gd_players)
                if matched_player:
                    player_dict = {
                        "person": {
                            "id": matched_player.get("id"),
                            "fullName": matched_player.get("fullName"),
                            "link": matched_player.get("link"),
                            "pitchHand": {"code": rw_p["throws"]}
                        },
                        "position": matched_player.get("primaryPosition", {})
                    }
                    home_pitchers.append(player_dict)
                    
            result["away"] = {
                "team": away_team_obj,
                "batters": away_batters,
                "pitchers": away_pitchers
            }
            result["home"] = {
                "team": home_team_obj,
                "batters": home_batters,
                "pitchers": home_pitchers
            }
        else:
            # Fall back to whatever boxscore has
            for side in ["away", "home"]:
                team_data = teams.get(side, {})
                batters = team_data.get("batters", [])
                pitchers = team_data.get("pitchers", [])
                players = team_data.get("players", {})
                result[side] = {
                    "team": team_data.get("team", {}),
                    "batters": [players.get(f"ID{pid}", {}) for pid in batters],
                    "pitchers": [players.get(f"ID{pid}", {}) for pid in pitchers],
                }
        await set_cache(cache_key, result, 60)
        return result

async def get_standings() -> dict:
    cache_key = f"standings:{date.today().isoformat()}"
    cached = await get_cache(cache_key)
    if cached:
        return cached
    data = await fetch(f"{MLB_BASE}/standings", {
        "leagueId": "103,104",
        "season": datetime.now().year,
        "hydrate": "team"
    })
    await set_cache(cache_key, data, 3600)
    return data
