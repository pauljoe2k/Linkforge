from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DBSession
from app.api.guards import api_rate_guard
from app.schemas.link import LinkCreate, LinkListOut, LinkRead, LinkUpdate
from app.services import link_service

router = APIRouter(
    prefix="/links",
    tags=["links"],
    dependencies=[Depends(api_rate_guard)],
    responses={429: {"description": "API rate limit exceeded (per user)"}},
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=LinkRead,
    summary="Create a short link",
    responses={
        409: {"description": "Custom slug already taken"},
        422: {"description": "Bad target_url or custom_slug"},
    },
)
def create_link(body: LinkCreate, user: CurrentUser, db: DBSession) -> LinkRead:
    link = link_service.create_link(
        db,
        user_id=user.id,
        target_url=body.target_url,
        custom_slug=body.custom_slug,
    )
    return LinkRead.model_validate(link)


@router.get(
    "",
    response_model=LinkListOut,
    summary="List the current user's links (paginated, newest first)",
)
def list_links(
    user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> LinkListOut:
    items, total = link_service.list_links(db, user_id=user.id, limit=limit, offset=offset)
    return LinkListOut(
        items=[LinkRead.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{link_id}",
    response_model=LinkRead,
    summary="Fetch one of your links by id",
    responses={404: {"description": "Link not found (or owned by someone else)"}},
)
def get_link(link_id: int, user: CurrentUser, db: DBSession) -> LinkRead:
    return LinkRead.model_validate(link_service.get_link(db, link_id, user.id))


@router.patch(
    "/{link_id}",
    response_model=LinkRead,
    summary="Update target URL, slug, or active state",
    responses={
        404: {"description": "Link not found (or owned by someone else)"},
        409: {"description": "New slug already taken"},
    },
)
def update_link(
    link_id: int,
    body: LinkUpdate,
    user: CurrentUser,
    db: DBSession,
) -> LinkRead:
    link = link_service.update_link(
        db,
        link_id=link_id,
        user_id=user.id,
        target_url=body.target_url,
        custom_slug=body.custom_slug,
        is_active=body.is_active,
    )
    return LinkRead.model_validate(link)


@router.delete(
    "/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of your links (click history evaporates with it)",
    responses={404: {"description": "Link not found (or owned by someone else)"}},
)
def delete_link(link_id: int, user: CurrentUser, db: DBSession) -> None:
    link_service.delete_link(db, link_id, user.id)
