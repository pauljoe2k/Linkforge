from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.link import Link
from app.services import cache
from app.services.slugs import generate_unique_slug, slug_exists

NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Link not found",
)
SLUG_TAKEN = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Slug already taken",
)


def _get_owned_link(db: Session, link_id: int, user_id: int) -> Link:
    """Owner-scoped fetch. A foreign link id is indistinguishable from a
    nonexistent one (both 404) so ids are never leaked to strangers."""
    link = db.get(Link, link_id)
    if link is None or link.user_id != user_id:
        raise NOT_FOUND
    return link


def create_link(
    db: Session,
    user_id: int,
    target_url: str,
    custom_slug: str | None = None,
) -> Link:
    if custom_slug is not None:
        slug = custom_slug
        if slug_exists(db, slug):
            raise SLUG_TAKEN
    else:
        slug = generate_unique_slug(db)
    link = Link(user_id=user_id, slug=slug, target_url=target_url)
    db.add(link)
    try:
        db.commit()
    except Exception:  # unique index race: custom slug taken by concurrent insert
        db.rollback()
        raise SLUG_TAKEN from None
    return link


def list_links(
    db: Session,
    user_id: int,
    limit: int,
    offset: int,
) -> tuple[list[Link], int]:
    stmt = (
        select(Link)
        .where(Link.user_id == user_id)
        .order_by(Link.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(db.scalars(stmt))
    total = db.scalar(
        select(func.count()).select_from(Link).where(Link.user_id == user_id)
    )
    return items, int(total or 0)


def get_link(db: Session, link_id: int, user_id: int) -> Link:
    return _get_owned_link(db, link_id, user_id)


def update_link(
    db: Session,
    link_id: int,
    user_id: int,
    target_url: str | None = None,
    custom_slug: str | None = None,
    is_active: bool | None = None,
) -> Link:
    link = _get_owned_link(db, link_id, user_id)
    if custom_slug is not None and custom_slug != link.slug:
        if slug_exists(db, custom_slug):
            raise SLUG_TAKEN
        old_slug = link.slug
        link.slug = custom_slug
    else:
        old_slug = link.slug
    link.target_url = target_url if target_url is not None else link.target_url
    link.is_active = is_active if is_active is not None else link.is_active
    db.commit()
    # Any change that could affect resolution invalidates the cached
    # lookup for both the old and the new slug (the new slug may itself
    # have been cached from a previous owner). Next visit re-reads DB.
    cache.invalidate(old_slug)
    if custom_slug is not None and custom_slug != old_slug:
        cache.invalidate(custom_slug)
    return link


def delete_link(db: Session, link_id: int, user_id: int) -> None:
    link = _get_owned_link(db, link_id, user_id)
    slug = link.slug
    db.delete(link)
    db.commit()
    cache.invalidate(slug)


def get_active_link_by_slug(db: Session, slug: str) -> Link | None:
    link = db.scalar(select(Link).where(Link.slug == slug))
    if link is None or not link.is_active:
        return None
    return link
