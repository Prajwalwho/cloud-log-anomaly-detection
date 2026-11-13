"""
Grouping anomalies into alerts in PostgreSQL (one transaction per anomaly).

For an anomaly from anomalies.detected:
- already linked to an alert            -> "duplicate" (Kafka delivers at least once; nothing changes)
- not in the database                   -> "unknown"   (e.g. a test message)
- an OPEN/ACKNOWLEDGED alert of the same service within the grouping gap
                                        -> join it: occurrence_count + 1, last_seen_at, severity = max, message
- otherwise, severity >= min_severity   -> open a new alert
- otherwise                             -> "below_threshold" (no alert)
The anomaly is linked to its alert (anomalies.alert_id). Rows are locked, so concurrent work stays consistent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from .rules import max_severity, opens_alert, title_for

ALERT_SELECT = """
SELECT al.id, s.name AS service, al.severity, al.title, al.message, al.status, al.occurrence_count,
       al.first_seen_at, al.last_seen_at, al.acknowledged_at, al.acknowledged_by, al.resolved_at,
       al.notification_sent
FROM alerts al
JOIN services s ON s.id = al.service_id
WHERE al.id = %(id)s
"""


def iso_ms(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def alert_item(row: dict) -> dict:
    """Alert in the API's alert item format (api-contracts.md §3.8), JSON-ready."""
    return {
        "id": str(row["id"]), "service": row["service"], "severity": row["severity"], "title": row["title"],
        "message": row["message"], "status": row["status"], "occurrence_count": row["occurrence_count"],
        "first_seen_at": iso_ms(row["first_seen_at"]), "last_seen_at": iso_ms(row["last_seen_at"]),
        "acknowledged_at": iso_ms(row["acknowledged_at"]), "acknowledged_by": row["acknowledged_by"],
        "resolved_at": iso_ms(row["resolved_at"]), "notification_sent": row["notification_sent"],
    }


@dataclass
class Outcome:
    result: str                         # created | updated | duplicate | unknown | below_threshold
    alert: dict | None = None

    @property
    def event_type(self) -> str | None:
        return {"created": "alert.created", "updated": "alert.updated"}.get(self.result)


class AlertStore:
    def __init__(self, conninfo: str, gap_s: float = 300.0, min_severity: str = "MEDIUM") -> None:
        self.conninfo = conninfo
        self.gap = timedelta(seconds=gap_s)
        self.min_severity = min_severity

    def process(self, message: dict) -> Outcome:
        anomaly_id = message["anomaly_id"]
        severity = message["severity"]
        detected_at = parse_ts(message["detected_at"])
        summary = message.get("summary") or {}
        reasons = list(summary.get("reasons") or [])
        text = "; ".join(reasons) or None

        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn, conn.transaction():
            anomaly = conn.execute("SELECT service_id, alert_id FROM anomalies WHERE id = %s FOR UPDATE",
                                   (anomaly_id,)).fetchone()
            if anomaly is None:
                return Outcome("unknown")
            if anomaly["alert_id"] is not None:
                return Outcome("duplicate")

            current = conn.execute(
                """
                SELECT id, severity FROM alerts
                WHERE service_id = %(service)s AND status IN ('OPEN', 'ACKNOWLEDGED')
                  AND last_seen_at BETWEEN %(lo)s AND %(hi)s
                ORDER BY last_seen_at DESC
                LIMIT 1
                FOR UPDATE
                """,
                {"service": anomaly["service_id"], "lo": detected_at - self.gap, "hi": detected_at + self.gap},
            ).fetchone()

            if current is not None:
                conn.execute(
                    """
                    UPDATE alerts
                    SET occurrence_count = occurrence_count + 1,
                        last_seen_at = GREATEST(last_seen_at, %(seen)s),
                        severity = %(severity)s,
                        message = %(message)s
                    WHERE id = %(id)s
                    """,
                    {"seen": detected_at, "severity": max_severity(current["severity"], severity),
                     "message": text, "id": current["id"]},
                )
                alert_id, result = current["id"], "updated"
            elif opens_alert(severity, self.min_severity):
                alert_id = conn.execute(
                    """
                    INSERT INTO alerts (service_id, severity, title, message, first_seen_at, last_seen_at)
                    VALUES (%(service)s, %(severity)s, %(title)s, %(message)s, %(seen)s, %(seen)s)
                    RETURNING id
                    """,
                    {"service": anomaly["service_id"], "severity": severity,
                     "title": title_for(message["service"], reasons, summary.get("rule")),
                     "message": text, "seen": detected_at},
                ).fetchone()["id"]
                result = "created"
            else:
                return Outcome("below_threshold")

            conn.execute("UPDATE anomalies SET alert_id = %s WHERE id = %s", (alert_id, anomaly_id))
            row = conn.execute(ALERT_SELECT, {"id": alert_id}).fetchone()
        return Outcome(result, alert_item(row))