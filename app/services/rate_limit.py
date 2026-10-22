"""Fixed-window rate limiting on Redis counters.

Fixed window: counter key rate:{scope}:{principal} with the window id
baked in, INCR on each hit, EXPIRE on first hit of a window. When the
count exceeds the limit the scope is refused until the window laps.

Checked trade-off (fixed vs sliding):
- Sliding window (log/Tokyo-drift-free sliding counter) smooths the
  boundary burst: fixed windows allow up to 2x limit across a window
  boundary (limit in each of two adjacent halves). Sliding costs more
  Redis round-trips or a ZSET with sorted set memory per principal.
- For this MVP the fixed window's worst case is a burst of 2x the
  configured limit for a few seconds around the boundary — tolerable,
  and precision energy is better spent elsewhere. The module hides the
  choice behind hit() so a sliding implementation can drop in later
  without touching callers.
"""

import logging

from app.core import redis as redis_module

logger = logging.getLogger(__name__)


def hit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Count one hit against (key, limit, window). -> (allowed, retry_after).

    retry_after is the seconds left on the current window (only meaningful
    when not allowed). Fails OPEN: if Redis is unreachable we allow the
    request — abuse protection degrades, availability does not.
    """
    try:
        client = redis_module.get_redis_client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_seconds)
        if count > limit:
            ttl = client.ttl(key)
            return False, max(ttl, 1)
        return True, 0
    except Exception:
        logger.warning("rate limiter unavailable; failing open for %r", key, exc_info=True)
        return True, 0
