# Database Design
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 1.0
Database: PostgreSQL 16

---

## 1. What is stored where

| Data | Store | Reason |
|---|---|---|
| Raw log events | Elasticsearch | High volume, full-text search, time-range filtering |
| Scored windows, anomalies, alerts, models, services | PostgreSQL | Structured data, relations, transactions, status updates |

PostgreSQL never stores raw logs. It references them through `event_id` values (`anomalies.sample_event_ids`), which the API resolves from Elasticsearch.

---

## 2. Entity Relationships

```
services ──1:N── detection_windows ──1:0..1── anomalies ──N:0..1── alerts
                        │                         │                   │
model_registry ──1:N────┘─────────────────────────┘     services ──1:N┘
```

- Every scored window is stored, whether it is normal or anomalous.
- A window flagged as anomalous produces exactly one anomaly.
- Several anomalies of the same service can be grouped into one alert (deduplication).

---

## 3. Tables

### 3.1 `services`
Services seen in the log stream. New services are registered automatically the first time they appear.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| name | VARCHAR(100) UNIQUE | e.g. `payment-service` |
| description | TEXT | Optional |
| created_at | TIMESTAMPTZ | |

### 3.2 `model_registry`
Every trained model version and its evaluation results.

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| name | VARCHAR(100) | e.g. `isolation_forest` |
| version | VARCHAR(20) | e.g. `1.0.0`; (name, version) is unique |
| algorithm | VARCHAR(50) | `isolation_forest`, `one_class_svm`, `pca`, `statistical` |
| file_path | TEXT | Path to the saved model file |
| parameters | JSONB | Hyperparameters |
| threshold | DOUBLE PRECISION | Decision threshold on the normalized score |
| training_data | TEXT | Description of the training data |
| training_samples | INTEGER | Number of training windows |
| metrics | JSONB | Precision, recall, F1, etc. |
| is_active | BOOLEAN | Only one model can be active at a time |
| trained_at | TIMESTAMPTZ | |

### 3.3 `detection_windows`
One row per scored 60-second window per service. This table powers the trend charts and the live evaluation.

| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| service_id | FK → services | |
| model_id | FK → model_registry | Model that scored the window |
| window_start, window_end | TIMESTAMPTZ | |
| log_count, error_count, warn_count | INTEGER | |
| avg_latency_ms, p95_latency_ms | DOUBLE PRECISION | Null if no latency data |
| unique_templates, new_templates | INTEGER | From Drain parsing |
| anomaly_score | DOUBLE PRECISION | 0–1 |
| is_anomaly | BOOLEAN | score ≥ model threshold |
| created_at | TIMESTAMPTZ | |

Unique on (service_id, window_start, model_id), so reprocessing a window cannot create duplicates.

Size estimate: 5 services × 1,440 windows/day = 7,200 rows/day, which is small for PostgreSQL.

### 3.4 `anomalies`
Windows that crossed the threshold.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | Same as `anomaly_id` in the Kafka message |
| window_id | FK → detection_windows, UNIQUE | |
| service_id | FK → services | |
| model_id | FK → model_registry | |
| alert_id | FK → alerts, nullable | Set when an alert is created or grouped |
| detected_at | TIMESTAMPTZ | |
| window_start, window_end | TIMESTAMPTZ | Copied from the window for fast queries |
| anomaly_score | DOUBLE PRECISION | 0–1 |
| severity | VARCHAR(10) | LOW / MEDIUM / HIGH / CRITICAL |
| summary | JSONB | Window statistics shown on the dashboard |
| sample_event_ids | TEXT[] | Up to 10 log IDs in Elasticsearch |
| feedback | VARCHAR(20), nullable | CONFIRMED / FALSE_POSITIVE, set by an administrator |
| feedback_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

The `feedback` column lets administrators mark false positives. It gives a real-world precision measure and could be used for future model retraining.

### 3.5 `alerts`
Notifications for administrators, with a status lifecycle.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| service_id | FK → services | |
| severity | VARCHAR(10) | Highest severity among grouped anomalies |
| title | VARCHAR(200) | e.g. "High error rate in payment-service" |
| message | TEXT | |
| status | VARCHAR(15) | OPEN → ACKNOWLEDGED → RESOLVED |
| occurrence_count | INTEGER | Number of anomalies grouped into this alert |
| first_seen_at, last_seen_at | TIMESTAMPTZ | |
| acknowledged_at, acknowledged_by, resolved_at | | Lifecycle tracking |
| notification_sent, notified_at | | Telegram/email delivery status |
| created_at | TIMESTAMPTZ | |

**Deduplication rule (implemented in Phase 8):** while an OPEN alert exists for a service, new anomalies for that service are attached to it. The alert's `occurrence_count` and `last_seen_at` are updated and no new notification is sent.

---

## 4. Write Ownership

Each table has a single writer, which avoids conflicting updates between services.

| Table | Written by |
|---|---|
| services | Detection (auto-registration) |
| model_registry | Training script |
| detection_windows, anomalies (creation) | Detection service |
| alerts, anomalies.alert_id | Alerting service |
| alerts.status, anomalies.feedback | API (administrator actions) |

---

## 5. Indexes

| Index | Supports |
|---|---|
| anomalies (service_id, detected_at DESC) | Anomaly list filtered by service |
| anomalies (severity, detected_at DESC) | Severity filters |
| alerts (status, created_at DESC) | Open-alerts view |
| detection_windows (service_id, window_start DESC) | Trend charts |
| detection_windows (window_start) | Time-range statistics |

---

## 6. Schema Management

The schema is created by `infrastructure/docker/postgres/init.sql` when the Postgres container starts for the first time. If the schema changes often during development, Alembic migrations can be added later.