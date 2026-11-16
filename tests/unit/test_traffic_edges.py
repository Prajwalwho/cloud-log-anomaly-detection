"""Minutes in which all traffic started or stopped are not judged (Day 43)."""
from backend.detection.edges import MinuteBounds, traffic_edge

M = 1_794_800_000.0          # a minute start (epoch seconds, multiple of 60)


def test_normal_minute_is_judged():
    assert traffic_edge(M, 60, (M + 0.2, M + 59.8), latest_seen=M + 64.0, previous_had_traffic=True) is None


def test_traffic_starting_mid_minute_after_quiet_minute():
    assert traffic_edge(M, 60, (M + 25.0, M + 59.9), M + 64.0, previous_had_traffic=False) == "started"


def test_start_near_the_minute_boundary_is_judged():
    assert traffic_edge(M, 60, (M + 4.0, M + 59.9), M + 64.0, previous_had_traffic=False) is None


def test_late_first_event_after_busy_minute_is_not_a_start():
    # previous minute had traffic: a quiet beginning is a real dip (or a silent service), so judge it
    assert traffic_edge(M, 60, (M + 25.0, M + 59.9), M + 64.0, previous_had_traffic=True) is None


def test_traffic_stopping_mid_minute():
    assert traffic_edge(M, 60, (M + 0.1, M + 40.0), latest_seen=M + 40.0, previous_had_traffic=True) == "stopped"


def test_one_silent_service_is_not_an_edge():
    # the window of the silent service may be empty, but other services keep logging: latest_seen moves on
    assert traffic_edge(M, 60, (M + 0.1, M + 59.9), latest_seen=M + 64.5, previous_had_traffic=True) is None


def test_idle_minute_is_left_to_the_idle_rule():
    assert traffic_edge(M, 60, None, M + 10.0, previous_had_traffic=True) is None


def test_minute_bounds_track_first_last_and_latest():
    bounds = MinuteBounds()
    bounds.add(M, M + 30)
    bounds.add(M, M + 5)
    bounds.add(M + 60, M + 61)
    assert bounds.latest == M + 61
    assert bounds.pop(M) == (M + 5, M + 30)
    assert bounds.pop(M) is None
    bounds.clear()
    assert bounds.pop(M + 60) is None and bounds.latest == M + 61