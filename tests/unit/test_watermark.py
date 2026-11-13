"""Unit tests for the per-partition watermark."""
from datetime import datetime, timedelta, timezone

from backend.detection.watermark import PartitionWatermark

T0 = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
P0, P1, P2 = ("logs.raw", 0), ("logs.raw", 1), ("logs.raw", 2)


def test_lagging_partition_holds_the_watermark_at_its_latest_event():
    wm = PartitionWatermark()
    wm.update(*P0, T0 + timedelta(minutes=5))      # inventory, far ahead
    wm.update(*P1, T0 + timedelta(minutes=1))      # gateway/auth/payment, behind
    assert wm.current([P0, P1], caught_up={P0}) == T0 + timedelta(minutes=1)


def test_lagging_partition_with_no_events_yet_blocks_closing():
    """Day 24 bug (second version): only partition 0 had delivered; 1 and 2 were still unread."""
    wm = PartitionWatermark()
    wm.update(*P0, T0 + timedelta(minutes=5))
    assert wm.current([P0, P1, P2], caught_up={P0}) is None


def test_all_caught_up_uses_wall_clock_or_latest_event():
    wm = PartitionWatermark()
    wm.update(*P0, T0)
    wm.update(*P1, T0 + timedelta(seconds=30))
    later = T0 + timedelta(minutes=3)
    assert wm.current([P0, P1], caught_up={P0, P1}, now_utc=later) == later
    assert wm.current([P0, P1], caught_up={P0, P1}, now_utc=T0 - timedelta(hours=1)) == T0 + timedelta(seconds=30)


def test_caught_up_partition_does_not_hold_the_watermark_back():
    wm = PartitionWatermark()
    wm.update(*P0, T0 + timedelta(minutes=1))      # caught up long ago
    wm.update(*P1, T0 + timedelta(minutes=5))      # still reading
    assert wm.current([P0, P1], caught_up={P0}) == T0 + timedelta(minutes=5)


def test_no_assignment_or_no_events_means_no_watermark():
    wm = PartitionWatermark()
    assert wm.current([], caught_up=set()) is None
    assert wm.current([P0], caught_up={P0}) is None