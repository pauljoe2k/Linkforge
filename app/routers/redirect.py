import json
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.api.deps import DBSession
from app.api.guards import redirect_rate_guard
from app.core.config import settings
from app.models.click import Click
from app.services import cache as redirect_cache
from app.services import link_service
from app.services.device import classify_device

router = APIRouter(
    tags=["redirect"],
    dependencies=[Depends(redirect_rate_guard)],
    responses={429: {"description": "Redirect rate limit exceeded (per IP)"}},
)

# 302 (not 301): browsers and proxies cache 301s indefinitely, which
# would silently drop repeat-visit clicks from analytics and serve stale
# targets after an update. 302 keeps analytics fidelity; the cost of a
# second hop is what having link analytics at all buys us.

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Short link not found",
)


def _log_click(link_id: int, referrer: str | None, device_type: str) -> None:
    """Persist one visit. Runs as a background task so the redirect
    response never waits on an INSERT; a failed click-log costs analytics,
    never the visitor's redirect. Own session because the request-scoped
    one is closed by the time background tasks run."""
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        db.add(
            Click(
                link_id=link_id,
                clicked_at=datetime.now(UTC),
                referrer=referrer,
                device_type=device_type,
            )
        )
        db.commit()
    finally:
        db.close()


@router.get(
    "/{slug}",
    summary="Resolve a short link (public)",
    responses={
        302: {"description": "Redirects to the destination"},
        404: {"description": "Unknown slug (or link deactivated)"},
    },
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
)
def redirect(
    slug: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> RedirectResponse:
    referrer = request.headers.get("referer")
    device = classify_device(request.headers.get("user-agent"))
    link_id: int
    target_url: str

    # Hot path: Redis first. The cached value is JSON that lets a hit log
    # the click WITHOUT touching Postgres at all. Only active links are
    # cached; updates and deletes invalidate the key outright.
    hit_payload = None
    if not settings.disable_redirect_cache:  # A/B kill-switch for load tests
        hit_payload = redirect_cache.get_cached_target(slug)
    if hit_payload is not None:
        payload = json.loads(hit_payload)
        link_id = int(payload["link_id"])
        target_url = payload["target_url"]
    else:
        link = link_service.get_active_link_by_slug(db, slug)
        if link is None:
            raise _NOT_FOUND
        link_id = link.id
        target_url = link.target_url
        if not settings.disable_redirect_cache:
            redirect_cache.set_cached_target(
                slug,
                json.dumps({"link_id": link.id, "target_url": target_url}),
                settings.cache_redirect_ttl_seconds,
            )

    background_tasks.add_task(_log_click, link_id, referrer, device)
    return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
