from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(
        examples=["alice@example.com"],
        description="Email used to sign in; stored lowercased",
    )
    # Min 8: avoids the most trivially brute-forceable secrets.
    # Max 128: Argon2 processes arbitrarily long inputs, but a cap prevents
    # someone sending a 10 MB "password" as a DoS vector.
    password: str = Field(
        min_length=8,
        max_length=128,
        examples=["super-secret-pass-9"],
    )


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr = Field(examples=["alice@example.com"])
    # Deliberately no min_length here: login failure must not change the
    # 422 shape users get for malformed bodies vs. the 401 they get for
    # wrong credentials.
    password: str = Field(max_length=128, examples=["super-secret-pass-9"])


class TokenOut(BaseModel):
    access_token: str = Field(examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."])
    token_type: str = Field(default="bearer", examples=["bearer"])
    expires_in: int = Field(examples=[1800], description="Access token lifetime in seconds")
