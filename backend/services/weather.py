"""
WeatherAPI.com service for MLB ballpark weather
"""
import httpx
import os
from db.cache import get_cache, set_cache
from services.http_client import get_client

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_BASE = "https://api.weatherapi.com/v1"

# Map MLB Stats API venue IDs to our internal venue IDs
# This is a fallback map for known discrepencies
MLB_VENUE_MAP = {
    4705: 133, # Oakland Coliseum
    2500: 108, # Angel Stadium
    15:   109, # Chase Field
    2:    110, # Oriole Park at Camden Yards
    3:    111, # Fenway Park
    17:   112, # Wrigley Field
    2602: 113, # Great American Ball Park
    5:    114, # Progressive Field
    19:   115, # Coors Field
    2394: 116, # Comerica Park
    4169: 117, # Minute Maid Park
    7:    118, # Kauffman Stadium
    22:   119, # Dodger Stadium
    3312: 120, # Nationals Park
    3289: 121, # Citi Field
    680:  136, # T-Mobile Park
    2395: 137, # Oracle Park
    2889: 138, # Busch Stadium
    12:   139, # Tropicana Field
    5325: 140, # Globe Life Field
    14:   141, # Rogers Centre
    3315: 142, # Target Field
    2681: 143, # Citizens Bank Park
    4703: 144, # Truist Park
    4:    145, # Guaranteed Rate Field
    4167: 146, # loanDepot Park
    3313: 147, # Yankee Stadium
    32:   158, # American Family Field
    31:   134, # PNC Park
    2680: 135, # Petco Park
}

# All 30 MLB stadiums with coordinates and metadata
MLB_STADIUMS = {
    133: {"name": "Oakland Coliseum",       "team": "Athletics",      "lat": 37.7516, "lon": -122.2005, "roof": "open",         "elevation_ft": 25},
    108: {"name": "Angel Stadium",          "team": "Angels",         "lat": 33.8003, "lon": -117.8827, "roof": "open",         "elevation_ft": 160},
    109: {"name": "Chase Field",            "team": "Diamondbacks",   "lat": 33.4453, "lon": -112.0667, "roof": "retractable",  "elevation_ft": 1082},
    110: {"name": "Oriole Park at Camden Yards","team":"Orioles",     "lat": 39.2839, "lon": -76.6217,  "roof": "open",         "elevation_ft": 20},
    111: {"name": "Fenway Park",            "team": "Red Sox",        "lat": 42.3467, "lon": -71.0972,  "roof": "open",         "elevation_ft": 20},
    112: {"name": "Wrigley Field",          "team": "Cubs",           "lat": 41.9484, "lon": -87.6553,  "roof": "open",         "elevation_ft": 595},
    113: {"name": "Great American Ball Park","team":"Reds",           "lat": 39.0975, "lon": -84.5065,  "roof": "open",         "elevation_ft": 490},
    114: {"name": "Progressive Field",      "team": "Guardians",      "lat": 41.4963, "lon": -81.6852,  "roof": "open",         "elevation_ft": 653},
    115: {"name": "Coors Field",            "team": "Rockies",        "lat": 39.7559, "lon": -104.9942, "roof": "open",         "elevation_ft": 5200},
    116: {"name": "Comerica Park",          "team": "Tigers",         "lat": 42.3390, "lon": -83.0485,  "roof": "open",         "elevation_ft": 600},
    117: {"name": "Minute Maid Park",       "team": "Astros",         "lat": 29.7573, "lon": -95.3555,  "roof": "retractable",  "elevation_ft": 43},
    118: {"name": "Kauffman Stadium",       "team": "Royals",         "lat": 39.0514, "lon": -94.4803,  "roof": "open",         "elevation_ft": 1040},
    119: {"name": "Dodger Stadium",         "team": "Dodgers",        "lat": 34.0739, "lon": -118.2400, "roof": "open",         "elevation_ft": 512},
    120: {"name": "Nationals Park",         "team": "Nationals",      "lat": 38.8730, "lon": -77.0074,  "roof": "open",         "elevation_ft": 24},
    121: {"name": "Citi Field",             "team": "Mets",           "lat": 40.7571, "lon": -73.8458,  "roof": "open",         "elevation_ft": 15},
    136: {"name": "T-Mobile Park",          "team": "Mariners",       "lat": 47.5914, "lon": -122.3325, "roof": "retractable",  "elevation_ft": 30},
    137: {"name": "Oracle Park",            "team": "Giants",         "lat": 37.7786, "lon": -122.3893, "roof": "open",         "elevation_ft": 10},
    138: {"name": "Busch Stadium",          "team": "Cardinals",      "lat": 38.6226, "lon": -90.1928,  "roof": "open",         "elevation_ft": 465},
    139: {"name": "Tropicana Field",        "team": "Rays",           "lat": 27.7683, "lon": -82.6534,  "roof": "fixed dome",   "elevation_ft": 44},
    140: {"name": "Globe Life Field",       "team": "Rangers",        "lat": 32.7473, "lon": -97.0822,  "roof": "retractable",  "elevation_ft": 551},
    141: {"name": "Rogers Centre",          "team": "Blue Jays",      "lat": 43.6414, "lon": -79.3894,  "roof": "retractable",  "elevation_ft": 287},
    142: {"name": "Target Field",           "team": "Twins",          "lat": 44.9817, "lon": -93.2781,  "roof": "open",         "elevation_ft": 830},
    143: {"name": "Citizens Bank Park",     "team": "Phillies",       "lat": 39.9061, "lon": -75.1665,  "roof": "open",         "elevation_ft": 20},
    144: {"name": "Truist Park",            "team": "Braves",         "lat": 33.8908, "lon": -84.4678,  "roof": "open",         "elevation_ft": 1037},
    145: {"name": "Guaranteed Rate Field",  "team": "White Sox",      "lat": 41.8300, "lon": -87.6339,  "roof": "open",         "elevation_ft": 595},
    146: {"name": "loanDepot Park",         "team": "Marlins",        "lat": 25.7781, "lon": -80.2197,  "roof": "retractable",  "elevation_ft": 6},
    147: {"name": "Yankee Stadium",         "team": "Yankees",        "lat": 40.8296, "lon": -73.9262,  "roof": "open",         "elevation_ft": 55},
    158: {"name": "American Family Field",  "team": "Brewers",        "lat": 43.0280, "lon": -87.9712,  "roof": "retractable",  "elevation_ft": 634},
    134: {"name": "PNC Park",               "team": "Pirates",        "lat": 40.4469, "lon": -80.0057,  "roof": "open",         "elevation_ft": 730},
    135: {"name": "Petco Park",             "team": "Padres",         "lat": 32.7076, "lon": -117.1570, "roof": "open",         "elevation_ft": 17},
}

