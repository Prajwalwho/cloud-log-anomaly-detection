"""
Live evaluation of one real-time run (Phase 10, RQ3): stored detection windows, anomalies and alerts compared with
the generator's ground truth. Pure functions on plain records, so they are unit-tested without a database;
scripts/live_eval.py loads the records from PostgreSQL and saves the results.

Definitions (docs/testing/live-evaluation-plan.md):
- A window is *faulty* if it overlaps a fault of the same service; *full* if it lies completely inside the fault.
- An *incident* is one injected scenario (all its fault records); its period is first start to last end.
- A window is *near an incident* if it overlaps an incident period extended by `margin_s` on both sides, on any
  service. Flags there are counted as expected reactions (a downstream failure also shows at the gateway).
- *Quiet* windows are all other windows: flags there are false alarms.
- Idle windows (no logs and not flagged) are ignored, as in the API statistics (Day 34).
- Detection delay = detected_at of the first anomaly - start of the fault (wall-clock time, real-time runs only).
"""
from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

SEVERITY_ORDER = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


@dataclass(frozen=True)
class FaultRecord:
    scenario: str
    service: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class WindowRecord:
    service: str
    start: datetime
    end: datetime
    log_count: int
    flagged: bool
    severity: str | None = None
    detected_at: datetime | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AlertRecord:
    service: str
    severity: str
    first_seen: datetime
    last_seen: datetime
    resolved_at: datetime | None
    notified: bool
    occurrences: int


@dataclass(frozen=True)
class Incident:
    scenario: str
    start: datetime
    end: datetime
    services: tuple[str, ...]


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and a_end > b_start


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def _worst(severities: list[str]) -> str | None:
    known = [s for s in severities if s in SEVERITY_ORDER]
    return max(known, key=SEVERITY_ORDER.index) if known else None


def _seconds(delta: timedelta) -> float:
    return round(delta.total_seconds(), 1)


def incidents_of(faults: list[FaultRecord]) -> list[Incident]:
    """One incident per scenario, in time order (a scenario appears once per run)."""
    groups: dict[str, list[FaultRecord]] = {}
    for f in faults:
        groups.setdefault(f.scenario, []).append(f)
    result = [Incident(name, min(f.start for f in fs), max(f.end for f in fs),
                       tuple(sorted({f.service for f in fs}))) for name, fs in groups.items()]
    return sorted(result, key=lambda i: i.start)


def evaluate_run(faults: list[FaultRecord], windows: list[WindowRecord], alerts: list[AlertRecord],
                 margin_s: float = 120.0, alert_tail_s: float = 240.0) -> dict:
    margin = timedelta(seconds=margin_s)
    tail = timedelta(seconds=alert_tail_s)
    active = [w for w in windows if w.log_count > 0 or w.flagged]
    incidents = incidents_of(faults)

    def faulty(w: WindowRecord) -> bool:
        return any(f.service == w.service and _overlaps(w.start, w.end, f.start, f.end) for f in faults)

    def full(w: WindowRecord) -> bool:
        return any(f.service == w.service and w.start >= f.start and w.end <= f.end for f in faults)

    def near_incident(w: WindowRecord) -> bool:
        return any(_overlaps(w.start, w.end, i.start - margin, i.end + margin) for i in incidents)

    # ---- window level ----
    tp = sum(1 for w in active if w.flagged and faulty(w))
    fp = sum(1 for w in active if w.flagged and not faulty(w))
    fn = sum(1 for w in active if not w.flagged and faulty(w))
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else 0.0
    full_windows = [w for w in active if full(w)]
    flagged = [w for w in active if w.flagged]
    quiet = [w for w in active if not near_incident(w)]
    quiet_alarms = [w for w in quiet if w.flagged]

    window_level = {
        "windows": len(active),
        "faulty_windows": tp + fn,
        "flagged_windows": len(flagged),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "full_window_recall": _ratio(sum(1 for w in full_windows if w.flagged), len(full_windows)),
        "incident_precision": _ratio(sum(1 for w in flagged if near_incident(w)), len(flagged)),
        "quiet_windows": len(quiet),
        "quiet_false_alarms": len(quiet_alarms),
        "quiet_false_alarm_rate": _ratio(len(quiet_alarms), len(quiet)),
        "quiet_false_alarm_severities": dict(Counter(w.severity or "?" for w in quiet_alarms)),
        "quiet_false_alarm_list": [
            {"service": w.service, "start": w.start.isoformat(), "severity": w.severity, "reasons": list(w.reasons)}
            for w in quiet_alarms
        ],
    }

    # ---- per fault record ----
    per_fault = []
    for f in faults:
        overlap = [w for w in active if w.service == f.service and _overlaps(w.start, w.end, f.start, f.end)]
        hits = sorted((w for w in overlap if w.flagged and w.detected_at), key=lambda w: w.detected_at)
        per_fault.append({
            "scenario": f.scenario, "service": f.service,
            "windows": len(overlap), "flagged": sum(1 for w in overlap if w.flagged),
            "delay_s": _seconds(hits[0].detected_at - f.start) if hits else None,
            "severities": [w.severity for w in hits],
        })

    # ---- per incident (any service) and its alerts ----
    per_incident = []
    for inc in incidents:
        hits = sorted((w for w in active if w.flagged and w.detected_at and _overlaps(w.start, w.end, inc.start, inc.end)),
                      key=lambda w: w.detected_at)
        own = [a for a in alerts if inc.start - margin <= a.first_seen <= inc.end + tail]
        own.sort(key=lambda a: a.first_seen)
        resolved_after = [_seconds(a.resolved_at - inc.end) for a in own if a.resolved_at]
        per_incident.append({
            "scenario": inc.scenario,
            "faulty_services": list(inc.services),
            "detected": bool(hits),
            "delay_s": _seconds(hits[0].detected_at - inc.start) if hits else None,
            "first_service": hits[0].service if hits else None,
            "anomalies": len(hits),
            "worst_severity": _worst([w.severity or "" for w in hits]),
            "alerts": len(own),
            "alert_services": sorted({a.service for a in own}),
            "alert_delay_s": _seconds(own[0].first_seen - inc.start) if own else None,
            "alerts_notified": sum(1 for a in own if a.notified),
            "resolved_after_end_s": statistics.median(resolved_after) if resolved_after else None,
        })

    # ---- alerts outside incidents ----
    def in_incident(a: AlertRecord) -> bool:
        return any(i.start - margin <= a.first_seen <= i.end + tail for i in incidents)

    stray = [a for a in alerts if not in_incident(a)]
    detected = [i for i in per_incident if i["detected"]]
    alerted = [i for i in per_incident if i["alerts"]]
    summary = {
        "incidents": len(per_incident),
        "incidents_detected": len(detected),
        "incidents_alerted": len(alerted),
        "mean_delay_s": statistics.mean(i["delay_s"] for i in detected) if detected else None,
        "mean_alert_delay_s": statistics.mean(i["alert_delay_s"] for i in alerted) if alerted else None,
        "anomalies_in_incidents": sum(i["anomalies"] for i in per_incident),
        "alerts_in_incidents": sum(i["alerts"] for i in per_incident),
        "alerts_notified": sum(i["alerts_notified"] for i in per_incident),
        "alerts_outside_incidents": len(stray),
        "alerts_outside_incidents_list": [
            {"service": a.service, "severity": a.severity, "first_seen": a.first_seen.isoformat()} for a in stray
        ],
    }
    return {"summary": summary, "window_level": window_level, "per_incident": per_incident, "per_fault": per_fault}


