"""
Event-time watermark over several Kafka partitions.

A window may be closed only when no assigned partition can still deliver events for it. Kafka does not
deliver partitions at the same pace (especially when catching up on a backlog). Day 24 showed two
wrong rules:
  1. latest event time over all partitions: closes windows before slower partitions deliver;
  2. minimum over partitions SEEN so far: a lagging partition that has delivered nothing yet is ignored.
Both dropped tens of thousands of events as late and produced false "no logs" anomalies.

Correct rule, using whether each assigned partition is caught up (read up to its high-water mark):
- if a partition that is NOT caught up has delivered no events yet: no watermark (close nothing);
- if some partitions are not caught up: minimum of their latest event times;
- if all partitions are caught up: the later of the latest event time and wall-clock time.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

Key = tuple[str, int]


class PartitionWatermark:
    def __init__(self) -> None:
        self._latest: dict[Key, datetime] = {}

    def update(self, topic: str, partition: int, event_time: datetime) -> None:
        key = (topic, partition)
        if key not in self._latest or event_time > self._latest[key]:
            self._latest[key] = event_time

    def current(self, assigned: Iterable[Key], caught_up: set[Key],
                now_utc: datetime | None = None) -> datetime | None:
        assigned = list(assigned)
        if not assigned:
            return None
        behind = [key for key in assigned if key not in caught_up]
        if behind:
            if any(key not in self._latest for key in behind):
                return None                     # a lagging partition has not delivered anything yet
            return min(self._latest[key] for key in behind)
        if not self._latest:
            return None
        now_utc = now_utc or datetime.now(timezone.utc)
        return max(max(self._latest.values()), now_utc)