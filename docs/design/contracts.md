# Data Contracts
## Cloud Log Anomaly Detection for Proactive Fault Management

Document version: 1.2 (message schema_version stays "1.0": only optional fields and a new topic were added, see Section 7)
Status: Implemented for logs, dead-letter, anomalies, alert events and ground truth.

This document defines the formats of all data exchanged between system components. Every service must follow these contracts.

---

## 1. General Conventions

| Rule | Value |
|---|---|
| Encoding | JSON, UTF-8 |
| Field naming | snake_case |
| Timestamps | ISO 8601, UTC, millisecond precision (`2026-11-08T10:15:30.123Z`) |
| IDs | UUID v4 strings |
| Anomaly scores | Normalized to 0.0–1.0; higher means more anomalous; 0.5 = model threshold |
| Schema version | Every message carries `schema_version` |

All components store and process time in UTC. Conversion to local time happens only in the dashboard.

---

## 2. Log Event Schema

The canonical format of every log event in the system.

### 2.1 Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | Yes | Contract version, currently `"1.0"` |
| `event_id` | string (UUID) | Yes | Unique ID; used for deduplication and for linking anomalies to logs |
| `timestamp` | string (ISO 8601) | Yes | Time the event occurred at the source |
| `service` | string | Yes | Name of the service that produced the log |
| `host` | string | Yes | Node or container that produced the log |
| `level` | enum | Yes | One of `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL` |
| `message` | string | Yes | Raw log message, max 10,000 characters |
| `trace_id` | string | No | Request trace ID, links logs across services |
| `endpoint` | string | No | Request endpoint, e.g. `POST /api/payments` |
| `status_code` | integer | No | HTTP status code, 100–599 |
| `latency_ms` | number | No | Request latency in milliseconds, ≥ 0 |
| `metadata` | object | No | Any extra key-value data |

### 2.2 Example — normal request

```json
{
  "schema_version": "1.0",
  "event_id": "3f2b8c1e-9a4d-4e2b-8f61-2c7d9e0a1b34",
  "timestamp": "2026-11-08T10:15:30.123Z",
  "service": "payment-service",
  "host": "node-2",
  "level": "INFO",
  "message": "Payment processed for order 48213 in 142 ms",
  "trace_id": "a91c4e7f",
  "endpoint": "POST /api/payments",
  "status_code": 200,
  "latency_ms": 142.0,
  "metadata": {}
}
```

### 2.3 Example — error

```json
{
  "schema_version": "1.0",
  "event_id": "7d1e5a90-3c2f-4b8e-a6d4-91f0b2c3e5a7",
  "timestamp": "2026-11-08T10:15:31.877Z",
  "service": "payment-service",
  "host": "node-2",
  "level": "ERROR",
  "message": "Database connection timeout after 3000 ms",
  "trace_id": "b72d5f80",
  "endpoint": "POST /api/payments",
  "status_code": 500,
  "latency_ms": 3012.0,
  "metadata": {"db_host": "postgres-primary"}
}
```

### 2.4 Validation rules

The ingestion service rejects a message and sends it to `logs.deadletter` if:

1. It is not valid JSON.
2. Any required field is missing or has the wrong type.
3. `level` is not one of the allowed values.
4. `timestamp` cannot be parsed, or is more than 5 minutes in the future.
5. `status_code` is outside 100–599, or `latency_ms` is negative.
6. It contains top-level fields not defined in this contract (extra data belongs in `metadata`).

The detection service reads `logs.raw` independently and applies rules 1, 2 (for the fields it uses) and 4:
such messages are counted and skipped, so an invalid timestamp can never move its event-time watermark.
(Fast-mode test replays, whose timestamps are deliberately in the future, use `--allow-future`.)

Ingestion stores timestamps in Elasticsearch in the format of Section 1 (millisecond precision).

### 2.5 Ground truth is never part of the log

Log events do **not** carry anomaly labels. When the log generator injects a fault, it writes the ground truth to a separate file (Section 5.5). This prevents label leakage: the detector can never see the answer it is being evaluated on.

---

## 3. Simulated Environment

| Service | Role |
|---|---|
| `api-gateway` | Entry point; routes all requests |
| `auth-service` | Login and token validation |
| `order-service` | Order creation and lookup |
| `payment-service` | Payment processing; depends on the database |
| `inventory-service` | Stock checks and reservation |

