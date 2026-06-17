"""
MLB Park Factors service
Provides per-park HR factor and run factor (multi-year averages from Baseball Reference).
Factor > 100 = hitter-friendly, < 100 = pitcher-friendly (100 = neutral).

Sources: Baseball Reference Park Factors (2022-2024 3-year avg) + known attributes.
"""
from datetime import datetime

# Team abbreviation → park data
# hr_factor: HR park factor (100 = neutral, 115 = 15% more HRs, 85 = 15% fewer)
# run_factor: Overall run park factor
# name: Ballpark name
# roof: open / retractable / dome  (dome/retractable = weather-neutral)
# elevation_ft: Elevation in feet (Coors = 5200, significant ball travel effect)
PARK_FACTORS: dict[str, dict] = {
    "COL": {"name": "Coors Field",               "hr_factor": 122, "run_factor": 115, "roof": "open",         "elevation_ft": 5200},
    "CIN": {"name": "Great American Ball Park",   "hr_factor": 117, "run_factor": 107, "roof": "open",         "elevation_ft": 490},
    "PHI": {"name": "Citizens Bank Park",         "hr_factor": 116, "run_factor": 105, "roof": "open",         "elevation_ft": 20},
    "TEX": {"name": "Globe Life Field",           "hr_factor": 112, "run_factor": 104, "roof": "retractable",  "elevation_ft": 551},
    "BOS": {"name": "Fenway Park",                "hr_factor": 110, "run_factor": 106, "roof": "open",         "elevation_ft": 20},
    "MIL": {"name": "American Family Field",      "hr_factor": 110, "run_factor": 103, "roof": "retractable",  "elevation_ft": 635},
    "BAL": {"name": "Oriole Park at Camden Yards","hr_factor": 109, "run_factor": 103, "roof": "open",         "elevation_ft": 20},
    "NYY": {"name": "Yankee Stadium",             "hr_factor": 109, "run_factor": 104, "roof": "open",         "elevation_ft": 55},
    "CHC": {"name": "Wrigley Field",              "hr_factor": 107, "run_factor": 103, "roof": "open",         "elevation_ft": 595},
    "ATL": {"name": "Truist Park",                "hr_factor": 106, "run_factor": 102, "roof": "open",         "elevation_ft": 1050},
    "DET": {"name": "Comerica Park",              "hr_factor": 104, "run_factor": 100, "roof": "open",         "elevation_ft": 600},
    "LAD": {"name": "Dodger Stadium",             "hr_factor": 103, "run_factor": 101, "roof": "open",         "elevation_ft": 510},
    "ARI": {"name": "Chase Field",                "hr_factor": 102, "run_factor": 101, "roof": "retractable",  "elevation_ft": 1082},
    "MIN": {"name": "Target Field",               "hr_factor": 101, "run_factor": 100, "roof": "open",         "elevation_ft": 820},
    "CLE": {"name": "Progressive Field",          "hr_factor": 100, "run_factor": 100, "roof": "open",         "elevation_ft": 653},
    "NYM": {"name": "Citi Field",                 "hr_factor": 99,  "run_factor": 99,  "roof": "open",         "elevation_ft": 20},
    "HOU": {"name": "Minute Maid Park",           "hr_factor": 99,  "run_factor": 99,  "roof": "retractable",  "elevation_ft": 43},
    "PIT": {"name": "PNC Park",                   "hr_factor": 99,  "run_factor": 99,  "roof": "open",         "elevation_ft": 730},
    "TOR": {"name": "Rogers Centre",              "hr_factor": 99,  "run_factor": 100, "roof": "dome",         "elevation_ft": 250},
    "STL": {"name": "Busch Stadium",              "hr_factor": 98,  "run_factor": 98,  "roof": "open",         "elevation_ft": 465},
    "LAA": {"name": "Angel Stadium",              "hr_factor": 98,  "run_factor": 98,  "roof": "open",         "elevation_ft": 160},
    "KC":  {"name": "Kauffman Stadium",           "hr_factor": 97,  "run_factor": 98,  "roof": "open",         "elevation_ft": 1040},
    "CWS": {"name": "Guaranteed Rate Field",      "hr_factor": 97,  "run_factor": 98,  "roof": "open",         "elevation_ft": 595},
    "WSH": {"name": "Nationals Park",             "hr_factor": 96,  "run_factor": 98,  "roof": "open",         "elevation_ft": 25},
    "MIA": {"name": "loanDepot park",             "hr_factor": 95,  "run_factor": 97,  "roof": "retractable",  "elevation_ft": 6},
    "TB":  {"name": "Tropicana Field",            "hr_factor": 95,  "run_factor": 96,  "roof": "dome",         "elevation_ft": 15},
    "SEA": {"name": "T-Mobile Park",              "hr_factor": 94,  "run_factor": 97,  "roof": "retractable",  "elevation_ft": 20},
    "SD":  {"name": "Petco Park",                 "hr_factor": 93,  "run_factor": 96,  "roof": "open",         "elevation_ft": 20},
    "OAK": {"name": "Oakland Coliseum",           "hr_factor": 91,  "run_factor": 96,  "roof": "open",         "elevation_ft": 25},
    "SF":  {"name": "Oracle Park",                "hr_factor": 88,  "run_factor": 95,  "roof": "open",         "elevation_ft": 10},
    # Sacramento (Athletics new home from 2025)
    "SAC": {"name": "Sutter Health Park",         "hr_factor": 100, "run_factor": 100, "roof": "open",         "elevation_ft": 30},
}

# Alias map — some API responses use different abbreviations
_ALIAS: dict[str, str] = {
    "WAS": "WSH", "WSN": "WSH",
    "SFG": "SF",
    "SDG": "SD",
    "ANA": "LAA",
    "TBR": "TB",
    "KCR": "KC",
    "CHW": "CWS",
    "AZ":  "ARI",
}


def get_park_factor(home_team_abbr: str) -> dict:
    """
    Returns park factor dict for the home team's ballpark.
    Falls back to neutral (100/100) if team not found.
    """
    abbr = home_team_abbr.upper().strip() if home_team_abbr else ""
    abbr = _ALIAS.get(abbr, abbr)
    pf = PARK_FACTORS.get(abbr)
    if pf:
        return {
            "team": abbr,
            "name": pf["name"],
            "hr_factor": pf["hr_factor"],
            "run_factor": pf["run_factor"],
            "roof": pf["roof"],
            "elevation_ft": pf["elevation_ft"],
            "hr_boost_label": _hr_label(pf["hr_factor"]),
        }
    return {
        "team": abbr,
        "name": "Unknown Park",
        "hr_factor": 100,
        "run_factor": 100,
        "roof": "open",
        "elevation_ft": 0,
        "hr_boost_label": "Neutral",
    }


def _hr_label(hr_factor: int) -> str:
    if hr_factor >= 115:
        return "Extreme HR Park 🚀"
    if hr_factor >= 108:
        return "HR-Friendly 📈"
    if hr_factor >= 103:
        return "Slightly HR-Friendly"
    if hr_factor >= 97:
        return "Neutral ⚖️"
    if hr_factor >= 92:
        return "HR-Suppressing 📉"
    return "Extreme Pitcher's Park 🏔️"
