import redis as redis_lib

from app.core.config import settings

_client: redis_lib.Redis | None = None


def get_redis_client() -> redis_lib.Redis:
    """Lazily create a process-wide Redis client with socket timeouts."""
    global _client
    if _client is None:
        _client = redis_lib.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _client