Hosts: `node-1`, `node-2`, `node-3`.

The list may be extended. Detection must not assume a fixed set of services: services not in its configuration are
added when their first log arrives (they have no baseline until a model is trained with them).

---

## 4. Kafka Topics

The setup has a single broker, so replication factor is 1 for all topics. This is a known limitation of the development setup; production would use a replication factor of 3.

| Topic | Partitions | Retention | Message key | Producer | Consumers |
|---|---|---|---|---|---|
| `logs.raw` | 3 | 24 hours | `service` | Log generator / applications | Ingestion (`ingestion-group`), Detection (`detection-group`) |
| `logs.deadletter` | 1 | 7 days | none | Ingestion | Manual inspection |
| `anomalies.detected` | 1 | 7 days | `service` | Detection | Alerting (`alerting-group`), API (all partitions assigned, see 4.2) |
| `alerts.events` | 1 | 7 days | `service` | Alerting | API (all partitions assigned, see 4.2) |

`alerts.events` (added in Phase 8) is created by the alerting service and the API on start-up if it does not exist;
the other topics are created by `kafka-init`.

### 4.1 Why `service` is the message key

Kafka keeps message order only within a partition. Keying by `service` sends all logs of one service to the same partition, so the detection service receives each service's logs in order. This is needed to build correct time windows.

Partitions are not consumed at the same pace, especially when catching up on a backlog. The detection service
therefore closes windows using a per-partition watermark (detection-design.md, Section 2).

### 4.2 Consumer groups

Ingestion and detection use different consumer groups on `logs.raw`, so each receives every message. Slow detection does not delay storage, and either service can be restarted or scaled independently.

The alerting service uses `alerting-group`; a new group starts at the end of `anomalies.detected`, so old and test
messages are not turned into alerts.

The API broadcasts events to browsers, so every API instance must receive every message. It does not join a
balanced consumer group (which would divide partitions between instances); it assigns itself all partitions at
the current end offset and never commits offsets (`api-group` is used as a label only).

---

## 5. Message Formats

### 5.1 `logs.raw`

Exactly the log event schema in Section 2.

### 5.2 `logs.deadletter`

```json
{
  "schema_version": "1.0",
  "failed_at": "2026-11-08T10:15:32.004Z",
  "source_topic": "logs.raw",
  "source_partition": 1,
  "source_offset": 58213,
  "error": "Field 'level': value 'CRITICAL' is not a valid level",
  "raw_message": "{\"service\": \"auth-service\", \"level\": \"CRITICAL\", ...}"
}
```

`raw_message` holds the original message exactly as received, as a string, so nothing is lost.

### 5.3 `anomalies.detected`

Published by the detection service after the anomaly is stored in PostgreSQL (PostgreSQL is the source of truth).

```json
{
  "schema_version": "1.0",
  "anomaly_id": "c4e8a2f1-6b3d-4a9e-8c7f-0d1e2b3a4c5d",
  "detected_at": "2026-11-08T10:16:02.511Z",
  "service": "payment-service",
  "window_start": "2026-11-08T10:15:00.000Z",
  "window_end": "2026-11-08T10:16:00.000Z",
  "anomaly_score": 0.84,
  "severity": "CRITICAL",
  "model_name": "live-pca",
  "model_version": "1.1.0",
  "model_id": 5,
  "summary": {
    "log_count": 282,
    "error_rate": 0.422,
    "warn_rate": 0.004,
    "avg_latency_ms": 137.4,
    "p95_latency_ms": 261.4,
    "new_templates": 0,
    "raw_score": 244.5,
    "threshold": 9.9,
    "rule": null,
    "reasons": ["error rate 42.2%"]
  },
  "sample_event_ids": [
    "7d1e5a90-3c2f-4b8e-a6d4-91f0b2c3e5a7"
  ]
}
```

| Field | Description |
|---|---|
| `window_start`, `window_end` | The 60-second window that was scored |
| `anomaly_score` | Normalized 0.0–1.0 model output; 0.5 = threshold (log-ratio normalisation, detection-design.md §5) |
| `severity` | One of `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`; graded by rules (detection-design.md §5) |
| `model_name`, `model_version` | The registered model that produced the anomaly |
| `model_id` | Optional (added in document version 1.1): id in `model_registry` |
| `summary` | Window statistics so the dashboard can explain the anomaly (table below) |
| `sample_event_ids` | Up to 10 log IDs, errors first, then warnings, then others; full logs are fetched from Elasticsearch |

