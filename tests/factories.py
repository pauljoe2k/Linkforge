"""Row factories: build users/links/clicks directly through the models
(think factory_boy-lite). Services like create_link prefer the real code
path where we want to test it; factories are for seeding analytics and
edge-case data fast."""

from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.click import Click
from app.models.link import Link
from app.models.user import User


class Factories:
    def __init__(self, engine):
        self._engine = engine

    @contextmanager
    def session(self):
        db = Session(bind=self._engine)
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def user(self, email: str, password_hash: str = "factory-hash") -> User:
        with self.session() as db:
            user = User(email=email, password_hash=password_hash)
            db.add(user)
            db.commit()
            return user

    def link(
        self,
        user_id: int,
        slug: str,
        target_url: str = "https://example.com/factory",
        is_active: bool = True,
    ) -> Link:
        with self.session() as db:
            link = Link(user_id=user_id, slug=slug, target_url=target_url, is_active=is_active)
            db.add(link)
            db.commit()
            return link

    def clicks(
        self,
        link_id: int,
        rows: list[tuple[datetime, str | None, str]],
    ) -> None:
        """rows: (clicked_at, referrer, device_type)."""
        with self.session() as db:
            for at, referrer, device in rows:
                db.add(
                    Click(
                        link_id=link_id,
                        clicked_at=at,
                        referrer=referrer,
                        device_type=device,
                    )
                )
            db.commit()

    @staticmethod
    def utc(y: int, m: int, d: int, h: int = 12) -> datetime:
        return datetime(y, m, d, h, tzinfo=UTC)
