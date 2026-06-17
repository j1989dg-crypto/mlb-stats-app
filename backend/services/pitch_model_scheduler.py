"""
Pitch Model Scheduler — runs nightly auto-retraining at 2:00 AM daily.
"""
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def _scheduler_loop():
    """
    Background loop: wake up at the next 2:00 AM, run pitch models retrain, then repeat.
    Runs inside the FastAPI lifespan.
    """
    # Import here to avoid circular imports
    from routers.live_pitches import run_pitch_model_training
    
    while True:
        now = datetime.now()
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        logger.info("[PitchScheduler] Next nightly retrain in %.0f seconds (at %s).", sleep_seconds, target)
        await asyncio.sleep(sleep_seconds)
        try:
            logger.info("[PitchScheduler] Starting nightly auto-retrain of pitch models...")
            success = await run_pitch_model_training()
            logger.info("[PitchScheduler] Nightly auto-retrain completed. Success: %s", success)
        except Exception as e:
            logger.error("[PitchScheduler] Nightly auto-retrain error: %s", e)

def start_pitch_model_scheduler():
    """Launch the pitch model retrain scheduler as a background task."""
    asyncio.create_task(_scheduler_loop())
    logger.info("[PitchScheduler] Nightly pitch model scheduler started.")
