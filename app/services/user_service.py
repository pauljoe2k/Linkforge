from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.passwords import hash_password, verify_password


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def create_user(db: Session, email: str, password: str) -> User:
    """Create a user with a normalized (lowercased) email.

    Raises DuplicateEmailError if the email is taken — detected both via
    a pre-check and defensively via the unique index IntegrityError, so a
    concurrent double-registration races into a 409, not a 500.
    """
    email = email.lower()
    if get_user_by_email(db, email) is not None:
        raise DuplicateEmailError(email)

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        orig = exc.orig
        constraint_name = getattr(getattr(orig, "diag", None), "constraint_name", None)
        if getattr(orig, "sqlstate", None) == "23505" and constraint_name == "ix_users_email":
            raise DuplicateEmailError(email) from None
        raise
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Return the user if the credentials are valid, else None.

    The two miss modes (unknown email, wrong password) collapse into None
    so the API can return one identical error and not leak which emails
    are registered.
    """
    email = email.lower()
    user = get_user_by_email(db, email)
    if user is None:
        # Burn comparable CPU time to a verification so a timing observer
        # cannot enumerate registered emails by response latency.
        hash_password(password)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


class DuplicateEmailError(Exception):
    """Raised when registering with an email that is already taken."""
