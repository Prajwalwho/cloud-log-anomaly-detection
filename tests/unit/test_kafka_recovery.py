"""Recovery after a lost consumer-group membership (Day 40, 43): safe commits, and detection's state reset."""
from datetime import datetime, timedelta, timezone

import pytest
from confluent_kafka import KafkaError, KafkaException, TopicPartition

from backend.common.kafka_commit import commit_safely
from backend.detection.offsets import OffsetTracker
from backend.detection.watermark import PartitionWatermark
from backend.detection.windowing import WindowAggregator


class FakeConsumer:
    def __init__(self, error_code: int | None = None) -> None:
        self.error_code = error_code
        self.calls = []

    def commit(self, offsets=None, asynchronous=True):
        self.calls.append(offsets)
        if self.error_code is not None:
            raise KafkaException(KafkaError(self.error_code))


def test_commit_succeeds_normally():
    consumer = FakeConsumer()
    assert commit_safely(consumer) is True
    assert commit_safely(consumer, [TopicPartition("logs.raw", 0, 10)]) is True
    assert len(consumer.calls) == 2


@pytest.mark.parametrize("code", [-142, 22, 25, 27, -168])
def test_lost_membership_is_reported_not_raised(code, capsys):
    assert commit_safely(FakeConsumer(code), label="ingestion") is False
    if code != -168:                                   # "nothing to commit" is silent
        assert "ingestion: offsets not committed" in capsys.readouterr().err


def test_other_commit_errors_are_raised():
    with pytest.raises(KafkaException):
        commit_safely(FakeConsumer(-195))              # _TRANSPORT: a real failure, not a rebalance


T0 = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


def test_discard_open_keeps_closed_windows_closed():
    agg = WindowAggregator(60, services=["payment-service"])
    agg.add("payment-service", T0 + timedelta(seconds=10), "INFO", 1)
    agg.add("payment-service", T0 + timedelta(seconds=70), "INFO", 1)
    closed = agg.close_until(T0 + timedelta(seconds=65))
    assert [w.log_count for w in closed] == [1]

    assert agg.discard_open() == 1                    # the 10:01 window, rebuilt from the replay
    assert agg.open_windows == 0
    # replay: the event of the closed 10:00 window is dropped as late, the open one is counted once
    assert agg.add("payment-service", T0 + timedelta(seconds=10), "INFO", 1) is False
    assert agg.add("payment-service", T0 + timedelta(seconds=70), "INFO", 1) is True
    reopened = agg.close_until(T0 + timedelta(seconds=125))
    assert [w.log_count for w in reopened] == [1]
    assert agg.late_events == 1


def test_offset_tracker_clear():
    tracker = OffsetTracker()
    tracker.add("logs.raw", 0, 5, T0.timestamp())
    tracker.add("logs.raw", 1, 9, T0.timestamp())
    tracker.clear()
    assert tracker.pending == 0
    assert tracker.committable(T0.timestamp() + 60) == []


def test_watermark_is_reset_so_replayed_events_are_not_late():
    # Day 43: partitions were reassigned and re-read from older offsets. The old latest event times let the
    # watermark run ahead of the replay, so minutes closed early and replayed events were dropped as late.
    wm = PartitionWatermark()
    p0, p1 = ("logs.raw", 0), ("logs.raw", 1)
    wm.update(*p0, T0 + timedelta(minutes=5))          # read before the rebalance
    wm.update(*p1, T0 + timedelta(minutes=5))
    assert wm.current([p0, p1], caught_up={p1}) == T0 + timedelta(minutes=5)    # stale: p0 re-read from T0

    wm.clear()                                         # what the service now does on revoke / lost
    assert wm.current([p0, p1], caught_up={p1}) is None                         # wait for p0's replay
    wm.update(*p0, T0 + timedelta(seconds=30))
    assert wm.current([p0, p1], caught_up={p1}) == T0 + timedelta(seconds=30)   # follows the replay