"""
Elasticsearch sink for the ingestion service.

- Daily indices: <prefix>-YYYY.MM.DD, chosen by the event timestamp (UTC), so old days
  can be deleted as whole indices.
- Index template: explicit field types, 1 shard, 0 replicas (single node -> cluster stays
  green), strict mapping (unknown fields rejected), refresh every 5 s (near real-time search).
- Idempotent writes: the document id is the event_id, so writing the same event twice
  overwrites it instead of creating a duplicate. This makes the consumer's at-least-once
  delivery safe.
- Transient failures (Elasticsearch down or slow) are retried with exponential backoff.
  If they persist, an exception stops the consumer before offsets are committed, so no
  logs are lost; they are re-read from Kafka after restart.
- Documents Elasticsearch rejects permanently are returned to the consumer, which sends
  them to the dead-letter topic.
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from datetime import datetime, timezone

from elasticsearch import ConnectionError as ESConnectionError
from elasticsearch import ConnectionTimeout, Elasticsearch, helpers

from .validator import LogEvent, utc_now_iso

MAX_ATTEMPTS = 5
BULK_CHUNK_SIZE = 500

# Elasticsearch 8 has a built-in template "logs" (pattern logs-*-*, priority 100) for its own
# data streams. Our pattern logs-* overlaps it, and two overlapping templates may not share a
# priority, so ours uses a higher one. Our index names (logs-YYYY.MM.DD) have a single dash and
# never match logs-*-*, so the built-in template is unaffected.
TEMPLATE_PRIORITY = 500


def build_index_template(prefix: str) -> dict:
    """Composable index template applied to every <prefix>-* index."""
    return {
        "index_patterns": [f"{prefix}-*"],
        "priority": TEMPLATE_PRIORITY,
        "meta": {"description": "Log events (contracts.md, Section 2)", "schema_version": "1.0"},
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,      # single node: replicas could never be placed
                "refresh_interval": "5s",     # logs become searchable within ~5 s
            },
            "mappings": {
                "dynamic": "strict",          # reject fields not defined below
                "properties": {
                    "schema_version": {"type": "keyword"},
                    "event_id": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "service": {"type": "keyword"},
                    "host": {"type": "keyword"},
                    "level": {"type": "keyword"},
                    "message": {"type": "text"},
                    "trace_id": {"type": "keyword"},
                    "endpoint": {"type": "keyword"},
                    "status_code": {"type": "integer"},
                    "latency_ms": {"type": "float"},
                    "metadata": {"type": "flattened"},   # free key-value data without mapping explosion
                    "ingested_at": {"type": "date"},
                },
            },
        },
    }


def index_name(prefix: str, timestamp: datetime) -> str:
    """Daily index for an event, by its UTC day: logs-2026.11.09."""
    return f"{prefix}-{timestamp.astimezone(timezone.utc):%Y.%m.%d}"


def to_document(event: LogEvent, ingested_at: str) -> dict:
    """Elasticsearch document: the log event plus the time ingestion stored it."""
    document = event.model_dump(mode="json")
    document["ingested_at"] = ingested_at
    return document


class ElasticsearchSink:
    def __init__(
        self,
        url: str,
        index_prefix: str = "logs",
        client: Elasticsearch | None = None,
        retry_backoff_s: float = 1.0,
    ) -> None:
        self.url = url
        self.index_prefix = index_prefix
        self.template_name = f"{index_prefix}-template"
        self.es = client or Elasticsearch(url, request_timeout=30)
        self.retry_backoff_s = retry_backoff_s
        self.indexed_by_index: Counter = Counter()

    def ensure_ready(self) -> None:
        """Check the connection and install (or update) the index template."""
        try:
            self.es.info()
        except (ESConnectionError, ConnectionTimeout) as exc:
            raise RuntimeError(
                f"Elasticsearch not reachable at {self.url} ({exc}). "
                f"Is the stack running? Start it with: .\\scripts\\start.ps1 up"
            ) from exc
        self.es.indices.put_index_template(name=self.template_name, **build_index_template(self.index_prefix))

    def write_batch(self, events: list[LogEvent]) -> list[tuple[LogEvent, str]]:
        """
        Index a batch of events. Returns the events Elasticsearch rejected permanently,
        with the reason. Raises RuntimeError if Elasticsearch stays unavailable.
        """
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self._bulk(events)
            except (ESConnectionError, ConnectionTimeout) as exc:
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError(f"Elasticsearch unavailable after {MAX_ATTEMPTS} attempts: {exc}") from exc
                wait = self.retry_backoff_s * 2 ** (attempt - 1)
                print(f"  Elasticsearch unavailable (attempt {attempt}/{MAX_ATTEMPTS}), "
                      f"retrying in {wait:.0f} s", file=sys.stderr)
                time.sleep(wait)
        return []   # not reached

    def _bulk(self, events: list[LogEvent]) -> list[tuple[LogEvent, str]]:
        by_id = {str(event.event_id): event for event in events}
        ingested_at = utc_now_iso()
        actions = (
            {
                "_op_type": "index",                       # create or overwrite: idempotent
                "_index": index_name(self.index_prefix, event.timestamp),
                "_id": str(event.event_id),
                "_source": to_document(event, ingested_at),
            }
            for event in events
        )

        rejected: list[tuple[LogEvent, str]] = []
        indexed: Counter = Counter()
        for ok, item in helpers.streaming_bulk(
            self.es, actions, chunk_size=BULK_CHUNK_SIZE,
            raise_on_error=False,          # per-document errors are returned, not raised
            max_retries=3, initial_backoff=1,   # retry documents rejected for overload (HTTP 429)
        ):
            result = item.get("index", {})
            if ok:
                indexed[result.get("_index")] += 1
                continue
            error = result.get("error", {})
            if isinstance(error, dict):
                reason = f"elasticsearch: {error.get('type', 'error')}: {error.get('reason', '')}"
            else:
                reason = f"elasticsearch: {error}"
            event = by_id.get(result.get("_id"))
            if event is not None:
                rejected.append((event, reason[:1000]))

        self.indexed_by_index.update(indexed)   # counted only after the whole batch succeeded
        return rejected