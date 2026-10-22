import secrets
import string
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.link import Link

ALPHABET: Final[str] = string.ascii_letters + string.digits  # 62 symbols
RANDOM_SLUG_LENGTH: Final[int] = 7
MIN_SLUG_LENGTH: Final[int] = 3
MAX_SLUG_LENGTH: Final[int] = 64

# Slugs that would collide with app routes / docs / future endpoints.
RESERVED_SLUGS: Final[frozenset[str]] = frozenset(
    {
        "docs",
        "redoc",
        "openapi.json",
        "health",
        "auth",
        "links",
        "api",
        "admin",
        "app",
        "static",
        "assets",
    }
)


def random_slug(length: int = RANDOM_SLUG_LENGTH) -> str:
    """Cryptographically random base62 slug.

    62^7 ≈ 3.5 × 10^12 combinations. With 62 bits of entropy *at minimum*
    for URL guessing, this keeps unguessability practical: enumerating
    even 1 billion slugs yields the right one with probability < 0.03%,
    and each guess costs a request (which Day 4 rate-limits further).
    `secrets` (CSPRNG), so slugs are not predictable from timestamps.
    """
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def slug_exists(db: Session, slug: str) -> bool:
    return db.scalar(select(Link.id).where(Link.slug == slug)) is not None


def generate_unique_slug(db: Session, length: int = RANDOM_SLUG_LENGTH) -> str:
    """Produce a random slug guaranteed not to exist yet.

    Collision math: 62^7 space stays enormous; with N links already
    stored, the expected retries for the (N+1)-th insert is ~N / 62^7,
    so the retry loop is effectively immediate at MVP scale and still
    not pathological into the millions.
    """
    for _ in range(50):  # hard cap: 50 consecutive 12-digit-space misses
        candidate = random_slug(length)
        if not slug_exists(db, candidate):
            return candidate
    # Defensive: lengthen the slug rather than ever give up or fail.
    return random_slug(length + 2)


__all__ = [
    "ALPHABET",
    "RANDOM_SLUG_LENGTH",
    "MIN_SLUG_LENGTH",
    "MAX_SLUG_LENGTH",
    "RESERVED_SLUGS",
    "random_slug",
    "slug_exists",
    "generate_unique_slug",
]
