"""
Tumbling time windows per service for live detection (detection-design.md, Section 2).

Every log event is assigned to the window that contains its timestamp (UTC, aligned to multiples of
window_s, e.g. whole minutes), separately per service.

close_until(watermark) closes every window that ended at or before the watermark and returns one
WindowStats per KNOWN service for each closed window, including services that sent no logs in it.
Empty windows matter: a crashed service is visible only as a window with zero logs (silent_service fault).

Events that arrive after their window has been closed are counted as late and dropped, so they never
end up in the wrong window. The caller chooses the watermark, typically "latest event time minus a
grace period" (replay) or "current time minus a grace period" (live).
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

ERROR_LEVELS = frozenset({"ERROR", "FATAL"})
WARN_LEVELS = frozenset({"WARN"})


@dataclass
class WindowStats:
    """Everything observed for one service in one window."""
    service: str
    start_epoch: float
    window_s: float
    log_count: int = 0
    error_count: int = 0
    warn_count: int = 0
    template_counts: Counter = field(default_factory=Counter)
    latencies: list[float] = field(default_factory=list)

    @property
    def start(self) -> datetime:
        return datetime.fromtimestamp(self.start_epoch, tz=timezone.utc)

    @property
    def end(self) -> datetime:
        return datetime.fromtimestamp(self.start_epoch + self.window_s, tz=timezone.utc)

    def add(self, level: str, template_id: int, latency_ms: float | None) -> None:
        self.log_count += 1
        if level in ERROR_LEVELS:
            self.error_count += 1
        elif level in WARN_LEVELS:
            self.warn_count += 1
        self.template_counts[template_id] += 1
        if latency_ms is not None:
            self.latencies.append(float(latency_ms))


class WindowAggregator:
    def __init__(self, window_s: float = 60.0, services: Iterable[str] = ()) -> None:
        if window_s <= 0:
            raise ValueError("window_s must be positive")
        self.window_s = float(window_s)
        self.services: set[str] = set(services)
        self._open: dict[tuple[str, float], WindowStats] = {}
        self._next_close: float | None = None    # start of the oldest window not yet closed
        self.late_events = 0

    def window_start(self, timestamp: datetime) -> float:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return math.floor(timestamp.timestamp() / self.window_s) * self.window_s

    def add(self, service: str, timestamp: datetime, level: str, template_id: int,
            latency_ms: float | None = None) -> bool:
        """Add one event. Returns False (and counts it as late) if its window is already closed."""
        start = self.window_start(timestamp)
        if self._next_close is None:
            self._next_close = start
        if start < self._next_close:
            self.late_events += 1
            return False
        self.services.add(service)
        key = (service, start)
        stats = self._open.get(key)
        if stats is None:
            stats = self._open[key] = WindowStats(service, start, self.window_s)
        stats.add(level, template_id, latency_ms)
        return True

    def close_until(self, watermark: datetime) -> list[WindowStats]:
        """Close all windows ending at or before the watermark; one result per known service and window."""
        if self._next_close is None:
            return []
        if watermark.tzinfo is None:
            raise ValueError("watermark must be timezone-aware (UTC)")
        limit = watermark.timestamp()
        closed: list[WindowStats] = []
        while self._next_close + self.window_s <= limit:
            start = self._next_close
            for service in sorted(self.services):
                closed.append(self._open.pop((service, start), None) or WindowStats(service, start, self.window_s))
            self._next_close = start + self.window_s
        return closed

    @property
    def open_windows(self) -> int:
        return len(self._open)