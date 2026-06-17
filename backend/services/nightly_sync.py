"""
Nightly Sync Worker — runs at 3:00 AM daily.

Steps:
  1. Find all predictions from yesterday with no actual_outcome.
  2. Fetch yesterday's boxscores from the MLB API.
  3. Mark each batter as 1 (HR) or 0 (no HR) in history.db.
  4. Count resolved rows; if >= MIN_SAMPLES, retrain the ML model.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from services.http_client import get_client

from db.history import get_pending_predictions, update_outcomes_bulk, get_training_data, get_prediction_count
from services.ml_engine import train_model, MIN_SAMPLES

logger = logging.getLogger(__name__)

from services.mlb_api import get_schedule, get_boxscore

async def _fetch_yesterday_hr_batters(game_date: str) -> set[int]:
    """
    Query the MLB Stats API for boxscores on game_date.
    Returns the set of batter IDs who hit at least one HR.
    """
    hr_batters: set[int] = set()
    try:
        games = await get_schedule(game_date)
        if not games:
            return hr_batters

        async def process_game_boxscore(game):
            game_pk = game.get("gamePk")
            try:
                boxscore = await get_boxscore(game_pk)
                teams = boxscore.get("teams", {})
                for side in ("home", "away"):
                    players = teams.get(side, {}).get("players", {})
                    for player_key, player_data in players.items():
                        stats = player_data.get("stats", {}).get("batting", {})
                        hr = int(stats.get("homeRuns", 0) or 0)
                        if hr >= 1:
                            pid = player_data.get("person", {}).get("id")
                            if pid:
                                hr_batters.add(pid)
            except Exception as e:
                logger.error("[Sync] Error fetching boxscore for game %s: %s", game_pk, e)

        await asyncio.gather(*[process_game_boxscore(g) for g in games])
    except Exception as e:
        logger.error("[Sync] Failed to fetch boxscores for %s: %s", game_date, e)

    return hr_batters


async def sync_yesterday_results():
    """Sync outcomes for yesterday's pending predictions."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info("[Sync] Syncing results for %s …", yesterday)

    pending = await get_pending_predictions(yesterday)
    if not pending:
        logger.info("[Sync] No pending predictions found for %s.", yesterday)
        return

    hr_batters = await _fetch_yesterday_hr_batters(yesterday)
    synced_at = datetime.now(timezone.utc).isoformat()
    synced = 0
    updates = []

    for pred in pending:
        outcome = 1 if pred["batter_id"] in hr_batters else 0
        updates.append((outcome, synced_at, pred["prediction_id"]))
        synced += 1

    if updates:
        await update_outcomes_bulk(updates)

    logger.info("[Sync] Updated %d predictions for %s.", synced, yesterday)

    # Retrain if we've hit the threshold
    total = await get_prediction_count()
    logger.info("[Sync] Total resolved predictions: %d / %d needed.", total, MIN_SAMPLES)
    if total >= MIN_SAMPLES:
        logger.info("[Sync] Threshold reached — retraining ML model …")
        training_data = await get_training_data()
        success = train_model(training_data)
        if success:
            logger.info("[Sync] Model retrained successfully.")
        else:
            logger.warning("[Sync] Model retraining skipped or failed.")


async def _scheduler_loop():
    """
    Background loop: wake up at the next 3:00 AM, run sync, then repeat.
    Runs inside the FastAPI lifespan so it exits when the server stops.
    """
    while True:
        now = datetime.now()
        target = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        logger.info("[Sync] Next nightly sync in %.0f seconds (at %s).", sleep_seconds, target)
        await asyncio.sleep(sleep_seconds)
        try:
            await sync_yesterday_results()
        except Exception as e:
            logger.error("[Sync] Nightly sync error: %s", e)


def start_nightly_scheduler():
    """Launch the scheduler as a background asyncio task."""
    asyncio.create_task(_scheduler_loop())
    logger.info("[Sync] Nightly sync scheduler started.")
