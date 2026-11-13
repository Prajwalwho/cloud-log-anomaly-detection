"""
PostgreSQL writes of the detection service (database-design.md):
every closed window -> detection_windows; every flagged window -> anomalies.

Idempotent: a window already stored for the same (service, window_start, model) is skipped
(unique key), and anomalies are created only for newly stored windows. Replaying events after a
restart therefore never duplicates windows or anomalies.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from .windowing import WindowStats


@dataclass
class WindowResult:
    window: WindowStats
    summary: dict
    raw_score: float
    threshold: float
    score: float
    is_anomaly: bool
    severity: str | None
    rule: str | None = None
    extra: dict = field(default_factory=dict)


class DetectionStore:
    def __init__(self, conninfo: str) -> None:
        self.conninfo = conninfo
        self._service_ids: dict[str, int] = {}

    def _service_id(self, conn: psycopg.Connection, name: str) -> int:
        if name not in self._service_ids:
            conn.execute("INSERT INTO services (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
            self._service_ids[name] = conn.execute("SELECT id FROM services WHERE name = %s", (name,)).fetchone()[0]
        return self._service_ids[name]

    def write(self, results: list[WindowResult], model_id: int) -> list[dict]:
        """Store windows and anomalies in one transaction. Returns the anomalies that were created."""
        created: list[dict] = []
        with psycopg.connect(self.conninfo) as conn, conn.transaction():
            for r in results:
                w, s = r.window, r.summary
                service_id = self._service_id(conn, w.service)
                row = conn.execute(
                    """
                    INSERT INTO detection_windows
                        (service_id, model_id, window_start, window_end, log_count, error_count, warn_count,
                         avg_latency_ms, p95_latency_ms, unique_templates, new_templates, anomaly_score, is_anomaly)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (service_id, window_start, model_id) DO NOTHING
                    RETURNING id
                    """,
                    (service_id, model_id, w.start, w.end, s["log_count"], s["error_count"], s["warn_count"],
                     s["avg_latency_ms"], s["p95_latency_ms"], s["unique_templates"], s["new_templates"],
                     r.score, r.is_anomaly),
                ).fetchone()
                if row is None or not r.is_anomaly:
                    continue

                anomaly = {
                    "anomaly_id": str(uuid.uuid4()),
                    "detected_at": datetime.now(timezone.utc),
                    "service": w.service,
                    "window_start": w.start,
                    "window_end": w.end,
                    "anomaly_score": r.score,
                    "severity": r.severity,
                    "summary": {
                        "log_count": s["log_count"],
                        "error_rate": s["error_count"] / s["log_count"] if s["log_count"] else 0.0,
                        "warn_rate": s["warn_count"] / s["log_count"] if s["log_count"] else 0.0,
                        "avg_latency_ms": s["avg_latency_ms"],
                        "p95_latency_ms": s["p95_latency_ms"],
                        "new_templates": s["new_templates"],
                        "raw_score": r.raw_score,
                        "threshold": r.threshold,
                        "rule": r.rule,
                    },
                    "sample_event_ids": w.sample_event_ids,
                }
                conn.execute(
                    """
                    INSERT INTO anomalies
                        (id, window_id, service_id, model_id, detected_at, window_start, window_end,
                         anomaly_score, severity, summary, sample_event_ids)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (anomaly["anomaly_id"], row[0], service_id, model_id, anomaly["detected_at"], w.start, w.end,
                     r.score, r.severity, Jsonb(anomaly["summary"]), anomaly["sample_event_ids"]),
                )
                created.append(anomaly)
        return created