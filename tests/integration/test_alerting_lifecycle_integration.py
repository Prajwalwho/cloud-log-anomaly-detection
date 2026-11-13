"""
Auto-resolve and notification bookkeeping against PostgreSQL (own alerts dated 2001-01-05, removed afterwards).
Note: resolve_quiet resolves EVERY quiet open alert in the database, as the service would.
"""
from datetime import datetime, timezone

import psycopg
import pytest

from backend.alerting.config import AlertingSettings
from backend.alerting.store import AlertStore

pytestmark = pytest.mark.integration
SETTINGS = AlertingSettings()
T = datetime(2001, 1, 5, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def alerts():
    try:
        with psycopg.connect(SETTINGS.postgres_conninfo):
            pass
    except Exception:
        pytest.skip("PostgreSQL not reachable; start the stack with .\\scripts\\start.ps1 up")
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        service = conn.execute("SELECT id FROM services WHERE name = 'payment-service'").fetchone()[0]
        ids = [conn.execute(
            "INSERT INTO alerts (service_id, severity, title, status, first_seen_at, last_seen_at, notification_sent) "
            "VALUES (%s, 'HIGH', %s, %s, %s, %s, %s) RETURNING id",
            (service, title, status, T, T, notified)).fetchone()[0]
            for title, status, notified in (("quiet open", "OPEN", True), ("quiet acknowledged", "ACKNOWLEDGED", False),
                                            ("not notified", "OPEN", False))]
    yield [str(i) for i in ids]
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        conn.execute("DELETE FROM alerts WHERE id = ANY(%s)", (ids,))


def test_quiet_alerts_are_resolved(alerts):
    resolved = {a["id"]: a for a in AlertStore(SETTINGS.postgres_conninfo).resolve_quiet(300)}
    for alert_id in alerts:
        assert resolved[alert_id]["status"] == "RESOLVED" and resolved[alert_id]["resolved_at"]
    assert resolved[alerts[0]]["notification_sent"] is True      # this one would get a "Resolved" message


def test_mark_notified(alerts):
    alert = AlertStore(SETTINGS.postgres_conninfo).mark_notified(alerts[2])
    assert alert["notification_sent"] is True
    with psycopg.connect(SETTINGS.postgres_conninfo) as conn:
        assert conn.execute("SELECT notified_at FROM alerts WHERE id = %s", (alerts[2],)).fetchone()[0] is not None