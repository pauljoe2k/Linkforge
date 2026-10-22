from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings


class TokenDecodeError(Exception):
    """Raised by create/decode helpers; callers map it to 401."""


def create_access_token(user_id: int) -> tuple[str, int]:
    """Return (encoded_token, expires_in_seconds).

    Payload holds only identity and temporal claims — sub, iat, exp, type.
    Nothing user-controllable or personal beyond the internal id: if a token
    leaks, the blast radius is "someone can act as this user until expiry",
    not "someone's PII leaked".
    """
    now = datetime.now(UTC)
    expires_delta = timedelta(minutes=settings.jwt_expires_minutes)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_delta,
        "type": "access",
    }
    encoded = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> int:
    """Return the user id from a valid access type token.

    jwt.decode already rejects tokens whose `exp` has passed, raises on
    bad signatures, and we additionally require type == "access" so a
    token minted for another purpose can never be replayed here.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenDecodeError(str(exc)) from exc

    if payload.get("type") != "access":
        raise TokenDecodeError("wrong token type")

    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise TokenDecodeError("invalid sub claim") from exc
