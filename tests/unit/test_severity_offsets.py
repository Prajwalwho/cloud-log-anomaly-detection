"""Unit tests for severity grading and the offset tracker."""
from backend.detection.offsets import OffsetTracker
from backend.detection.scoring.severity import grade

BASE = {"log_count": 300.0, "p95_latency_ms": 60.0}


def summary(logs=300, errors=0, p95=60.0, new=0):
    return {"log_count": logs, "error_count": errors, "warn_count": 0, "p95_latency_ms": p95, "new_templates": new}


def test_error_rate_bands():
    assert grade(summary(errors=150), BASE).severity == "CRITICAL"    # 50%
    assert grade(summary(errors=30), BASE).severity == "HIGH"         # 10%
    assert grade(summary(errors=6), BASE).severity == "MEDIUM"        # 2%


def test_no_logs_is_critical_with_reason():
    g = grade(summary(logs=0), BASE, no_logs=True)
    assert g.severity == "CRITICAL" and "no logs" in g.reasons[0]


def test_volume_drop_and_latency():
    assert grade(summary(logs=20), BASE).severity == "CRITICAL"        # 7% of normal
    assert grade(summary(logs=120), BASE).severity == "HIGH"           # 40% of normal
    assert grade(summary(p95=340.0), BASE).severity == "HIGH"          # 5.7x
    assert grade(summary(p95=100.0), BASE).severity == "MEDIUM"        # 1.7x


def test_new_template_is_medium():
    assert grade(summary(new=1), BASE).severity == "MEDIUM"


def test_no_signal_is_low_and_highest_signal_wins_with_reasons_sorted():
    assert grade(summary(), BASE).severity == "LOW"
    g = grade(summary(errors=6, p95=340.0, new=1), BASE)
    assert g.severity == "HIGH" and g.reasons[0].startswith("p95 latency") and len(g.reasons) == 3


def test_only_offsets_of_closed_windows_are_committed():
    tracker = OffsetTracker()
    tracker.add("logs.raw", 0, 10, window_start=0.0)
    tracker.add("logs.raw", 0, 11, window_start=0.0)
    tracker.add("logs.raw", 0, 12, window_start=60.0)    # still open
    commits = tracker.committable(closed_before=60.0)
    assert [(tp.partition, tp.offset) for tp in commits] == [(0, 12)]
    assert tracker.pending == 1


def test_nothing_to_commit_before_any_window_closes():
    tracker = OffsetTracker()
    tracker.add("logs.raw", 1, 5, window_start=120.0)
    assert tracker.committable(closed_before=120.0) == []
    assert tracker.committable(closed_before=None) == []


def test_each_partition_is_tracked_separately():
    tracker = OffsetTracker()
    tracker.add("logs.raw", 0, 3, window_start=0.0)
    tracker.add("logs.raw", 2, 7, window_start=0.0)
    commits = {tp.partition: tp.offset for tp in tracker.committable(closed_before=60.0)}
    assert commits == {0: 4, 2: 8}