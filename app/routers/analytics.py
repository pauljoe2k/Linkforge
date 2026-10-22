from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.api.guards import api_rate_guard
from app.schemas.analytics import (
    DailyOut,
    DailyPoint,
    ReferrerPoint,
    ReferrersOut,
    SummaryOut,
)
from app.services import analytics_service

router = APIRouter(
    prefix="/links/{link_id}/analytics",
    tags=["analytics"],
    dependencies=[Depends(api_rate_guard)],
    responses={
        # Ownership violations intentionally do NOT differentiate from
        # missing links: both 404, one body, so probing ids reveals
        # nothing. Rationale documented in the README (Day 8).
        404: {"description": "Link not found or not owned by you"},
        429: {"description": "API rate limit exceeded (per user)"},
    },
)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Link not found",
    )


@router.get(
    "/summary",
    response_model=SummaryOut,
    summary="Total clicks and device breakdown",
)
def summary(link_id: int, user: CurrentUser, db: DBSession) -> SummaryOut:
    try:
        total, devices = analytics_service.get_summary(db, link_id, user.id)
    except KeyError:
        raise _not_found() from None
    return SummaryOut(total_clicks=total, devices=devices)


@router.get(
    "/daily",
    response_model=DailyOut,
    summary="Clicks per day over a date range (UTC days, both ends inclusive)",
)
def daily(
    link_id: int,
    user: CurrentUser,
    db: DBSession,
    start: date = Query(..., examples=["2026-10-01"]),
    end: date = Query(..., examples=["2026-10-08"]),
) -> DailyOut:
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start must be on or before end",
        )
    try:
        rows = analytics_service.get_daily(db, link_id, user.id, start, end)
    except KeyError:
        raise _not_found() from None
    return DailyOut(
        days=[DailyPoint(day=day.date(), clicks=int(clicks)) for day, clicks in rows]
    )


@router.get(
    "/referrers",
    response_model=ReferrersOut,
    summary="Top referrers, most-clicked first (NULL referrer -> 'direct')",
)
def referrers(
    link_id: int,
    user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=10, ge=1, le=100),
) -> ReferrersOut:
    try:
        rows = analytics_service.get_referrers(db, link_id, user.id, limit)
    except KeyError:
        raise _not_found() from None
    return ReferrersOut(
        referrers=[ReferrerPoint(referrer=str(r), clicks=int(c)) for r, c in rows]
    )