`summary` fields:

| Field | Type | Description |
|---|---|---|
| `log_count` | integer | Log lines in the window (0 for a silent service) |
| `error_rate` | number | ERROR/FATAL lines / log_count (0 if no logs) |
| `warn_rate` | number | Optional (1.1): WARN lines / log_count |
| `avg_latency_ms` | number or null | Mean latency of lines with latency |
| `p95_latency_ms` | number or null | Optional (1.1): 95th percentile latency |
| `new_templates` | integer | Distinct message types not seen in training |
| `raw_score` | number | Optional (1.1): model score before normalisation |
| `threshold` | number | Optional (1.1): model threshold for raw_score |
| `rule` | string or null | Optional (1.1): `"no_logs"` if flagged by the no-logs rule |
| `reasons` | array of strings | Optional (1.1): human-readable reasons for the severity, strongest first |

### 5.4 `alerts.events`

Published by the alerting service whenever an alert is created, updated (new anomaly, escalation, notification
sent) or resolved. The alert is in the API's alert item format (api-contracts.md §3.8), so the API forwards it to
browsers unchanged.

```json
{
  "schema_version": "1.0",
  "type": "alert.updated",
  "anomaly_id": "c4e8a2f1-6b3d-4a9e-8c7f-0d1e2b3a4c5d",
  "alert": {
    "id": "135cf5d6-b1ca-4235-acc0-d9836020138d",
    "service": "payment-service",
    "severity": "CRITICAL",
    "title": "Error rate increase in payment-service",
    "message": "error rate 38.9%",
    "status": "OPEN",
    "occurrence_count": 2,
    "first_seen_at": "2026-11-13T19:13:06.000Z",
    "last_seen_at": "2026-11-13T19:14:05.000Z",
    "acknowledged_at": null,
    "acknowledged_by": null,
    "resolved_at": null,
    "notification_sent": true
  }
}
```

| Field | Description |
|---|---|
| `type` | `alert.created` or `alert.updated` |
| `anomaly_id` | The anomaly that caused the change; `null` when the alert was resolved automatically |
| `alert` | The alert after the change |

Alert lifecycle (alerting service):
- An anomaly joins an `OPEN`/`ACKNOWLEDGED` alert of the same service whose `last_seen_at` is within 5 minutes;
  otherwise a new alert opens, but only from anomalies of severity `MEDIUM` or higher.
- Alert severity is the highest severity of its anomalies; `message` holds the latest anomaly's reasons.
- An alert without new anomalies for 5 minutes is `RESOLVED` automatically. Operators can acknowledge or resolve
  alerts through the API.

### 5.5 Ground-truth record (file, not Kafka)

Written by the log generator to `data/ground_truth/<run_id>.jsonl`, one JSON object per line:

```json
{
  "run_id": "run-20261108-101500",
  "scenario": "error_burst",
  "service": "payment-service",
  "start": "2026-11-08T10:15:00.000Z",
  "end": "2026-11-08T10:17:00.000Z",
  "description": "Database timeouts causing 40% error rate"
}
```

During evaluation, a detection window counts as a true positive if it overlaps a ground-truth fault interval for the same service.

---

## 6. Change Policy

- Adding an optional field: allowed; update this document.
- Removing or renaming a field, or changing a type: increment `schema_version` and update every component.

## 7. Change Log

| Document version | Change |
|---|---|
| 1.0 | Initial contracts (Day 1) |
| 1.1 | `anomalies.detected`: optional `model_id`; summary fields `warn_rate`, `p95_latency_ms`, `raw_score`, `threshold`, `rule`, `reasons`. Detection-side validation rules (§2.4). Day 25 publisher sent a nested `model` object and non-millisecond timestamps, which violated §5.3; fixed in code (Day 27) |
| 1.2 | New topic `alerts.events` (§4, §5.4) with the alert lifecycle; alerting consumer group; API consumption without a balanced group (§4.2); ingestion stores millisecond timestamps (Day 29) |