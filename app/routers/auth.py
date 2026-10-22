from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.user import LoginRequest, TokenOut, UserCreate, UserRead
from app.services import tokens
from app.services.user_service import DuplicateEmailError, authenticate, create_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRead,
    summary="Register a new user",
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Validation error (bad email, short password)"},
    },
)
def register(user_in: UserCreate, db: DBSession) -> UserRead:
    try:
        user = create_user(db, user_in.email, user_in.password)
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Log in and receive a JWT access token",
    responses={
        401: {
            "description": "Invalid credentials (identical for unknown email and wrong password)",
        },
        422: {"description": "Validation error (malformed body)"},
    },
)
def login(body: LoginRequest, db: DBSession) -> TokenOut:
    user = authenticate(db, body.email, body.password)
    if user is None:
        # Identical error for unknown email and wrong password.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    encoded, expires_in = tokens.create_access_token(user.id)
    return TokenOut(access_token=encoded, expires_in=expires_in)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Current authenticated user",
    responses={401: {"description": "Invalid, missing, expired, or forged bearer token"}},
)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
