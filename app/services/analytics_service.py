"""Analytics aggregations, all computed in SQL (not Python) so the
database does the grouping: GROUP BY ran serverside is the difference
between streaming 10 aggregate rows and streaming 10 million clicks."""

from collections.abc import Sequence

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.click import Click
from app.models.link import Link

NOT_OWNED_OR_MISSING = "link_not_found"


def _assert_owned(db: Session, link_id: int, user_id: int) -> None:
    link = db.get(Link, link_id)
    if link is None or link.user_id != user_id:
        raise KeyError(link_id)


def get_summary(db: Session, link_id: int, user_id: int) -> tuple[int, dict[str, int]]:
    """(total_clicks, device_counts). One query: COUNT + SUM(CASE)."""
    _assert_owned(db, link_id, user_id)
    count_all = func.count()
    stmt = select(
        count_all.label("total"),
        func.sum(
            case((Click.device_type == "desktop", 1), else_=0)
        ).label("desktop"),
        func.sum(
            case((Click.device_type == "mobile", 1), else_=0)
        ).label("mobile"),
        func.sum(
            case((Click.device_type == "tablet", 1), else_=0)
        ).label("tablet"),
        func.sum(
            case((Click.device_type == "other", 1), else_=0)
        ).label("other"),
    ).where(Click.link_id == link_id)

    row = db.execute(stmt).one()
    total = int(row[0] or 0)
    devices = {k: int(getattr(row, k) or 0) for k in ("desktop", "mobile", "tablet", "other")}
    return total, devices


def get_daily(
    db: Session,
    link_id: int,
    user_id: int,
    start,
    end,
) -> Sequence[tuple]:
    """Clicks grouped per calendar day (UTC), inclusive [start, end].
    Empty range or no traffic in range -> []."""
    _assert_owned(db, link_id, user_id)
    day = func.date_trunc("day", Click.clicked_at).label("day")
    # end date is inclusive: hours of that date up to 23:59:59.999...,
    # bounded tightly to also discard clicks before `start` 00:00.
    stmt = (
        select(day, func.count().label("clicks"))
        .where(
            Click.link_id == link_id,
            func.date_trunc("day", Click.clicked_at) >= start,
            func.date_trunc("day", Click.clicked_at) <= end,
        )
        .group_by(day)
        .order_by(day)
    )
    rows: Sequence[tuple] = db.execute(stmt).all()
    return rows


def get_referrers(
    db: Session,
    link_id: int,
    user_id: int,
    limit: int,
) -> Sequence[tuple]:
    """Top `limit` referrers by click count. NULL referrer rows are grouped
    together and returned under ('direct', n)."""
    _assert_owned(db, link_id, user_id)
    stmt = (
        select(
            Click.referrer.label("referrer"),
            func.count().label("clicks"),
        )
        .where(Click.link_id == link_id)
        .group_by(Click.referrer)
        .order_by(func.count().desc(), func.max(Click.referrer).asc())
        .limit(limit)
    )
    rows: Sequence[tuple] = db.execute(stmt).all()
    return [((r[0] if r[0] is not None else "direct"), r[1]) for r in rows]


def get_total_clicks(db: Session, link_id: int, user_id: int) -> int:
    _assert_owned(db, link_id, user_id)
    return int(
        db.scalar(select(func.count()).where(Click.link_id == link_id)) or 0
    )
