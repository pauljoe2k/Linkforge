from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEVELOPMENT_JWT_SECRET = "dev-only-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://linkforge:linkforge@localhost:5432/linkforge"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = _DEVELOPMENT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 30

    # Redirect cache: how long a slug->target lookup survives in Redis.
    cache_redirect_ttl_seconds: int = 300
    # A/B switch for load tests: bypass the cache entirely (every redirect
    # reads Postgres). Also the emergency kill-switch in production.
    disable_redirect_cache: bool = False

    # Rate limits (fixed windows in the Day 4 module).
    api_rate_limit: int = 100  # writes/reads per user
    api_rate_window_seconds: int = 60
    redirect_rate_limit: int = 30  # redirects per client IP
    redirect_rate_window_seconds: int = 60

    environment: str = "development"

    @model_validator(mode="after")
    def require_production_jwt_secret(self) -> "Settings":
        if self.environment.lower() in {"prod", "production"} and (
            self.jwt_secret_key == _DEVELOPMENT_JWT_SECRET
            or len(self.jwt_secret_key) < 32
        ):
            raise ValueError(
                "Production requires a JWT_SECRET_KEY with at least 32 characters."
            )
        return self


settings = Settings()
