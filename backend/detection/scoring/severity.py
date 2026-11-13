"""
Severity from the normalised anomaly score (detection-design.md, Section 5).

    score > 0.90  CRITICAL
    score > 0.75  HIGH
    score > 0.60  MEDIUM
    score > 0.50  LOW        (0.5 = model threshold)
    otherwise     None       (not an anomaly)

Rule override: a known service with no logs in a window is at least HIGH (PCA alone caught the silent
service in only 2 of 3 windows on Day 22). Bands are a first choice, to be calibrated on live data.
"""
from __future__ import annotations

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
BANDS = ((0.90, "CRITICAL"), (0.75, "HIGH"), (0.60, "MEDIUM"), (0.50, "LOW"))


def severity_from_score(score: float) -> str | None:
    for limit, name in BANDS:
        if score > limit:
            return name
    return None


def severity_for(score: float, no_logs: bool = False) -> str | None:
    severity = severity_from_score(score)
    if no_logs:
        candidates = [s for s in (severity, "HIGH") if s is not None]
        return max(candidates, key=SEVERITIES.index)
    return severity