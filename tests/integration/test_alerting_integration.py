"""
Alert grouping against PostgreSQL, with its own data (2001-01-04, removed afterwards).

payment-service anomalies at minutes 0, 1, 2 (HIGH, CRITICAL, HIGH) -> ONE alert, count 3, severity CRITICAL;
a payment anomaly at minute 20 (beyond the 5-min gap) -> a NEW alert;
an api-gateway LOW anomaly -> no alert; processing an anomaly twice -> duplicate; unknown id -> unknown.
"""
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from psycopg.types.json import Jsonb

from backend.alerting.config import AlertingSettings
from backend.alerting.store import AlertStore

pytestmark = pytest.mark.integration
SETTINGS = AlertingSettings()
T0 = datetime(2001, 1, 4, 10, 0, tzinfo=timezone.utc)
# service, minute, severity, reasons
ROWS = [("payment-service", 0, "HIGH", ["error rate 18.6%"]),
        ("payment-service", 1, "CRITICAL", ["error rate 39.3%"]),
        ("payment-service", 2, "HIGH", ["error rate 18.3%"]),
        ("api-gateway", 0, "LOW", ["unusual log pattern (no single signal above its limit)"]),
        ("payment-service", 20, "HIGH", ["error rate 9.0%"])]


def iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture(scope="module")
def data():
    try:
        with psycopg.connect(SETTINGS.postgres_conninfo):
            pass
    except Exception:
        pytest.skip("PostgreSQL not reachable; start the stack with .\\scripts\\start.ps1 up")
    messages, window_ids, anomaly_ids = [], [], []
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        model = conn.execute("SELECT id FROM model_registry WHERE is_active").fetchone()
        if model is None:
            pytest.skip("No active model")
        services = dict(conn.execute("SELECT name, id FROM services").fetchall())
        for service, minute, severity, reasons in ROWS:
            start = T0 + timedelta(minutes=minute)
            window_id = conn.execute(
                "INSERT INTO detection_windows (service_id, model_id, window_start, window_end, log_count, "
                "anomaly_score, is_anomaly) VALUES (%s, %s, %s, %s, 100, 0.8, TRUE) RETURNING id",
                (services[service], model[0], start, start + timedelta(minutes=1))).fetchone()[0]
            anomaly_id = uuid.uuid4()
            detected = start + timedelta(seconds=66)
            conn.execute(
                "INSERT INTO anomalies (id, window_id, service_id, model_id, detected_at, window_start, window_end, "
                "anomaly_score, severity, summary) VALUES (%s, %s, %s, %s, %s, %s, %s, 0.8, %s, %s)",
                (anomaly_id, window_id, services[service], model[0], detected, start, start + timedelta(minutes=1),
                 severity, Jsonb({"reasons": reasons, "rule": None})))
            window_ids.append(window_id)
            anomaly_ids.append(anomaly_id)
            messages.append({"anomaly_id": str(anomaly_id), "service": service, "severity": severity,
                             "detected_at": iso(detected), "summary": {"reasons": reasons, "rule": None}})
    yield messages
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        alert_ids = [r[0] for r in conn.execute("SELECT DISTINCT alert_id FROM anomalies WHERE id = ANY(%s) "
                                                "AND alert_id IS NOT NULL", (anomaly_ids,)).fetchall()]
        conn.execute("DELETE FROM anomalies WHERE id = ANY(%s)", (anomaly_ids,))
        conn.execute("DELETE FROM detection_windows WHERE id = ANY(%s)", (window_ids,))
        conn.execute("DELETE FROM alerts WHERE id = ANY(%s)", (alert_ids,))


def test_grouping(data):
    store = AlertStore(SETTINGS.postgres_conninfo, gap_s=300, min_severity="MEDIUM")
    first = store.process(data[0])
    assert first.result == "created" and first.event_type == "alert.created"
    assert first.alert["title"] == "Error rate increase in payment-service"
    assert first.alert["occurrence_count"] == 1 and first.alert["severity"] == "HIGH"

    second = store.process(data[1])
    assert second.result == "updated" and second.alert["id"] == first.alert["id"]
    assert second.alert["severity"] == "CRITICAL"                       # escalated

    third = store.process(data[2])
    assert third.alert["id"] == first.alert["id"] and third.alert["occurrence_count"] == 3
    assert third.alert["severity"] == "CRITICAL"                        # never drops back
    assert third.alert["message"] == "error rate 18.3%"                 # latest reasons

    assert store.process(data[3]).result == "below_threshold"           # LOW opens nothing

    later = store.process(data[4])
    assert later.result == "created" and later.alert["id"] != first.alert["id"]   # beyond the 5-min gap

    assert store.process(data[1]).result == "duplicate"                 # replay changes nothing
    assert store.process({**data[0], "anomaly_id": str(uuid.uuid4())}).result == "unknown"