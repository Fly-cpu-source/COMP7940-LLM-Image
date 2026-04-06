"""
rate_limiter.py — Per-user rate limiting backed by Redis.

Falls back to in-memory limiting if Redis is unavailable.
"""

from __future__ import annotations

import datetime
import logging
import os

logger = logging.getLogger(__name__)

RATE_LIMIT = int(os.getenv("RATE_LIMIT", "3"))
RATE_WINDOW = int(os.getenv("RATE_WINDOW_SECONDS", "60"))

# ── Redis client (lazy init) ──────────────────────────────────────────────────

_redis = None


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis as redis_lib
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis = redis_lib.from_url(url, decode_responses=True)
        _redis.ping()
        logger.info("Redis connected at %s", url)
    except Exception as exc:
        logger.warning("Redis unavailable (%s). Falling back to in-memory rate limit.", exc)
        _redis = None
    return _redis


# ── In-memory fallback ────────────────────────────────────────────────────────

_memory_store: dict[int, list[datetime.datetime]] = {}


def _check_memory(user_id: int) -> bool:
    now = datetime.datetime.utcnow()
    window_start = now - datetime.timedelta(seconds=RATE_WINDOW)
    history = [t for t in _memory_store.get(user_id, []) if t > window_start]
    if len(history) >= RATE_LIMIT:
        _memory_store[user_id] = history
        return True
    history.append(now)
    _memory_store[user_id] = history
    return False


# ── Public API ────────────────────────────────────────────────────────────────

def is_rate_limited(user_id: int) -> bool:
    """Return True if the user has exceeded the rate limit."""
    r = _get_redis()
    if r is None:
        return _check_memory(user_id)
    try:
        key = f"rate:{user_id}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, RATE_WINDOW)
        count, _ = pipe.execute()
        if count > RATE_LIMIT:
            logger.info("Rate limit hit for user %s (count=%s)", user_id, count)
            return True
        return False
    except Exception as exc:
        logger.warning("Redis rate check failed (%s). Falling back to in-memory.", exc)
        return _check_memory(user_id)
