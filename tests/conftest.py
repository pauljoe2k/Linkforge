import os
import urllib.parse

import pytest

# ---------------------------------------------------------------------------
# Database selection MUST happen before importing anything that builds the
# SQLAlchemy engine: we redirect the test run to a dedicated linkforge_test
# database derived from DATABASE_URL, so the dev database (and CI's service
# database) is never touched by tests.
# ---------------------------------------------------------------------------
from app.core.config import settings as _settings  # noqa: E402

_parts = urllib.parse.urlsplit(_settings.database_url)
_test_db_name = (_parts.path or "/").split("/")[-1] + "_test"
_test_url = urllib.parse.urlunsplit(
    _parts._replace(path="/" + _test_db_name)
)
os.environ["DATABASE_URL"] = _test_url


def _ensure_test_database() -> None:
    """CREATE DATABASE if missing. Connects to the maintenance 'postgres'
    database with the same credentials as the main DATABASE_URL."""
    import psycopg

    # psycopg.connect takes a plain DSN — strip the SQLAlchemy driver tag.
    plain_maintenance = _settings.database_url.replace(
        "+psycopg", ""
    ).rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(plain_maintenance, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (_test_db_name,)
        ).fetchone()
        if exists is None:
            conn.execute(f'CREATE DATABASE "{_test_db_name}"')


_ensure_test_database()

# Now the app modules are safe to import: engine binds to the TEST database.
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core import redis as redis_module  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Schema in the test database for the session, dropped at teardown."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate before AND after each test.

    Why truncation instead of rollback-per-test: request-scoped sessions
    (get_db), service commits, and the background click-logger (its OWN
    SessionLocal) all write through separate connections. A single outer
    transaction cannot see or roll back those cross-connection writes --
    truncate-per-test gives exactly the same isolation guarantee without
    fighting the app's real session topology. (SQLAlchemy's
    create_savepoint/rollback pattern only isolates sessions that agree to
    join the same Connection; ours do not, by design, because production
    behavior is what we're testing.)
    """
    _truncate()
    yield
    _truncate()


def _truncate():
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE users, links, clicks RESTART IDENTITY CASCADE")
        )
    # Rate-limit counters and redirect-cache entries must not leak between
    # tests either: user ids restart at 1, so a leaked counter IS a new
    # test's counter. Best-effort when Redis is not running.
    _flush_redis()


def _flush_redis():
    """Best-effort: no Redis running = nothing to flush, tests still pass."""
    try:
        redis_module.get_redis_client().flushall()
    except Exception:
        pass


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def make_auth(client):
    """Factory: creates a user + logs in, returns bearer headers.

    Usage: headers = make_auth()  or  make_auth("bob@example.com")
    """
    import itertools

    counter = itertools.count(1)

    def _factory(email: str | None = None, password: str = "super-secret-pass-9"):
        email = email or f"user{next(counter)}@example.com"
        client.post("/auth/register", json={"email": email, "password": password})
        token = client.post(
            "/auth/login", json={"email": email, "password": password}
        ).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _factory


@pytest.fixture
def factories():
    """Model-level factories for seeding rows directly (analytics tests)."""
    from tests.factories import Factories

    yield Factories(engine)
