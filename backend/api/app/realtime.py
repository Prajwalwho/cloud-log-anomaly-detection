"""
Real-time feed behind /ws/live (api-contracts.md §4).

- FeedListener (a background thread) reads Kafka topics and converts each message into a live event:
    anomalies.detected (contracts.md §5.3) -> {"type": "anomaly.created", "data": anomaly item (api-contracts §3.5)}
    alerts.events      (Phase 8)          -> {"type": "alert.created" | "alert.updated", "data": alert item (§3.8)}
- LiveHub fans every event out to all connected browsers, each with its own bounded queue.

Decisions (Day 30):
- Every API instance must see EVERY event. A consumer group divides partitions between its members, which is
  right for sharing work but wrong for broadcasting, so the listener assigns itself all partitions directly (no
  group balancing, no committed offsets) at the current end of each topic. History comes from the REST endpoints.
- A browser that stops reading must not block the others: when its queue is full, only that connection is closed.
- The API starts even when Kafka is down: the listener retries in the background.
"""
from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable

from confluent_kafka import Consumer, TopicPartition

from backend.common.kafka_topics import ensure_topics

CLOSE = None          # queue marker: close this connection (client too slow)
ALERT_EVENT_TYPES = {"alert.created", "alert.updated"}


class LiveHub:
    def __init__(self, loop: asyncio.AbstractEventLoop, queue_size: int = 100) -> None:
        self.loop = loop
        self.queue_size = queue_size
        self._clients: set[asyncio.Queue] = set()
        self.sent = 0
        self.dropped_clients = 0

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def register(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.queue_size)
        self._clients.add(queue)
        return queue

    def unregister(self, queue: asyncio.Queue) -> None:
        self._clients.discard(queue)

    def publish(self, event: dict) -> None:
        """Send an event to every client. Must run in the event loop's thread."""
        for queue in list(self._clients):
            try:
                queue.put_nowait(event)
                self.sent += 1
            except asyncio.QueueFull:
                self._clients.discard(queue)
                self.dropped_clients += 1
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(CLOSE)

    def publish_threadsafe(self, event: dict) -> None:
        """Send an event from another thread (Kafka listener, sync endpoints)."""
        try:
            self.loop.call_soon_threadsafe(self.publish, event)
        except RuntimeError:
            pass                                  # event loop already closed (shutting down)


def to_anomaly_item(message: dict) -> dict:
    """anomalies.detected message (contracts.md §5.3) -> anomaly item (api-contracts.md §3.5)."""
    return {
        "id": message["anomaly_id"],
        "service": message["service"],
        "detected_at": message["detected_at"],
        "window_start": message["window_start"],
        "window_end": message["window_end"],
        "anomaly_score": message["anomaly_score"],
        "severity": message["severity"],
        "model": {"id": message.get("model_id"), "name": message["model_name"], "version": message["model_version"]},
        "summary": message.get("summary", {}),
        "alert_id": None,
        "feedback": None,
    }


def anomaly_event(message: dict) -> dict:
    return {"type": "anomaly.created", "data": to_anomaly_item(message)}


def alert_event(message: dict) -> dict:
    """alerts.events message -> live event; the alert item is already in the API format."""
    if message.get("type") not in ALERT_EVENT_TYPES or not isinstance(message.get("alert"), dict):
        raise ValueError("not an alert event")
    return {"type": message["type"], "data": message["alert"]}


class FeedListener(threading.Thread):
    def __init__(self, hub: LiveHub, bootstrap_servers: str, converters: dict[str, Callable[[dict], dict]],
                 group_id: str, retry_s: float = 5.0) -> None:
        super().__init__(name="feed-listener", daemon=True)
        self.hub = hub
        self.bootstrap_servers = bootstrap_servers
        self.converters = converters              # topic -> message-to-event function
        self.group_id = group_id
        self.retry_s = retry_s
        self.ready = threading.Event()            # set once all partitions of all topics are assigned
        self._stop_event = threading.Event()      # (Thread already has a private _stop)
        self.received = 0
        self.invalid = 0

    def stop(self) -> None:
        self._stop_event.set()

    def _assign_at_end(self, consumer: Consumer) -> bool:
        try:
            ensure_topics(self.bootstrap_servers, {topic: 1 for topic in self.converters}, timeout_s=5)
            assignment = []
            for name in self.converters:
                topic = consumer.list_topics(name, timeout=5).topics.get(name)
                if topic is None or topic.error is not None or not topic.partitions:
                    return False
                for partition in topic.partitions:
                    _low, high = consumer.get_watermark_offsets(TopicPartition(name, partition), timeout=5)
                    assignment.append(TopicPartition(name, partition, high))   # explicit end offset
            consumer.assign(assignment)
            return True
        except Exception:
            return False

    def run(self) -> None:
        consumer = Consumer({
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,            # label only: partitions are assigned, offsets never committed
            "client.id": "api-live",
            "enable.auto.commit": False,
        })
        try:
            while not self._stop_event.is_set() and not self._assign_at_end(consumer):
                self._stop_event.wait(self.retry_s)
            if self._stop_event.is_set():
                return
            self.ready.set()
            while not self._stop_event.is_set():
                message = consumer.poll(1.0)
                if message is None or message.error():
                    continue
                try:
                    event = self.converters[message.topic()](json.loads(message.value()))
                except Exception:
                    self.invalid += 1
                    continue
                self.received += 1
                self.hub.publish_threadsafe(event)
        finally:
            consumer.close()