"""
End-to-end speed of the pipeline (Phase 10, Day 41). Pure functions on plain records, unit-tested without a
database; scripts/latency_report.py loads the records from Elasticsearch, PostgreSQL and the live feed.

Stages (docs/testing/latency-results.md):
    log created -> stored in Elasticsearch          ingested_at - timestamp              (both: host clock)
    minute ends -> judged by detection              anomaly detected_at - window_end     (both: host clock)
    anomaly -> alert opened                         alert created_at - first_seen_at     (database clock - host clock)
    alert opened -> Telegram message sent           notified_at - created_at             (both: database clock)
    anomaly / alert -> shown on the dashboard       received over /ws/live - detected_at (both: host clock)

The services run on the host, PostgreSQL in Docker (a separate virtual machine on Windows): created_at and
notified_at come from the database's clock. The report measures the offset between the two clocks and subtracts it
(offset_s) wherever the two are mixed.

notified_at is the FIRST Telegram message of an alert (kept since Day 41; before that an escalation overwrote it).
Older alerts whose notified_at lies more than telegram_window_s after their creation were notified later
(escalation or a retry after a failed send) and are left out of the Telegram stage.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from .live_run import Incident


@dataclass(frozen=True)
class AnomalyTiming:
    service: str
    window_end: datetime
    detected_at: datetime


@dataclass(frozen=True)
class AlertTiming:
    service: str
    first_seen: datetime                 # detected_at of the alert's first anomaly (host clock)
    created_at: datetime                 # database clock
    notified_at: datetime | None         # database clock


def percentile(sorted_values: list[float], q: float) -> float:
    """Linear interpolation between the closest ranks (same as numpy's default)."""
    if not sorted_values:
        raise ValueError("no values")
    position = (len(sorted_values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def distribution(values: list[float]) -> dict | None:
    """n, mean, min, p50, p95, p99, max of a list of durations (seconds); None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": round(sum(ordered) / len(ordered), 3),
        "min": round(ordered[0], 3),
        "p50": round(percentile(ordered, 0.50), 3),
        "p95": round(percentile(ordered, 0.95), 3),
        "p99": round(percentile(ordered, 0.99), 3),
        "max": round(ordered[-1], 3),
    }


def _s(delta: timedelta) -> float:
    return delta.total_seconds()


def detection_stage(anomalies: list[AnomalyTiming]) -> list[float]:
    """Seconds from the end of a minute to its anomaly (grace period + scoring + storing)."""
    return [_s(a.detected_at - a.window_end) for a in anomalies]


def alert_stages(alerts: list[AlertTiming], offset_s: float = 0.0,
                 telegram_window_s: float = 30.0) -> tuple[list[float], list[float], int]:
    """(anomaly -> alert opened, alert opened -> Telegram sent, alerts notified only later)."""
    offset = timedelta(seconds=offset_s)
    opened = [_s(a.created_at - offset - a.first_seen) for a in alerts]
    telegram, later = [], 0
    for a in alerts:
        if a.notified_at is None:
            continue
        seconds = _s(a.notified_at - a.created_at)
        if seconds <= telegram_window_s:
            telegram.append(seconds)
        else:
            later += 1
    return opened, telegram, later


def incident_chain(incidents: list[Incident], anomalies: list[AnomalyTiming], alerts: list[AlertTiming],
                   margin_s: float = 120.0, offset_s: float = 0.0, telegram_window_s: float = 30.0) -> list[dict]:
    """Per incident: seconds from the fault's start to the first anomaly, first alert and first Telegram message.

    Anomalies and alerts count for an incident if they appear between its start and its end plus margin_s, on any
    service (a downstream failure also shows at the gateway). A Telegram time is given only where it was measured.
    """
    margin = timedelta(seconds=margin_s)
    offset = timedelta(seconds=offset_s)
    rows = []
    for inc in incidents:
        lo, hi = inc.start, inc.end + margin
        hits = sorted(a.detected_at for a in anomalies if lo <= a.detected_at <= hi)
        mine = [a for a in alerts if lo <= a.first_seen <= hi]
        opened = sorted(a.created_at - offset for a in mine)
        sent = sorted(a.notified_at - offset for a in mine
                      if a.notified_at is not None and _s(a.notified_at - a.created_at) <= telegram_window_s)
        rows.append({
            "scenario": inc.scenario,
            "start": inc.start.isoformat(),
            "anomaly_s": round(_s(hits[0] - inc.start), 1) if hits else None,
            "alert_s": round(_s(opened[0] - inc.start), 1) if opened else None,
            "telegram_s": round(_s(sent[0] - inc.start), 1) if sent else None,
        })
    return rows


def feed_stages(records: list[dict]) -> dict[str, list[float]]:
    """Live-feed records (scripts/latency_report.py watch) -> seconds per event type."""
    result: dict[str, list[float]] = {}
    for r in records:
        if r.get("delay_s") is not None:
            result.setdefault(r["type"], []).append(float(r["delay_s"]))
    return result