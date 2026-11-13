"""
Alerting rules that do not need a database (unit-tested): severity order, escalation, titles, notifications.
"""
from __future__ import annotations

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def rank(severity: str) -> int:
    return SEVERITIES.index(severity)


def max_severity(a: str, b: str) -> str:
    return a if rank(a) >= rank(b) else b


def opens_alert(severity: str, min_severity: str) -> bool:
    """A new alert is opened only from anomalies at or above min_severity (LOW false alarms, Day 25)."""
    return rank(severity) >= rank(min_severity)


def title_for(service: str, reasons: list[str], rule: str | None = None) -> str:
    """Readable title from the strongest reason (reasons are sorted strongest first by the detector)."""
    first = reasons[0] if reasons else ""
    if rule == "no_logs" or first.startswith("no logs"):
        title = f"{service} stopped logging"
    elif first.startswith("error rate"):
        title = f"Error rate increase in {service}"
    elif first.startswith("log volume"):
        title = f"Log volume drop in {service}"
    elif first.startswith("p95 latency"):
        title = f"Latency increase in {service}"
    elif "new message type" in first:
        title = f"New message type in {service}"
    else:
        title = f"Unusual log pattern in {service}"
    return title[:200]


def notification_kind(result: str, severity: str, previous_severity: str | None, notified: bool,
                      min_severity: str = "HIGH") -> str | None:
    """
    Which notification (if any) a created/updated alert needs:
      "new"       the alert reached min_severity and nobody has been told yet
      "escalated" an already-notified alert just became CRITICAL
      None        nothing to send (below min_severity, or a repeat at the same severity)
    """
    if result not in ("created", "updated") or rank(severity) < rank(min_severity):
        return None
    if not notified:
        return "new"
    if severity == "CRITICAL" and previous_severity is not None and previous_severity != "CRITICAL":
        return "escalated"
    return None