"""
Telegram messages sent from a background thread (Day 43).

Day 41 measured that the alerting service waited for each Telegram send (about 1 s, up to 11 s on a slow connection)
before it handled the next anomaly, so in a multi-service failure every later alert opened a send later. Now the
loop only queues the message and moves on; one worker thread sends the queued messages in order (so "new" always
goes out before "escalated" and "resolved" of the same alert) and reports each successful send back (on_sent), where
the service records it (notified_at) and publishes the updated alert.

While a message for an alert is queued or being sent, the alert counts as notified (is_pending), so a second "new"
message is not queued for it. If the send fails, the alert stays not notified and the next update tries again, as
before.
"""
from __future__ import annotations

import queue
import threading
from collections import Counter
from collections.abc import Callable

from .notifier import format_message

_STOP = None


class BackgroundSender:
    def __init__(self, notifier, on_sent: Callable[[str, dict], None], max_queue: int = 1000) -> None:
        self.notifier = notifier                 # TelegramNotifier (or anything with .enabled and .send(text))
        self.on_sent = on_sent
        self.dropped = 0
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue)
        self._pending: Counter = Counter()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="telegram-sender", daemon=True)
        self._thread.start()

    @property
    def enabled(self) -> bool:
        return self.notifier.enabled

    def is_pending(self, alert_id: str) -> bool:
        with self._lock:
            return self._pending[alert_id] > 0

    def submit(self, kind: str, alert: dict) -> None:
        """Queue a message and return at once."""
        with self._lock:
            self._pending[alert["id"]] += 1
        try:
            self._queue.put_nowait((kind, alert))
        except queue.Full:                       # only if Telegram has been unreachable for a long time
            self._done(alert["id"])
            self.dropped += 1
            print(f"  [WARN] notification queue full; {kind} message for {alert['service']} dropped")

    def close(self, timeout_s: float = 15.0) -> int:
        """Send what is queued (up to timeout_s), stop the worker; returns how many messages were left unsent."""
        try:
            self._queue.put(_STOP, timeout=timeout_s)
            self._thread.join(timeout_s)
        except queue.Full:
            return self._queue.qsize()
        except KeyboardInterrupt:                # a second Ctrl+C: stop waiting (the worker is a daemon thread)
            pass
        return self._queue.qsize() if self._thread.is_alive() else 0

    def _done(self, alert_id: str) -> None:
        with self._lock:
            self._pending[alert_id] -= 1
            if self._pending[alert_id] <= 0:
                del self._pending[alert_id]

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            kind, alert = item
            try:
                if self.notifier.send(format_message(kind, alert)):
                    self.on_sent(kind, alert)
            except Exception as exc:             # never let one message stop the worker
                print(f"  [WARN] notification for {alert['service']} failed: {type(exc).__name__}")
            finally:
                self._done(alert["id"])