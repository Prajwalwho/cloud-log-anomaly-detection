"""
Statistics and alert endpoints against the running stack, with their own test data on 2001-01-03
(windows, anomalies, alerts), removed afterwards.

Data: payment-service 3 windows (100 logs; errors 0/40/0), api-gateway 3 windows (200 logs; errors 0/10/0),
one anomaly each in minute 1 (payment CRITICAL, gateway HIGH); two alerts (payment OPEN, gateway ACKNOWLEDGED),
the payment anomaly belongs to the payment alert.
"""
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from backend.api.app.config import ApiSettings
from backend.api.app.main import create_app

pytestmark = pytest.mark.integration
SETTINGS = ApiSettings()
T0 = datetime(2001, 1, 3, 10, 0, tzinfo=timezone.utc)
RANGE = {"from": "2001-01-03T09:00:00Z", "to": "2001-01-03T11:00:00Z"}
WINDOWS = {"payment-service": (100, [0, 40, 0], "CRITICAL"), "api-gateway": (200, [0, 10, 0], "HIGH")}


@pytest.fixture(scope="module")
def data():
    try:
        with psycopg.connect(SETTINGS.postgres_conninfo, connect_timeout=5):
            pass
    except Exception:
        pytest.skip("PostgreSQL not reachable; start the stack with .\\scripts\\start.ps1 up")

    window_ids, anomaly_ids, alert_ids = [], [], {}
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        model = conn.execute("SELECT id FROM model_registry WHERE is_active").fetchone()
        if model is None:
            pytest.skip("No active model")
        services = dict(conn.execute("SELECT name, id FROM services").fetchall())
        for service, status in (("payment-service", "OPEN"), ("api-gateway", "ACKNOWLEDGED")):
            alert_ids[service] = conn.execute(
                "INSERT INTO alerts (service_id, severity, title, message, status, first_seen_at, last_seen_at) "
                "VALUES (%s, %s, %s, 'test', %s, %s, %s) RETURNING id",
                (services[service], WINDOWS[service][2], f"Test alert {service}", status,
                 T0 + timedelta(minutes=1), T0 + timedelta(minutes=2))).fetchone()[0]
        for service, (logs, errors, severity) in WINDOWS.items():
            for minute, error_count in enumerate(errors):
                start = T0 + timedelta(minutes=minute)
                anomalous = minute == 1
                window_id = conn.execute(
                    "INSERT INTO detection_windows (service_id, model_id, window_start, window_end, log_count, "
                    "error_count, avg_latency_ms, anomaly_score, is_anomaly) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 50, %s, %s) RETURNING id",
                    (services[service], model[0], start, start + timedelta(minutes=1), logs, error_count,
                     0.9 if anomalous else 0.2, anomalous)).fetchone()[0]
                window_ids.append(window_id)
                if anomalous:
                    anomaly_id = uuid.uuid4()
                    conn.execute(
                        "INSERT INTO anomalies (id, window_id, service_id, model_id, alert_id, detected_at, "
                        "window_start, window_end, anomaly_score, severity, summary) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0.9, %s, %s)",
                        (anomaly_id, window_id, services[service], model[0],
                         alert_ids[service] if service == "payment-service" else None,
                         start + timedelta(seconds=66), start, start + timedelta(minutes=1), severity,
                         Jsonb({"reasons": ["test"]})))
                    anomaly_ids.append(anomaly_id)

    yield {"alerts": {k: str(v) for k, v in alert_ids.items()}}

    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        conn.execute("DELETE FROM anomalies WHERE id = ANY(%s)", (anomaly_ids,))
        conn.execute("DELETE FROM detection_windows WHERE id = ANY(%s)", (window_ids,))
        conn.execute("DELETE FROM alerts WHERE id = ANY(%s)", (list(alert_ids.values()),))


@pytest.fixture(scope="module")
def client(data):
    with TestClient(create_app(SETTINGS)) as test_client:
        yield test_client


