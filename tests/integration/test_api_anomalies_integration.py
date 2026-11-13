"""
Anomaly endpoints against the running stack, with their own test data (2001-01-01, removed afterwards):
three anomalies in PostgreSQL and two log events in Elasticsearch.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from elasticsearch import Elasticsearch
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from backend.api.app.config import ApiSettings
from backend.api.app.main import create_app

pytestmark = pytest.mark.integration
SETTINGS = ApiSettings()
T0 = datetime(2001, 1, 1, 10, 0, tzinfo=timezone.utc)
RANGE = {"from": "2001-01-01T09:00:00Z", "to": "2001-01-01T11:00:00Z"}
ES_INDEX = f"{SETTINGS.elasticsearch_index_prefix}-2001.01.01"
MS_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
# service, minute, severity, score, feedback
ROWS = [("payment-service", 0, "CRITICAL", 0.84, None),
        ("api-gateway", 1, "LOW", 0.55, "CONFIRMED"),
        ("order-service", 2, "HIGH", 0.80, None)]


def log_event(event_id: str, level: str, message: str) -> dict:
    return {"schema_version": "1.0", "event_id": event_id, "timestamp": "2001-01-01T10:00:30.000Z",
            "service": "payment-service", "host": "node-2", "level": level, "message": message}


@pytest.fixture(scope="module")
def data():
    try:
        with psycopg.connect(SETTINGS.postgres_conninfo, connect_timeout=5):
            pass
    except Exception:
        pytest.skip("PostgreSQL not reachable; start the stack with .\\scripts\\start.ps1 up")

    error_id, info_id, missing_id = (str(uuid.uuid4()) for _ in range(3))
    es = Elasticsearch(SETTINGS.elasticsearch_url)
    es.index(index=ES_INDEX, id=info_id, document=log_event(info_id, "INFO", "Payment processed (test)"))
    es.index(index=ES_INDEX, id=error_id, document=log_event(error_id, "ERROR", "Payment failed (test)"),
             refresh=True)

    anomaly_ids, window_ids = [], []
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        model = conn.execute("SELECT id FROM model_registry WHERE is_active").fetchone()
        if model is None:
            pytest.skip("No active model")
        services = dict(conn.execute("SELECT name, id FROM services").fetchall())
        for service, minute, severity, score, feedback in ROWS:
            start = T0 + timedelta(minutes=minute)
            window_id = conn.execute(
                "INSERT INTO detection_windows (service_id, model_id, window_start, window_end, log_count, "
                "anomaly_score, is_anomaly) VALUES (%s, %s, %s, %s, 100, %s, TRUE) RETURNING id",
                (services[service], model[0], start, start + timedelta(minutes=1), score)).fetchone()[0]
            anomaly_id = uuid.uuid4()
            samples = [error_id, info_id, missing_id] if service == "payment-service" else []
            conn.execute(
                "INSERT INTO anomalies (id, window_id, service_id, model_id, detected_at, window_start, window_end, "
                "anomaly_score, severity, summary, sample_event_ids, feedback) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (anomaly_id, window_id, services[service], model[0], start + timedelta(seconds=66), start,
                 start + timedelta(minutes=1), score, severity, Jsonb({"log_count": 100, "reasons": ["test"]}),
                 samples, feedback))
            anomaly_ids.append(str(anomaly_id))
            window_ids.append(window_id)

    yield {"ids": dict(zip([r[0] for r in ROWS], anomaly_ids)), "error_id": error_id, "info_id": info_id}

    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        conn.execute("DELETE FROM anomalies WHERE id = ANY(%s)", ([uuid.UUID(i) for i in anomaly_ids],))
        conn.execute("DELETE FROM detection_windows WHERE id = ANY(%s)", (window_ids,))
    es.indices.delete(index=ES_INDEX, ignore_unavailable=True)
    es.close()


@pytest.fixture(scope="module")
def client(data):
    with TestClient(create_app(SETTINGS)) as test_client:
        yield test_client


def get(client, **params):
    response = client.get("/api/v1/anomalies", params={**RANGE, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_list_is_newest_first_with_contract_fields(client):
    body = get(client)
    assert body["total"] == 3 and body["page"] == 1 and body["size"] == 50
    assert [a["service"] for a in body["items"]] == ["order-service", "api-gateway", "payment-service"]
    item = body["items"][0]
    assert set(item) == {"id", "service", "detected_at", "window_start", "window_end", "anomaly_score",
                         "severity", "model", "summary", "alert_id", "feedback"}
    assert set(item["model"]) == {"id", "name", "version"}
    assert MS_TIMESTAMP.match(item["detected_at"])


def test_filters(client):
    assert get(client, severity="critical,HIGH")["total"] == 2
    assert get(client, service="payment-service")["total"] == 1
    assert get(client, feedback="NONE")["total"] == 2
    assert get(client, feedback="CONFIRMED")["total"] == 1
    assert get(client, feedback="NONE,CONFIRMED")["total"] == 3


def test_pagination(client):
    body = get(client, size=2, page=2)
    assert body["total"] == 3 and len(body["items"]) == 1
    assert body["items"][0]["service"] == "payment-service"


def test_bad_parameters(client):
    assert client.get("/api/v1/anomalies", params={**RANGE, "severity": "URGENT"}).status_code == 400
    assert client.get("/api/v1/anomalies", params={"from": RANGE["to"], "to": RANGE["from"]}).status_code == 400
    assert client.get("/api/v1/anomalies", params={"size": 500}).status_code == 422


def test_default_range_is_the_last_hour(client, data):
    response = client.get("/api/v1/anomalies", params={"size": 200})
    assert response.status_code == 200
    returned = {a["id"] for a in response.json()["items"]}
    assert not returned & set(data["ids"].values())      # 2001 test data is outside the last hour


def test_detail_has_sample_logs_errors_first_and_missing_omitted(client, data):
    response = client.get(f"/api/v1/anomalies/{data['ids']['payment-service']}")
    assert response.status_code == 200
    body = response.json()
    assert [log["event_id"] for log in body["sample_logs"]] == [data["error_id"], data["info_id"]]
    assert len(body["sample_event_ids"]) == 3
    assert body["sample_logs_error"] is None
    assert "ingested_at" not in body["sample_logs"][0]


def test_detail_not_found(client):
    assert client.get(f"/api/v1/anomalies/{uuid.uuid4()}").status_code == 404


def test_feedback_set_and_clear(client, data):
    anomaly_id = data["ids"]["order-service"]
    response = client.patch(f"/api/v1/anomalies/{anomaly_id}/feedback", json={"feedback": "FALSE_POSITIVE"})
    assert response.status_code == 200 and response.json()["feedback"] == "FALSE_POSITIVE"
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        assert conn.execute("SELECT feedback_at FROM anomalies WHERE id = %s", (anomaly_id,)).fetchone()[0] is not None
    response = client.patch(f"/api/v1/anomalies/{anomaly_id}/feedback", json={"feedback": None})
    assert response.status_code == 200 and response.json()["feedback"] is None
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        assert conn.execute("SELECT feedback_at FROM anomalies WHERE id = %s", (anomaly_id,)).fetchone()[0] is None


def test_feedback_rejects_unknown_values_and_ids(client, data):
    anomaly_id = data["ids"]["order-service"]
    assert client.patch(f"/api/v1/anomalies/{anomaly_id}/feedback", json={"feedback": "MAYBE"}).status_code == 422
    assert client.patch(f"/api/v1/anomalies/{uuid.uuid4()}/feedback",
                        json={"feedback": "CONFIRMED"}).status_code == 404