def evaluate_normal(windows: list[WindowRecord], alerts: list[AlertRecord]) -> dict:
    """A fault-free run: every flag is a false alarm, every alert a false alert."""
    active = [w for w in windows if w.log_count > 0 or w.flagged]
    alarms = [w for w in active if w.flagged]
    return {
        "windows": len(active),
        "false_alarms": len(alarms),
        "false_alarm_rate": _ratio(len(alarms), len(active)),
        "false_alarm_severities": dict(Counter(w.severity or "?" for w in alarms)),
        "false_alarms_per_service": dict(Counter(w.service for w in alarms)),
        "false_alarm_list": [{"service": w.service, "start": w.start.isoformat(), "severity": w.severity,
                              "reasons": list(w.reasons)} for w in alarms],
        "alerts": len(alerts),
        "alerts_notified": sum(1 for a in alerts if a.notified),
    }


def _stats(values: list[float]) -> dict | None:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {"n": len(values), "mean": statistics.mean(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values), "max": max(values)}


def summarise_runs(runs: list[dict], normals: list[dict]) -> dict:
    """Mean, standard deviation, min and max over fault runs, per metric and per scenario."""
    wl = [r["window_level"] for r in runs]
    sm = [r["summary"] for r in runs]
    overall = {
        "runs": len(runs),
        "incident_detection_rate": _stats([_ratio(s["incidents_detected"], s["incidents"]) for s in sm]),
        "mean_delay_s": _stats([s["mean_delay_s"] for s in sm]),
        "mean_alert_delay_s": _stats([s["mean_alert_delay_s"] for s in sm]),
        "precision": _stats([w["precision"] for w in wl]),
        "recall": _stats([w["recall"] for w in wl]),
        "f1": _stats([w["f1"] for w in wl]),
        "full_window_recall": _stats([w["full_window_recall"] for w in wl]),
        "incident_precision": _stats([w["incident_precision"] for w in wl]),
        "quiet_false_alarm_rate": _stats([w["quiet_false_alarm_rate"] for w in wl]),
        "anomalies_per_incident": _stats([_ratio(s["anomalies_in_incidents"], s["incidents"]) for s in sm]),
        "alerts_per_incident": _stats([_ratio(s["alerts_in_incidents"], s["incidents"]) for s in sm]),
        "alerts_outside_incidents": _stats([s["alerts_outside_incidents"] for s in sm]),
    }
    scenarios: dict[str, list[dict]] = {}
    for r in runs:
        for inc in r["per_incident"]:
            scenarios.setdefault(inc["scenario"], []).append(inc)
    per_scenario = {
        name: {
            "runs": len(items),
            "detected": sum(1 for i in items if i["detected"]),
            "delay_s": _stats([i["delay_s"] for i in items]),
            "alert_delay_s": _stats([i["alert_delay_s"] for i in items]),
            "anomalies": _stats([i["anomalies"] for i in items]),
            "alerts": _stats([i["alerts"] for i in items]),
            "worst_severities": dict(Counter(i["worst_severity"] or "none" for i in items)),
        }
        for name, items in scenarios.items()
    }
    normal = {
        "runs": len(normals),
        "windows": sum(n["windows"] for n in normals),
        "false_alarms": sum(n["false_alarms"] for n in normals),
        "false_alarm_rate": _ratio(sum(n["false_alarms"] for n in normals), sum(n["windows"] for n in normals)),
        "alerts": sum(n["alerts"] for n in normals),
    } if normals else None
    return {"overall": overall, "per_scenario": per_scenario, "normal": normal}