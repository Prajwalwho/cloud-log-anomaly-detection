"""
Real-time feed behind /ws/live (api-contracts.md §4).

- AnomalyListener (a background thread) reads Kafka topic anomalies.detected and converts each message from the
  Kafka format (contracts.md §5.3: flat model_name/model_version/model_id) into the API's anomaly item
  (api-contracts.md §3.5: nested model, alert_id and feedback null).
- LiveHub fans every event out to all connected browsers, each with its own bounded queue.

Decisions (Day 30):
- Every API instance must see EVERY anomaly. A consumer group divides partitions between its members, which is
  right for sharing work but wrong for broadcasting, so the listener assigns itself all partitions directly (no
  group balancing, no committed offsets) at the current end of the topic. The live feed shows what happens from
  now on; history comes from GET /anomalies (the dashboard reloads it after reconnecting).
- A browser that stops reading must not block the others: when its queue is full, only that connection is closed.
- The API starts even when Kafka is down: the listener retries in the background.
"""
from __future__ import annotations

import asyncio
import json
import threading

from confluent_kafka import Consumer, TopicPartition

CLOSE = None          # queue marker: close this connection (client too slow)


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


class AnomalyListener(threading.Thread):
    def __init__(self, hub: LiveHub, bootstrap_servers: str, topic: str, group_id: str,
                 retry_s: float = 5.0) -> None:
        super().__init__(name="anomaly-listener", daemon=True)
        self.hub = hub
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.retry_s = retry_s
        self.ready = threading.Event()            # set once all partitions are assigned
        self._stop_event = threading.Event()      # (Thread already has a private _stop)
        self.received = 0
        self.invalid = 0

    def stop(self) -> None:
        self._stop_event.set()

    def _assign_at_end(self, consumer: Consumer) -> bool:
        try:
            metadata = consumer.list_topics(self.topic, timeout=5)
            topic = metadata.topics.get(self.topic)
            if topic is None or topic.error is not None or not topic.partitions:
                return False
            assignment = []
            for partition in topic.partitions:
                _low, high = consumer.get_watermark_offsets(TopicPartition(self.topic, partition), timeout=5)
                assignment.append(TopicPartition(self.topic, partition, high))   # explicit end offset
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
                    item = to_anomaly_item(json.loads(message.value()))
                except Exception:
                    self.invalid += 1
                    continue
                self.received += 1
                self.hub.publish_threadsafe({"type": "anomaly.created", "data": item})
        finally:
            consumer.close()