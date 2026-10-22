"""Redis cache for the redirect hot path.

Key layout:   redirect:{slug} -> target_url (plain string, TTL'd)
Hit-rate wins: the redirect endpoint is the only endpoint anything hits
more than writes, so this cache is worth keeping as plain as possible.

Failure policy: Redis down = cache transparently misses (fail-open) and
every request walks the DB. A cache must never turn a healthy backend
into a broken one — losing the cache is a slowdown, not an outage.
"""

import logging

from app.core import redis as redis_module

logger = logging.getLogger(__name__)

_PREFIX = "redirect:"


def _client():
    # Lazy lookup (not import-time binding) so tests can simulate outages
    # via monkeypatch and callers can swap the client at runtime.
    return redis_module.get_redis_client()


def get_cached_target(slug: str) -> str | None:
    """Target URL for the slug, or None on miss/Redis-down."""
    try:
        return _client().get(_PREFIX + slug)
    except Exception:
        logger.warning("redirect cache read failed for %r", slug, exc_info=True)
        return None


def set_cached_target(slug: str, target_url: str, ttl_seconds: int) -> None:
    try:
        _client().set(_PREFIX + slug, target_url, ex=ttl_seconds)
    except Exception:
        logger.warning("redirect cache write failed for %r", slug, exc_info=True)


def invalidate(slug: str) -> None:
    """Drop the cached value (best effort). Next visit repopulates from DB.
    Correct because invalidation removes the key outright — a deactivated
    or retargeted link can never serve its old redirect from cache."""
    try:
        _client().delete(_PREFIX + slug)
    except Exception:
        logger.warning("redirect cache invalidate failed for %r", slug, exc_info=True)
