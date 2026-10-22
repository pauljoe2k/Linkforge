from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.user import User
from app.services.tokens import TokenDecodeError, decode_access_token

# auto_error=False lets us emit a single consistent 401 ourselves with a
# WWW-Authenticate header, instead of FastAPI's default 403 for a missing
# Authorization header (403 for "no header at all" is unauthenticated's
# classic FastAPI wart).
_bearer_scheme = HTTPBearer(auto_error=False)

DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)],
    db: DBSession,
) -> User:
    if credentials is None:
        raise _unauthorized()
    try:
        user_id = decode_access_token(credentials.credentials)
    except TokenDecodeError:
        raise _unauthorized() from None

    user = db.get(User, user_id)
    if user is None:
        # Token is cryptographically valid but the account vanished
        # (deleted after token issue): still 401, the session is invalid.
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
