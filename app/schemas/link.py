import re
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.slugs import RESERVED_SLUGS

MAX_TARGET_URL_LENGTH = 2048

# MVP allowlist: only web origins are valid targets. Everything else
# (javascript:, data:, file:, ftp:, mailto:, tel:...) is rejected so no
# crafted short link can open a non-web handler or execute script content.
ALLOWED_SCHEMES = frozenset({"http", "https"})

# Keep the custom slug alphabet deliberately boring: display-safe,
# case-insensitively unique, and guaranteed not to shadow API paths.
# (Length bounded by MAX_SLUG_LENGTH = 64: pattern matches 3-64 chars.)
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$")


def validate_target_url(value: str) -> str:
    """Shared validator: scheme allowlist + host + length. Raises ValueError."""
    value = value.strip()
    if not value:
        raise ValueError("target_url cannot be empty")
    if len(value) > MAX_TARGET_URL_LENGTH:
        raise ValueError(f"target_url exceeds {MAX_TARGET_URL_LENGTH} characters")
    parts = urlsplit(value)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError("target_url scheme must be http or https")
    if not parts.netloc:
        raise ValueError("target_url must include a host")
    return value


def validate_custom_slug(value: str | None) -> str | None:
    """Shared validator: normalizes to lowercase, pattern + reserved list."""
    if value is None:
        return None
    value = value.lower()
    if not SLUG_PATTERN.fullmatch(value):
        raise ValueError(
            "custom_slug must be 3-64 chars of letters, digits, - or _ "
            "and start/end alphanumeric"
        )
    if value in RESERVED_SLUGS:
        raise ValueError(f"custom_slug '{value}' is reserved")
    return value


class LinkCreate(BaseModel):
    target_url: str = Field(
        description="Destination URL to redirect visitors to",
        examples=["https://example.com/very/long/post"],
    )
    custom_slug: str | None = Field(
        default=None,
        description="Custom slug (3-64 chars, letters/digits/-/_). "
        "Omit for a random 7-character slug.",
        examples=[None, "my-launch-page"],
    )

    @field_validator("target_url")
    def _check_url(cls, v: object) -> object:
        return validate_target_url(v) if isinstance(v, str) else v

    @field_validator("custom_slug")
    def _check_slug(cls, v: object) -> object:
        return validate_custom_slug(v) if isinstance(v, str | None) else v


class LinkUpdate(BaseModel):
    target_url: str | None = Field(
        default=None,
        description="New destination URL (optional)",
    )
    custom_slug: str | None = Field(
        default=None,
        description="New slug (optional)",
    )
    is_active: bool | None = Field(
        default=None,
        description="Deactivated links stop redirecting (they keep their click history)",
    )

    @field_validator("target_url")
    def _check_url(cls, v: object) -> object:
        return validate_target_url(v) if isinstance(v, str) else v

    @field_validator("custom_slug")
    def _check_slug(cls, v: object) -> object:
        return validate_custom_slug(v) if isinstance(v, str | None) else v


class LinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    target_url: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LinkListOut(BaseModel):
    items: list[LinkRead]
    total: int
    limit: int
    offset: int
