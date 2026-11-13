"""
From log events to closed windows: the processing chain shared by training, offline evaluation
and the live detection service.

    events -> Drain template id -> WindowAggregator -> closed WindowStats

Also the future-timestamp rule of the log contract (contracts.md): a timestamp more than 5 minutes in the
future is invalid. Ingestion enforces it in its validator; the detection service reads logs.raw directly and
applies the same rule, so one bogus timestamp can never advance the watermark (Day 25 finding).
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

from drain3 import TemplateMiner

from .windowing import WindowAggregator, WindowStats

MAX_FUTURE_S = 300.0


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def too_far_in_future(timestamp: datetime, now: datetime | None = None, max_future_s: float = MAX_FUTURE_S) -> bool:
    now = now or datetime.now(timezone.utc)
    return timestamp - now > timedelta(seconds=max_future_s)


def read_events(path: Path) -> Iterator[dict]:
    """Log events from a JSONL file (one event per line, contracts.md Section 2)."""
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def build_windows(
    events: Iterable[dict],
    miner: TemplateMiner,
    services: Iterable[str],
    window_s: float = 60.0,
    grace_s: float = 5.0,
    complete_only: bool = True,
) -> list[WindowStats]:
    """
    Parse events with Drain and group them into closed windows (offline: files, no future-timestamp check).

    complete_only drops the partial windows at the very start and end of the data
    (the first and last minute are only partly covered and would look like outliers).
    """
    aggregator = WindowAggregator(window_s, services=services)
    grace = timedelta(seconds=grace_s)
    windows: list[WindowStats] = []
    first: datetime | None = None
    last: datetime | None = None

    for event in events:
        ts = parse_timestamp(event["timestamp"])
        template_id = miner.add_log_message(event["message"])["cluster_id"]
        aggregator.add(event["service"], ts, event["level"], template_id, event.get("latency_ms"))
        windows += aggregator.close_until(ts - grace)
        first = first or ts
        last = ts

    if last is None:
        return []
    windows += aggregator.close_until(last + timedelta(seconds=window_s) + grace)   # flush the end
    if complete_only:
        windows = [w for w in windows if w.start >= first and w.end <= last]
    return windows