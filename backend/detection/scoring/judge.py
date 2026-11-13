"""
Judging closed windows: model flag + no-logs rule + severity grade.
Shared by the live service (service.py) and evaluation (train.py), so both apply exactly the same rules.

- A window is an anomaly if the model flags it, or if the service sent no logs while other services did.
- If ALL services are empty in a window, there is no traffic at all (generator stopped, pipeline idle):
  no anomalies are created for that window.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ..live_model import LiveDetector
from ..windowing import WindowStats
from .severity import grade


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
    reasons: tuple[str, ...] = ()


def judge_windows(detector: LiveDetector, windows: Sequence[WindowStats]) -> tuple[list[WindowResult], list[datetime]]:
    """Results in time order (then service), and the window starts in which no service had logs."""
    if not windows:
        return [], []
    out = detector.predict(windows)
    baselines = getattr(detector, "baselines", {})
    by_start: dict[float, list[int]] = defaultdict(list)
    for i, w in enumerate(windows):
        by_start[w.start_epoch].append(i)

    results, idle_minutes = [], []
    for start, indices in sorted(by_start.items()):
        no_traffic = all(windows[i].log_count == 0 for i in indices)
        if no_traffic:
            idle_minutes.append(windows[indices[0]].start)
        for i in sorted(indices, key=lambda j: windows[j].service):
            w = windows[i]
            summary = detector.extractor.summary(w)
            no_logs = w.log_count == 0 and not no_traffic
            flagged = (bool(out["is_anomaly"][i]) or no_logs) and not no_traffic
            graded = grade(summary, baselines.get(w.service), no_logs) if flagged else None
            results.append(WindowResult(
                window=w, summary=summary,
                raw_score=float(out["raw"][i]), threshold=float(out["threshold"][i]),
                score=float(out["score"][i]), is_anomaly=flagged,
                severity=graded.severity if graded else None,
                rule="no_logs" if no_logs else None,
                reasons=graded.reasons if graded else (),
            ))
    return results, idle_minutes