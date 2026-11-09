# Elasticsearch Design
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 1.0
Elasticsearch: 8.17, single node

---

## 1. Purpose

Elasticsearch stores every validated log event and serves log search for the API and dashboard.
Structured results (windows, anomalies, alerts) are stored in PostgreSQL, not here.

## 2. Index naming

| Item | Value |
|---|---|
| Pattern | `logs-YYYY.MM.DD` (one index per UTC day) |
| Day chosen by | the event `timestamp` (UTC), not the ingestion time |
| Example | an event at 2026-11-10 02:00 IST (= 2026-11-09 20:30 UTC) goes to `logs-2026.11.09` |

Daily indices make retention cheap: deleting a day is deleting one index, instead of deleting
millions of documents one by one.

## 3. Index template

Installed (or updated) by the ingestion service at startup, name `logs-template`, pattern `logs-*`.

| Setting | Value | Reason |
|---|---|---|
| number_of_shards | 1 | Small daily volume; one shard per day is efficient |
| number_of_replicas | 0 | Single node: replicas could never be placed (cluster would be yellow) |
| refresh_interval | 5s | Logs become searchable within ~5 s; fewer refreshes = faster indexing |
| mappings.dynamic | strict | Unknown fields are rejected, protecting the index from schema drift |
| priority | 500 | Elasticsearch's built-in `logs` template (logs-*-*, priority 100) overlaps our pattern |

## 4. Field mappings

| Field | Type | Used for |
|---|---|---|
| schema_version | keyword | Contract version |
| event_id | keyword | Document id, lookups from anomaly records |
| timestamp | date | Time filters, sorting, daily index |
| service, host, level | keyword | Exact filters and counts (aggregations) |
| message | text | Full-text search (analysed into words) |
| trace_id | keyword | Reconstructing one request across services |
| endpoint | keyword | Filters by endpoint |
| status_code | integer | Range filters (e.g. >= 500) |
| latency_ms | float | Latency statistics |
| metadata | flattened | Free key-value data without creating a field per key |
| ingested_at | date | Pipeline latency (ingested_at − timestamp) |

`keyword` fields are stored as exact values (fast filtering and counting); `text` fields are split into
words (search). `service` must be keyword: "payment-service" must never match "payment".

## 5. Document id and idempotency

The document `_id` is the event's `event_id`, and documents are written with the `index` operation
(create or overwrite). Writing the same event twice therefore overwrites one document instead of
creating a duplicate.

Combined with the ingestion service's at-least-once delivery (offsets committed only after storage),
this gives effectively-once storage: no lost logs and no duplicates.

Verified on Day 10: re-reading the whole Kafka topic with a new consumer group left 18,190 existing
documents unduplicated.

## 6. Writing

- Bulk API, 500 documents per request.
- Documents rejected for overload (HTTP 429) are retried 3 times by the bulk helper.
- Connection failures: 5 attempts with exponential backoff (1, 2, 4, 8 s); then the consumer stops
  without committing offsets and resumes from Kafka after restart.
- Documents rejected permanently (e.g. mapping errors) go to the `logs.deadletter` Kafka topic.

## 7. Typical queries

| Need | Query |
|---|---|
| Recent errors of a service | bool filter: range timestamp, term service, terms level |
| Text search | match on message with operator "and" |
| One request across services | term trace_id, sorted by timestamp ascending |
| Counts per service / level | terms aggregations on keyword fields |
| Pipeline latency | runtime field ingested_at − timestamp, percentiles aggregation |

## 8. Retention (planned)

Daily indices older than N days can be deleted with a scheduled job or Elasticsearch
Index Lifecycle Management (ILM). Not needed at development volumes.