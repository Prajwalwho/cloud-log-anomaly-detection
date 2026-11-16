"""Random scenario start offsets (Day 43): faults start at different seconds of the minute."""
import random

import pytest

from backend.log_generator.scenarios import SCENARIOS, build_schedule

NAMES = ["error_burst", "latency_spike", "new_error", "silent_service", "cascading_failure"]


def test_no_jitter_keeps_the_old_schedule():
    schedule, total = build_schedule(NAMES, warmup_s=300, gap_s=300)
    assert [offset for _, offset in schedule] == [300, 720, 1140, 1560, 1980]
    assert total == 1980 + 180 + 300


def test_jitter_spreads_starts_over_the_minute_and_keeps_gaps():
    schedule, total = build_schedule(NAMES, warmup_s=300, gap_s=300, jitter_s=60, rng=random.Random(7))
    offsets = [offset for _, offset in schedule]
    assert len({round(o % 60) for o in offsets}) > 1                   # not all at the same second
    assert 300 <= offsets[0] <= 360
    for (prev, start), current in zip(schedule, offsets[1:]):
        assert current - (start + prev.duration_s) >= 300                # the gap after each scenario is kept
    last, start = schedule[-1]
    assert total >= start + last.duration_s + 300


def test_jitter_is_reproducible_with_the_same_seed():
    a, _ = build_schedule(NAMES, jitter_s=60, rng=random.Random(101))
    b, _ = build_schedule(NAMES, jitter_s=60, rng=random.Random(101))
    assert [o for _, o in a] == [o for _, o in b]


def test_negative_jitter_is_rejected():
    with pytest.raises(ValueError):
        build_schedule(["error_burst"], jitter_s=-1)


def test_every_scenario_can_be_jittered():
    schedule, _ = build_schedule(list(SCENARIOS), jitter_s=60, rng=random.Random(1))
    assert len(schedule) == len(SCENARIOS)