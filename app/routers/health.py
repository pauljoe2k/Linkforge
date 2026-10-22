from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.db import engine
from app.core.redis import get_redis_client

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    time: datetime


@router.get(
    "/health",
    summary="Liveness probe with dependency status",
    response_model=HealthResponse,
)
def health(response: Response) -> HealthResponse:
    """Used by Render health checks and local smoke tests.

    Always answers 200 so the process itself is observed as alive;
    per-dependency status tells you which one is unhappy.
    """
    db_status = "down"
    redis_status = "down"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "up"
    except Exception:
        pass

    try:
        get_redis_client().ping()
        redis_status = "up"
    except Exception:
        pass

    overall = "ok" if db_status == "up" else "degraded"
    if db_status == "down":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status=overall, db=db_status, redis=redis_status, time=datetime.now(tz=UTC)
    )
