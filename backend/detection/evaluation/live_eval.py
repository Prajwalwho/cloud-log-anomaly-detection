"""
Evaluation of window flags against generator ground truth (Days 22+, Phase 10).

- A window is faulty if it overlaps a fault interval of the same service; "full" if it lies completely
  inside the fault, "edge" if it overlaps only partly.
- "Quiet" windows are far from any fault (no fault within `margin_s` on any service): flags there are
  false alarms. Flags on other services during an incident are expected side effects (Day 7).
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

import numpy as np

from ..pipeline import parse_timestamp
from ..windowing import WindowStats
from .metrics import binary_metrics


def label_windows(windows: Sequence[WindowStats], faults: list[dict], margin_s: float = 120.0) -> dict:
    parsed = [(f["service"], parse_timestamp(f["start"]), parse_timestamp(f["end"])) for f in faults]
    n = len(windows)
    faulty = np.zeros(n, bool)
    full = np.zeros(n, bool)
    record_of: list[list[int]] = [[] for _ in range(n)]
    margin = timedelta(seconds=margin_s)
    quiet = np.ones(n, bool)
    for i, w in enumerate(windows):
        for r, (service, start, end) in enumerate(parsed):
            if w.start < end + margin and w.end > start - margin:
                quiet[i] = False
            if service == w.service and w.start < end and w.end > start:
                faulty[i] = True
                record_of[i].append(r)
                full[i] |= w.start >= start and w.end <= end
    return {"faulty": faulty, "full": full, "edge": faulty & ~full, "quiet": quiet, "record_of": record_of,
            "fault_starts": [start for _, start, _ in parsed]}


def evaluate_flags(windows: Sequence[WindowStats], flags: np.ndarray, faults: list[dict]) -> dict:
    labels = label_windows(windows, faults)
    flags = np.asarray(flags, bool)
    m = binary_metrics(labels["faulty"], flags)
    n = len(windows)
    per_record = []
    for r, fault in enumerate(faults):
        idx = [i for i in range(n) if r in labels["record_of"][i]]
        hits = [i for i in idx if flags[i]]
        per_record.append({
            "scenario": fault["scenario"], "service": fault["service"],
            "flagged": len(hits), "windows": len(idx),
            "time_to_detect_s": (windows[hits[0]].end - labels["fault_starts"][r]).total_seconds() if hits else None,
        })

    def rate(mask: np.ndarray) -> float | None:
        return float(flags[mask].mean()) if mask.any() else None

    return {
        "windows": n, "faulty_windows": int(labels["faulty"].sum()),
        "precision": m.precision, "recall": m.recall, "f1": m.f1,
        "full_window_recall": rate(labels["full"]), "edge_window_recall": rate(labels["edge"]),
        "incidents_detected": sum(1 for r in per_record if r["flagged"] > 0), "incidents": len(faults),
        "quiet_windows": int(labels["quiet"].sum()), "quiet_false_alarms": int(flags[labels["quiet"]].sum()),
        "per_record": per_record,
    }