# ---------------- statistics ----------------
def test_summary(client):
    body = client.get("/api/v1/stats/summary", params=RANGE).json()
    assert body["total_logs"] == 900 and body["total_windows"] == 6 and body["total_anomalies"] == 2
    assert body["error_rate"] == pytest.approx(50 / 900)
    assert body["by_severity"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 1, "CRITICAL": 1}
    payment = next(s for s in body["by_service"] if s["service"] == "payment-service")
    assert payment["anomalies"] == 1 and payment["error_rate"] == pytest.approx(40 / 300)
    assert body["open_alerts"] >= 1


def test_timeseries_per_minute(client):
    body = client.get("/api/v1/stats/timeseries",
                      params={**RANGE, "metric": "error_rate", "interval": "1m", "service": "payment-service"}).json()
    assert body["metric"] == "error_rate" and body["interval"] == "1m"
    assert len(body["series"]) == 1
    points = body["series"][0]["points"]
    assert [p["v"] for p in points] == pytest.approx([0.0, 0.4, 0.0])
    assert points[0]["t"] == "2001-01-03T10:00:00.000Z"


def test_timeseries_buckets_and_metrics(client):
    body = client.get("/api/v1/stats/timeseries", params={**RANGE, "metric": "anomaly_count", "interval": "5m"}).json()
    assert {s["service"] for s in body["series"]} == {"payment-service", "api-gateway"}
    assert all(len(s["points"]) == 1 and s["points"][0]["v"] == 1 for s in body["series"])
    logs = client.get("/api/v1/stats/timeseries", params={**RANGE, "metric": "log_count", "interval": "1h"}).json()
    assert sorted(s["points"][0]["v"] for s in logs["series"]) == [300, 600]


def test_timeseries_bad_parameters(client):
    assert client.get("/api/v1/stats/timeseries", params={**RANGE, "metric": "cpu"}).status_code == 400
    assert client.get("/api/v1/stats/timeseries",
                      params={**RANGE, "metric": "log_count", "interval": "2m"}).status_code == 400
    assert client.get("/api/v1/stats/timeseries", params={"metric": "log_count", "interval": "1m",
                                                          "from": "2001-01-01T00:00:00Z",
                                                          "to": "2001-02-01T00:00:00Z"}).status_code == 400
    assert client.get("/api/v1/stats/timeseries", params=RANGE).status_code == 422      # metric is required


# ---------------- alerts ----------------
def test_alert_list_and_filters(client):
    body = client.get("/api/v1/alerts", params=RANGE).json()
    assert body["total"] == 2
    assert client.get("/api/v1/alerts", params={**RANGE, "status": "open"}).json()["total"] == 1
    assert client.get("/api/v1/alerts", params={**RANGE, "service": "api-gateway"}).json()["total"] == 1
    assert client.get("/api/v1/alerts", params={**RANGE, "status": "CLOSED"}).status_code == 400


def test_alert_detail_has_its_anomalies(client, data):
    body = client.get(f"/api/v1/alerts/{data['alerts']['payment-service']}").json()
    assert body["status"] == "OPEN" and len(body["anomalies"]) == 1
    assert body["anomalies"][0]["service"] == "payment-service"
    assert client.get(f"/api/v1/alerts/{uuid.uuid4()}").status_code == 404


def test_alert_transitions(client, data):
    alert = data["alerts"]["payment-service"]
    response = client.patch(f"/api/v1/alerts/{alert}", json={"status": "ACKNOWLEDGED", "acknowledged_by": "admin"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACKNOWLEDGED" and body["acknowledged_by"] == "admin" and body["acknowledged_at"]

    assert client.patch(f"/api/v1/alerts/{alert}", json={"status": "OPEN"}).status_code == 400
    response = client.patch(f"/api/v1/alerts/{alert}", json={"status": "RESOLVED"})
    assert response.status_code == 200 and response.json()["resolved_at"]
    assert client.patch(f"/api/v1/alerts/{alert}", json={"status": "ACKNOWLEDGED"}).status_code == 400


def test_alert_patch_errors(client):
    assert client.patch(f"/api/v1/alerts/{uuid.uuid4()}", json={"status": "RESOLVED"}).status_code == 404
    assert client.patch(f"/api/v1/alerts/{uuid.uuid4()}", json={"status": "DONE"}).status_code == 422