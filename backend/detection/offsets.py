"""
Kafka offset tracking for the detection service.

An event's offset may be committed only after the window it belongs to has been closed and written.
Committing earlier would lose the events of still-open windows if the service crashed. With this
tracker a restart replays exactly the events of the open windows.
"""
from __future__ import annotations

from collections import defaultdict, deque

from confluent_kafka import TopicPartition


class OffsetTracker:
    def __init__(self) -> None:
        self._pending: dict[tuple[str, int], deque[tuple[int, float]]] = defaultdict(deque)

    def add(self, topic: str, partition: int, offset: int, window_start: float) -> None:
        """Record a consumed message and the start (epoch seconds) of the window it went into."""
        self._pending[(topic, partition)].append((offset, window_start))

    def committable(self, closed_before: float | None) -> list[TopicPartition]:
        """Offsets to commit: per partition, just past the last message whose window is closed."""
        if closed_before is None:
            return []
        result = []
        for (topic, partition), queue in self._pending.items():
            last = None
            while queue and queue[0][1] < closed_before:
                last = queue.popleft()[0]
            if last is not None:
                result.append(TopicPartition(topic, partition, last + 1))
        return result

    @property
    def pending(self) -> int:
        return sum(len(q) for q in self._pending.values())