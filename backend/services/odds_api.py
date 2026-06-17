"""
The Odds API service — real market lines for MLB games
Fetches moneyline, run line (spread), totals, and player props
Free tier: 500 requests/month — we cache aggressively (30-min TTL)
"""
import os
import httpx
from db.cache import get_cache, set_cache
from services.http_client import get_client

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_BASE = "https://api.the-odds-api.com/v4"
SPORT = "baseball_mlb"

# Bookmaker priority order (first available is used)
BOOK_PRIORITY = ["draftkings", "fanduel", "betmgm", "caesars", "pointsbet_us", "williamhill_us"]


def _best_book(outcomes: list, key="name") -> dict | None:
    """Pick the first available outcome from preferred bookmakers"""
    if not outcomes:
        return None
    return outcomes[0]


def _implied_prob(american_odds: int) -> float:
    """Convert American odds to implied probability"""
    if american_odds < 0:
        return round((-american_odds) / (-american_odds + 100) * 100, 1)
    return round(100 / (american_odds + 100) * 100, 1)


def _format_american(price: float) -> str:
    """Format decimal odds as American"""
    if price >= 2.0:
        return f"+{int((price - 1) * 100)}"
    return str(int(-100 / (price - 1)))


async def get_mlb_odds() -> list:
    """
    Fetch today's MLB moneyline + run line + totals for all games.
    Returns list of game odds objects.
    """
    cache_key = "odds:mlb_today"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    try:
        client = get_client()
        r = await client.get(
            f"{ODDS_BASE}/sports/{SPORT}/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "h2h,spreads,totals",
                "oddsFormat": "american",
                "bookmakers": ",".join(BOOK_PRIORITY),
            },
            timeout=15
        )
        if r.status_code != 200:
            return []
        games = r.json()

        result = []
        for game in games:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            event_id = game.get("id", "")
            commence = game.get("commence_time", "")

            ml_home = ml_away = None
            rl_home = rl_away = rl_line = None
            total_line = total_over = total_under = None

            for book in game.get("bookmakers", []):
                for market in book.get("markets", []):
                    mkey = market.get("key", "")
                    outcomes = market.get("outcomes", [])
                    home_out = next((o for o in outcomes if o.get("name") == home), None)
                    away_out = next((o for o in outcomes if o.get("name") == away), None)

                    if mkey == "h2h" and ml_home is None:
                        if home_out and away_out:
                            ml_home = home_out.get("price")
                            ml_away = away_out.get("price")

                    elif mkey == "spreads" and rl_home is None:
                        if home_out and away_out:
                            rl_home = home_out.get("price")
                            rl_line = home_out.get("point", -1.5)
                            rl_away = away_out.get("price")

                    elif mkey == "totals" and total_line is None:
                        over_out = next((o for o in outcomes if o.get("name") == "Over"), None)
                        under_out = next((o for o in outcomes if o.get("name") == "Under"), None)
                        if over_out:
                            total_line = over_out.get("point")
                            total_over = over_out.get("price")
                            total_under = under_out.get("price") if under_out else None

                if ml_home and rl_home and total_line:
                    break  # Got all markets

            result.append({
                "event_id": event_id,
                "home_team": home,
                "away_team": away,
                "commence_time": commence,
                "moneyline": {
                    "home": ml_home,
                    "away": ml_away,
                    "home_implied_prob": _implied_prob(ml_home) if ml_home else None,
                    "away_implied_prob": _implied_prob(ml_away) if ml_away else None,
                } if ml_home else None,
                "run_line": {
                    "home_line": rl_line,
                    "home_price": rl_home,
                    "away_price": rl_away,
                } if rl_home else None,
                "total": {
                    "line": total_line,
                    "over_price": total_over,
                    "under_price": total_under,
                } if total_line else None,
            })

        await set_cache(cache_key, result, 1800)  # 30-min cache
        return result

    except Exception as e:
        print(f"Odds API error: {e}")
        return []


async def get_game_props(event_id: str) -> list:
    """
    Fetch player props for a specific game.
    Returns props like batter HR, total bases, pitcher strikeouts.
    """
    cache_key = f"odds:props:{event_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    PROP_MARKETS = [
        "batter_home_runs",
        "batter_total_bases",
        "batter_hits",
        "pitcher_strikeouts",
        "batter_rbis",
    ]

    try:
        props = []
        client = get_client()
        for market in PROP_MARKETS:
            r = await client.get(
                f"{ODDS_BASE}/sports/{SPORT}/events/{event_id}/odds",
                params={
                    "apiKey": ODDS_API_KEY,
                    "regions": "us",
                    "markets": market,
                    "oddsFormat": "american",
                },
                timeout=15
            )
            if r.status_code != 200:
                continue
            data = r.json()
            for book in data.get("bookmakers", [])[:1]:  # just first book
                for mkt in book.get("markets", []):
                    for outcome in mkt.get("outcomes", []):
                        props.append({
                            "market": market,
                            "player": outcome.get("description", outcome.get("name", "")),
                            "name": outcome.get("name", ""),   # Over/Under
                            "point": outcome.get("point"),
                            "price": outcome.get("price"),
                            "implied_prob": _implied_prob(outcome.get("price", -110)),
                        })

        await set_cache(cache_key, props, 1800)
        return props

    except Exception as e:
        print(f"Props API error: {e}")
        return []


async def match_game_odds(home_team: str, away_team: str) -> dict | None:
    """Find odds for a specific matchup from today's lines"""
    all_odds = await get_mlb_odds()
    if not all_odds:
        return None

    def normalize(name: str) -> str:
        # Strip city, keep last word (team nickname)
        return name.strip().split()[-1].lower()

    home_nick = normalize(home_team)
    away_nick = normalize(away_team)

    for game in all_odds:
        if normalize(game["home_team"]) == home_nick and normalize(game["away_team"]) == away_nick:
            return game
        # Also try reversed (some APIs flip home/away)
        if normalize(game["home_team"]) == away_nick and normalize(game["away_team"]) == home_nick:
            return game

    return None
