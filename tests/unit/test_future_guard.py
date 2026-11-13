"""Unit tests for the future-timestamp rule and reason formatting."""
from datetime import datetime, timedelta, timezone

from backend.detection.pipeline import too_far_in_future
from backend.detection.scoring.severity import grade

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def test_more_than_five_minutes_ahead_is_rejected():
    assert too_far_in_future(NOW + timedelta(minutes=5, seconds=1), now=NOW)
    assert too_far_in_future(datetime(2030, 1, 1, tzinfo=timezone.utc), now=NOW)


def test_small_clock_differences_and_past_are_accepted():
    assert not too_far_in_future(NOW + timedelta(minutes=5), now=NOW)
    assert not too_far_in_future(NOW + timedelta(seconds=2), now=NOW)
    assert not too_far_in_future(NOW - timedelta(days=1), now=NOW)


def test_latency_ratio_just_under_the_limit_is_not_shown_as_the_limit():
    g = grade({"log_count": 300, "error_count": 0, "p95_latency_ms": 178.2, "new_templates": 0},
              {"log_count": 300.0, "p95_latency_ms": 60.0})
    assert g.severity == "MEDIUM"
    assert "2.97x" in g.reasons[0]