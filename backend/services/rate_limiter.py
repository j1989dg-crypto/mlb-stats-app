"""
Gemini rate limiter — prevents RPM and daily quota exhaustion.

Two-layer protection:
  1. Semaphore: caps simultaneous in-flight Gemini calls (default: 2)
  2. Token bucket: enforces a per-minute request ceiling (default: 8 RPM)

Adjust MAX_CONCURRENT and RPM_LIMIT to match your Gemini quota tier.
Paid tier defaults: gemini-2.5-flash allows 10 RPM on the default quota.
We use 8 RPM to leave headroom.
"""

import asyncio
import time
import logging

logger = logging.getLogger(__name__)

# ── Config (tune to your quota) ───────────────────────────────────────────────
MAX_CONCURRENT = 2   # max simultaneous Gemini calls in-flight
RPM_LIMIT      = 8   # max calls per 60-second rolling window
# ─────────────────────────────────────────────────────────────────────────────

_semaphore: asyncio.Semaphore | None = None
_call_timestamps: list[float] = []
_bucket_lock: asyncio.Lock | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    return _semaphore


def _get_lock() -> asyncio.Lock:
    global _bucket_lock
    if _bucket_lock is None:
        _bucket_lock = asyncio.Lock()
    return _bucket_lock


async def _wait_for_token() -> None:
    """
    Block until there is capacity in the rolling 60-second window.
    Prunes timestamps older than 60s, then sleeps if the window is full.
    """
    lock = _get_lock()
    async with lock:
        while True:
            now = time.monotonic()
            # Drop timestamps outside the 60-second window
            cutoff = now - 60.0
            while _call_timestamps and _call_timestamps[0] < cutoff:
                _call_timestamps.pop(0)

            if len(_call_timestamps) < RPM_LIMIT:
                _call_timestamps.append(now)
                return

            # Window is full — sleep until the oldest call ages out
            wait = 60.0 - (now - _call_timestamps[0]) + 0.1
            logger.info(f"[RateLimiter] RPM cap reached ({RPM_LIMIT}/min). Waiting {wait:.1f}s...")
            await asyncio.sleep(wait)


async def gemini_call(coro_fn, *args, **kwargs):
    """
    Wrap any async Gemini call with rate limiting + concurrency control.

    Usage:
        result = await gemini_call(my_async_fn, arg1, arg2, kwarg=val)

    Or with a lambda for inline calls:
        result = await gemini_call(lambda: model.generate_content(...))
    """
    await _wait_for_token()
    async with _get_semaphore():
        logger.debug("[RateLimiter] Acquired semaphore slot — calling Gemini")
        return await coro_fn(*args, **kwargs)
