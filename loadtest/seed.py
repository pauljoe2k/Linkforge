"""Seed the dev database for load tests: one user + one slug.

Run before load tests:
    python loadtest/seed.py
"""

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.db import engine
from app.db.base import Base
from app.models import *  # noqa: F403,F401  registers every model on Base
from app.models.link import Link
from app.services import link_service
from app.services.user_service import DuplicateEmailError, create_user, get_user_by_email

LOAD_SLUG = "loadtest"
LOAD_EMAIL = "loadtest@example.com"


def main() -> int:
    Base.metadata.create_all(bind=engine)  # idempotent: only fills gaps
    db = sessionmaker(bind=engine)()
    try:
        try:
            user = create_user(db, LOAD_EMAIL, "super-secret-pass-9")
        except DuplicateEmailError:
            user = get_user_by_email(db, LOAD_EMAIL)
        assert user is not None

        existing_id = db.scalar(select(Link.id).where(Link.slug == LOAD_SLUG))
        if existing_id is None:
            link = link_service.create_link(
                db, user.id, "https://example.com/load-target", custom_slug=LOAD_SLUG
            )
        else:
            link = db.get(Link, existing_id)
        assert link is not None
        print(f"ready: slug={link.slug} target={link.target_url}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