# Park factors (100 = neutral, >100 = hitter friendly)
PARK_FACTORS = {
    115: {"hr": 120, "runs": 115, "hits": 108, "note": "High altitude (5,200 ft) — significantly boosts HRs, balls carry far"},
    147: {"hr": 108, "runs": 104, "hits": 102, "note": "Short porch in right field favors left-handed pull hitters"},
    111: {"hr": 95,  "runs": 101, "hits": 104, "note": "Green Monster creates doubles; suppresses HRs but boosts hits"},
    112: {"hr": 105, "runs": 103, "hits": 102, "note": "Wind off Lake Michigan can be a major factor — in or out"},
    119: {"hr": 96,  "runs": 96,  "hits": 97,  "note": "Spacious foul territory and sea-level air suppress offense"},
    121: {"hr": 112, "runs": 107, "hits": 103, "note": "Power alley dimensions favor right-handed power hitters"},
    117: {"hr": 103, "runs": 103, "hits": 101, "note": "Retractable roof controls environment; train track adds excitement"},
    140: {"hr": 107, "runs": 106, "hits": 104, "note": "Retractable roof, hitter-friendly dimensions in Texas heat"},
    109: {"hr": 105, "runs": 104, "hits": 102, "note": "Retractable roof; dry desert air; hitter-friendly when roof open"},
    137: {"hr": 92,  "runs": 94,  "hits": 95,  "note": "Cold marine air and deep center field suppress power numbers"},
    114: {"hr": 97,  "runs": 98,  "hits": 98,  "note": "Pitcher-friendly park with large foul territory"},
    110: {"hr": 103, "runs": 101, "hits": 101, "note": "Classic ballpark; wind direction varies by game"},
    143: {"hr": 110, "runs": 107, "hits": 104, "note": "Short right-field porch — very favorable for LHB power"},
    144: {"hr": 104, "runs": 103, "hits": 101, "note": "Hot Georgia summers increase carry; hitter-friendly"},
}

def get_park_factors(venue_id: int) -> dict:
    default = {"hr": 100, "runs": 100, "hits": 100, "note": "Neutral park factor"}
    return PARK_FACTORS.get(venue_id, default)

def get_stadium(venue_id: int) -> dict:
    """Resolve MLB Stats API venue ID to our stadium data"""
    if venue_id in MLB_STADIUMS:
        return MLB_STADIUMS[venue_id]
    # Try the venue map (MLB Stats API uses different IDs than our internal ones)
    mapped = MLB_VENUE_MAP.get(venue_id)
    if mapped:
        return MLB_STADIUMS.get(mapped)
    return None

