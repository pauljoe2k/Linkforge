"""Rate-limit guard dependencies wiring settings into the two scopes."""

from fastapi import HTTPException, Request, status

from app.api.deps import CurrentUser
from app.core.config import settings
from app.services.rate_limit import hit


def _refused(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded, slow down",
        headers={"Retry-After": str(retry_after)},
    )


def api_rate_guard(user: CurrentUser) -> None:
    """Router-level dependency on the authenticated API (/links)."""
    allowed, retry_after = hit(
        f"rate:api:{user.id}",
        limit=settings.api_rate_limit,
        window_seconds=settings.api_rate_window_seconds,
    )
    if not allowed:
        raise _refused(retry_after)


def redirect_rate_guard(request: Request) -> None:
    """Router-level dependency on the public redirect endpoint, keyed by
    direct peer IP for the MVP; behind a proxy this must move to the
    rightmost X-Forwarded-For hop."""
    client = request.client
    ip = client.host if client is not None else "unknown"
    allowed, retry_after = hit(
        f"rate:ip:{ip}",
        limit=settings.redirect_rate_limit,
        window_seconds=settings.redirect_rate_window_seconds,
    )
    if not allowed:
        raise _refused(retry_after)
