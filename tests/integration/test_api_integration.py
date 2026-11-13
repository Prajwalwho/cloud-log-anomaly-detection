"""API endpoints against the running stack (skipped if PostgreSQL is unreachable)."""
import re

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.api.app.config import ApiSettings
from backend.api.app.main import create_app

pytestmark = pytest.mark.integration
SETTINGS = ApiSettings()
MS_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


@pytest.fixture(scope="module")
def client():
    try:
        with psycopg.connect(SETTINGS.postgres_conninfo):
            pass
    except Exception:
        pytest.skip("PostgreSQL not reachable; start the stack with .\\scripts\\start.ps1 up")
    with TestClient(create_app(SETTINGS)) as test_client:
        yield test_client


def test_health_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok",
                               "components": {"postgres": "ok", "elasticsearch": "ok", "kafka": "ok"}}


def test_services_include_the_seeded_five(client):
    names = {s["name"] for s in client.get("/api/v1/services").json()}
    assert {"api-gateway", "auth-service", "order-service", "payment-service", "inventory-service"} <= names


def test_timestamps_follow_the_contract(client):
    service = client.get("/api/v1/services").json()[0]
    assert MS_TIMESTAMP.match(service["created_at"]), service["created_at"]


def test_models_and_active_model_agree(client):
    models = client.get("/api/v1/models").json()
    active = client.get("/api/v1/models/active")
    assert active.status_code == 200
    body = active.json()
    assert body["is_active"] is True
    assert sum(m["is_active"] for m in models) == 1
    assert body["id"] in {m["id"] for m in models}
    assert MS_TIMESTAMP.match(body["trained_at"])