async def get_weather_for_venue(venue_id: int, game_time_hour: int = 19) -> dict:
    """Get weather forecast for a stadium at game time"""
    stadium = get_stadium(venue_id)
    if not stadium:
        # Try fetching weather by city name as fallback
        return {"error": "Stadium not found", "venue_id": venue_id, "controlled_environment": False,
                "temp_f": 72, "wind_mph": 0, "wind_dir": "N", "humidity": 50, "precip_chance": 0,
                "condition": "Unknown", "baseball_impact": "Weather data unavailable for this venue.", "hr_factor": 0}

    # Dome stadiums — weather is irrelevant
    if stadium["roof"] == "fixed dome":
        return {
            "venue_id": venue_id,
            "stadium_name": stadium["name"],
            "roof": "fixed dome",
            "controlled_environment": True,
            "temp_f": 72,
            "condition": "Controlled Indoor Environment",
            "wind_mph": 0,
            "wind_dir": "N/A",
            "humidity": 50,
            "precip_chance": 0,
            "baseball_impact": "No weather impact — fully enclosed dome",
            "hr_factor": 0,
        }

    cache_key = f"weather:{venue_id}"
    from db.cache import get_cache, set_cache
    cached = await get_cache(cache_key)
    if cached:
        return cached

    client = get_client()
    r = await client.get(f"{WEATHER_BASE}/forecast.json", params={
        "key": WEATHER_API_KEY,
        "q": f"{stadium['lat']},{stadium['lon']}",
        "days": 2,
        "aqi": "no",
    }, timeout=10)
    r.raise_for_status()
    data = r.json()

    current = data.get("current", {})
    forecast_day = data.get("forecast", {}).get("forecastday", [{}])[0]
    hour_data = None
    for h in forecast_day.get("hour", []):
        if h.get("time", "").endswith(f" {game_time_hour:02d}:00"):
            hour_data = h
            break
    if not hour_data and forecast_day.get("hour"):
        hour_data = forecast_day["hour"][min(game_time_hour, len(forecast_day["hour"])-1)]

    wind_mph = (hour_data or current).get("wind_mph", 0)
    wind_dir = (hour_data or current).get("wind_dir", "N")
    temp_f = (hour_data or current).get("temp_f", 72)
    precip_chance = (hour_data or current).get("chance_of_rain", 0)
    condition = (hour_data or current).get("condition", {}).get("text", "Clear")
    humidity = (hour_data or current).get("humidity", 50)

    # Baseball impact analysis
    baseball_impact, hr_factor = analyze_weather_impact(wind_mph, wind_dir, temp_f, precip_chance, stadium)

    result = {
        "venue_id": venue_id,
        "stadium_name": stadium["name"],
        "team": stadium["team"],
        "roof": stadium["roof"],
        "elevation_ft": stadium["elevation_ft"],
        "controlled_environment": False,
        "temp_f": temp_f,
        "condition": condition,
        "wind_mph": wind_mph,
        "wind_dir": wind_dir,
        "humidity": humidity,
        "precip_chance": precip_chance,
        "baseball_impact": baseball_impact,
        "hr_factor": hr_factor,  # -3 to +3 adjustment estimate
    }
    await set_cache(cache_key, result, 1800)  # 30 min
    return result

def analyze_weather_impact(wind_mph: float, wind_dir: str, temp_f: float, precip_chance: float, stadium: dict) -> tuple:
    """Generate human-readable weather impact and HR factor adjustment"""
    impacts = []
    hr_adj = 0

    if wind_mph >= 15:
        out_dirs = ["out", "SW", "S", "SE", "W"]  # general out-to-RF directions
        in_dirs = ["in", "NE", "N", "NW", "E"]
        if any(d in wind_dir for d in ["SW", "S", "SE", "W"]):
            impacts.append(f"🌬️ {wind_mph:.0f} mph wind blowing OUT — significant HR boost")
            hr_adj += min(3, int(wind_mph / 8))
        elif any(d in wind_dir for d in ["NE", "N", "NW", "E"]):
            impacts.append(f"🌬️ {wind_mph:.0f} mph wind blowing IN — suppresses fly balls")
            hr_adj -= min(3, int(wind_mph / 8))
        else:
            impacts.append(f"💨 {wind_mph:.0f} mph crosswind — affects pull hitters' trajectories")

    if temp_f >= 85:
        impacts.append(f"🌡️ Hot ({temp_f:.0f}°F) — warm air is less dense, balls carry further")
        hr_adj += 1
    elif temp_f <= 45:
        impacts.append(f"🥶 Cold ({temp_f:.0f}°F) — dense air suppresses fly ball distance")
        hr_adj -= 1

    if precip_chance >= 50:
        impacts.append(f"🌧️ {precip_chance:.0f}% rain chance — delay risk is high")
    elif precip_chance >= 25:
        impacts.append(f"🌦️ {precip_chance:.0f}% rain chance — monitor conditions")

    if stadium.get("elevation_ft", 0) >= 1000:
        impacts.append(f"⛰️ High elevation ({stadium['elevation_ft']:,} ft) — thinner air boosts carry")
        hr_adj += 1

    if not impacts:
        impacts.append("☀️ Ideal baseball weather — no significant environmental factors")

    return "; ".join(impacts), hr_adj
