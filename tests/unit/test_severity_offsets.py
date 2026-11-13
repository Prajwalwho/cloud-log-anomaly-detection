"""Unit tests for severity bands and the offset tracker."""
from backend.detection.offsets import OffsetTracker
from backend.detection.scoring.severity import severity_for, severity_from_score


def test_severity_bands():
    assert severity_from_score(0.50) is None
    assert severity_from_score(0.55) == "LOW"
    assert severity_from_score(0.70) == "MEDIUM"
    assert severity_from_score(0.80) == "HIGH"
    assert severity_from_score(0.95) == "CRITICAL"


def test_no_logs_is_at_least_high():
    assert severity_for(0.10, no_logs=True) == "HIGH"
    assert severity_for(0.55, no_logs=True) == "HIGH"
    assert severity_for(0.95, no_logs=True) == "CRITICAL"


def test_only_offsets_of_closed_windows_are_committed():
    tracker = OffsetTracker()
    tracker.add("logs.raw", 0, 10, window_start=0.0)
    tracker.add("logs.raw", 0, 11, window_start=0.0)
    tracker.add("logs.raw", 0, 12, window_start=60.0)    # still open
    commits = tracker.committable(closed_before=60.0)
    assert [(tp.partition, tp.offset) for tp in commits] == [(0, 12)]   # next offset to read = 12
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