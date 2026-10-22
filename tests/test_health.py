"""Smoke test proving the app wires up and OpenAPI generates."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint_responds(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert {"status", "db", "redis", "time"} <= set(body)


def test_health_fails_when_database_is_unavailable(client: TestClient, monkeypatch):
    def fail_connect():
        raise ConnectionError("database unavailable")

    monkeypatch.setattr("app.routers.health.engine.connect", fail_connect)

    resp = client.get("/health")

    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
    assert resp.json()["db"] == "down"


def test_frontend_is_served_at_root(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Your links, at a glance." in resp.text


def test_openapi_document_builds(client: TestClient):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Linkforge API"
