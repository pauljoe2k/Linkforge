import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_a_strong_jwt_secret():
    with pytest.raises(ValidationError, match="Production requires a JWT_SECRET_KEY"):
        Settings(environment="production")


def test_production_accepts_a_generated_secret():
    config = Settings(environment="production", jwt_secret_key="x" * 44)

    assert config.environment == "production"
