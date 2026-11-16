"""
Minutes in which traffic started or stopped (Day 43).

A minute that only partly contains traffic looks like a sudden volume drop on every service, so the model flags it
although nothing is wrong (seen when the generator starts or stops, and on Day 42 at the end of the load test).
Such minutes are not judged, like the first minute after the detection service starts:

- "started": the minute before had no traffic at all, and the first event of this minute came more than gap_s
  after the minute began (e.g. traffic began at :25);
- "stopped": no event at all has been seen from gap_s before the end of this minute until it was closed (traffic
  ended at :40 and nothing came since). The minute is closed 5 s (grace) after it ends, so this needs a quiet
  period of at least gap_s + 5 s.

Only whole-system edges count: if one service stops while the others keep logging, events keep arriving, the
minute is judged, and the silent service is flagged as before. When every service stops at once, the following
minutes are idle (no traffic), which is not an anomaly either (judge.py), so leaving out the partial minute in
between is consistent. While detection is catching up on a backlog, minutes close on event time, never before
newer events have been read, so "stopped" cannot fire then.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_GAP_S = 10.0


@dataclass
class MinuteBounds:
    """First and last event time (epoch seconds) per open minute, plus the latest event seen overall."""
    _bounds: dict[float, list[float]] = field(default_factory=dict)
    latest: float | None = None

    def add(self, minute_start: float, ts: float) -> None:
        bounds = self._bounds.get(minute_start)
        if bounds is None:
            self._bounds[minute_start] = [ts, ts]
        else:
            bounds[0] = min(bounds[0], ts)
            bounds[1] = max(bounds[1], ts)
        self.latest = ts if self.latest is None else max(self.latest, ts)

    def pop(self, minute_start: float) -> tuple[float, float] | None:
        bounds = self._bounds.pop(minute_start, None)
        return (bounds[0], bounds[1]) if bounds else None

    def clear(self) -> None:
        """Open minutes are rebuilt from Kafka after lost partitions (service.py); `latest` stays valid."""
        self._bounds.clear()


def traffic_edge(minute_start: float, window_s: float, bounds: tuple[float, float] | None, latest_seen: float | None,
                 previous_had_traffic: bool, gap_s: float = DEFAULT_GAP_S) -> str | None:
    """'started', 'stopped' or None (judge normally). A minute without any event is None: the idle rule applies."""
    if bounds is None or latest_seen is None:
        return None
    first, _last = bounds
    if not previous_had_traffic and first - minute_start > gap_s:
        return "started"
    if latest_seen < minute_start + window_s - gap_s:
        return "stopped"
    return None