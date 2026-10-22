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


def test_openapi_document_builds(client: TestClient):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Linkforge API"
