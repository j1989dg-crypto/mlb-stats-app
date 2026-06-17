"""
Hot/Cold streak calculator
Analyzes last N games of player game logs to detect streaks
"""
from typing import List, Dict, Any

def calculate_streak(game_log: list, n_games: int = 15) -> dict:
    """
    Given a player's game log (list of split dicts from MLB Stats API),
    calculate streak stats and classify as Hot/Cold/Neutral.
    """
    if not game_log:
        return {"status": "unknown", "games": 0}

    recent = game_log[-n_games:]  # last N games
    total = len(recent)
    if total == 0:
        return {"status": "unknown", "games": 0}

    # Aggregate hitting stats
    ab = sum(int(g.get("stat", {}).get("atBats", 0)) for g in recent)
    hits = sum(int(g.get("stat", {}).get("hits", 0)) for g in recent)
    hr = sum(int(g.get("stat", {}).get("homeRuns", 0)) for g in recent)
    rbi = sum(int(g.get("stat", {}).get("rbi", 0)) for g in recent)
    bb = sum(int(g.get("stat", {}).get("baseOnBalls", 0)) for g in recent)
    so = sum(int(g.get("stat", {}).get("strikeOuts", 0)) for g in recent)
    doubles = sum(int(g.get("stat", {}).get("doubles", 0)) for g in recent)
    triples = sum(int(g.get("stat", {}).get("triples", 0)) for g in recent)
    pa = ab + bb

    avg = round(hits / ab, 3) if ab > 0 else 0.000
    obp = round((hits + bb) / pa, 3) if pa > 0 else 0.000
    tb = hits + doubles + 2 * triples + 3 * hr
    slg = round(tb / ab, 3) if ab > 0 else 0.000
    ops = round(obp + slg, 3)

    # Build per-game trend for sparkline
    game_avgs = []
    running_h = 0
    running_ab = 0
    for g in recent:
        s = g.get("stat", {})
        running_h += int(s.get("hits", 0))
        running_ab += int(s.get("atBats", 0))
        game_avgs.append(round(running_h / running_ab, 3) if running_ab > 0 else 0.000)

    # Determine streak status
    # Hot: AVG >= .320 or OPS >= .900 in last N games
    # Cold: AVG <= .175 or OPS <= .550 in last N games
    if avg >= 0.320 or ops >= 0.900:
        status = "hot"
        label = "🔥 On Fire"
    elif avg <= 0.175 or ops <= 0.550:
        status = "cold"
        label = "❄️ Cold Streak"
    elif avg >= 0.280 or ops >= 0.800:
        status = "warm"
        label = "📈 Trending Up"
    else:
        status = "neutral"
        label = "➡️ Average"

    # Hit streak (consecutive games with a hit)
    hit_streak = 0
    for g in reversed(recent):
        if int(g.get("stat", {}).get("hits", 0)) > 0:
            hit_streak += 1
        else:
            break

    return {
        "status": status,
        "label": label,
        "games_analyzed": total,
        "avg": avg,
        "obp": obp,
        "slg": slg,
        "ops": ops,
        "hr": hr,
        "rbi": rbi,
        "bb": bb,
        "so": so,
        "hit_streak": hit_streak,
        "game_trend": game_avgs,  # for sparkline chart
    }

def calculate_pitcher_streak(game_log: list, n_games: int = 5) -> dict:
    """Analyze pitcher's recent performance"""
    if not game_log:
        return {"status": "unknown", "games": 0}

    recent = game_log[-n_games:]
    total = len(recent)
    if total == 0:
        return {"status": "unknown", "games": 0}

    er = sum(int(g.get("stat", {}).get("earnedRuns", 0)) for g in recent)
    ip_raw = sum(float(g.get("stat", {}).get("inningsPitched", 0)) for g in recent)
    so = sum(int(g.get("stat", {}).get("strikeOuts", 0)) for g in recent)
    bb = sum(int(g.get("stat", {}).get("baseOnBalls", 0)) for g in recent)
    hits_allowed = sum(int(g.get("stat", {}).get("hits", 0)) for g in recent)

    era = round((er / ip_raw) * 9, 2) if ip_raw > 0 else 99.00
    k_per_9 = round((so / ip_raw) * 9, 2) if ip_raw > 0 else 0
    whip = round((bb + hits_allowed) / ip_raw, 3) if ip_raw > 0 else 99.0

    # ERA-based classification
    if era <= 2.50:
        status = "hot"
        label = "🔥 Dominant"
    elif era <= 3.50:
        status = "warm"
        label = "📈 Sharp"
    elif era >= 6.00:
        status = "cold"
        label = "❄️ Struggling"
    else:
        status = "neutral"
        label = "➡️ Average"

    era_trend = []
    running_er = 0
    running_ip = 0
    for g in recent:
        s = g.get("stat", {})
        running_er += int(s.get("earnedRuns", 0))
        running_ip += float(s.get("inningsPitched", 0))
        era_trend.append(round((running_er / running_ip) * 9, 2) if running_ip > 0 else 0)

    return {
        "status": status,
        "label": label,
        "games_analyzed": total,
        "era": era,
        "whip": whip,
        "k_per_9": k_per_9,
        "strikeouts": so,
        "walks": bb,
        "era_trend": era_trend,
    }
