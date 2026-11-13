"""Unit tests for the window aggregator."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.detection.windowing import MAX_SAMPLES, WindowAggregator

T0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def test_events_are_grouped_into_minute_windows_per_service():
    agg = WindowAggregator(60)
    agg.add("a", at(5), "INFO", 1)
    agg.add("a", at(59), "INFO", 1)
    agg.add("a", at(61), "INFO", 2)
    agg.add("b", at(10), "INFO", 3)
    closed = agg.close_until(at(130))
    by_key = {(w.service, w.start): w.log_count for w in closed}
    assert by_key == {("a", at(0)): 2, ("b", at(0)): 1, ("a", at(60)): 1, ("b", at(60)): 0}


def test_known_services_get_empty_windows():
    agg = WindowAggregator(60, services=["a", "silent"])
    agg.add("a", at(5), "INFO", 1)
    closed = agg.close_until(at(60))
    silent = [w for w in closed if w.service == "silent"]
    assert len(silent) == 1 and silent[0].log_count == 0


def test_only_complete_windows_are_closed():
    agg = WindowAggregator(60)
    agg.add("a", at(5), "INFO", 1)
    assert agg.close_until(at(59)) == []
    assert len(agg.close_until(at(60))) == 1


def test_late_events_are_counted_and_dropped():
    agg = WindowAggregator(60)
    agg.add("a", at(5), "INFO", 1)
    agg.close_until(at(60))
    assert agg.add("a", at(30), "INFO", 1) is False
    assert agg.late_events == 1


def test_levels_templates_and_latency_are_recorded():
    agg = WindowAggregator(60)
    agg.add("a", at(1), "ERROR", 7, latency_ms=100)
    agg.add("a", at(2), "FATAL", 7, latency_ms=300)
    agg.add("a", at(3), "WARN", 8)
    window = agg.close_until(at(60))[0]
    assert (window.log_count, window.error_count, window.warn_count) == (3, 2, 1)
    assert window.template_counts == {7: 2, 8: 1}
    assert window.latencies == [100.0, 300.0]


def test_gap_produces_empty_windows_for_every_minute():
    agg = WindowAggregator(60, services=["a"])
    agg.add("a", at(5), "INFO", 1)
    closed = agg.close_until(at(240))
    assert [w.log_count for w in closed] == [1, 0, 0, 0]


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError):
        WindowAggregator(60).add("a", datetime(2026, 1, 1), "INFO", 1)


def test_sample_event_ids_prefer_errors_then_warnings():
    agg = WindowAggregator(60)
    for i in range(15):
        agg.add("a", at(1), "INFO", 1, event_id=f"info-{i}")
    agg.add("a", at(2), "WARN", 2, event_id="warn-0")
    agg.add("a", at(3), "ERROR", 3, event_id="error-0")
    samples = agg.close_until(at(60))[0].sample_event_ids
    assert samples[:2] == ["error-0", "warn-0"]
    assert len(samples) == MAX_SAMPLES


def test_closed_before_tracks_progress():
    agg = WindowAggregator(60)
    assert agg.closed_before is None
    agg.add("a", at(5), "INFO", 1)
    assert agg.closed_before == at(0).timestamp()
    agg.close_until(at(125))
    assert agg.closed_before == at(120).timestamp()