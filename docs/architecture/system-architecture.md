# System Architecture
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 2.0 (updated after Phase 4)
Status legend: **Implemented** = built and tested; **Planned** = designed, not yet built.

---

### 1. System Overview

A real-time platform that collects logs from cloud services, detects abnormal behaviour with
machine learning, and alerts administrators before problems turn into failures.

Logs flow through a streaming pipeline (Kafka), are validated and stored for search
(Elasticsearch), and are analysed in fixed time windows by a detection service. Anomalies are
scored, given a severity, stored in PostgreSQL and shown on a live dashboard.

### 2. Architectural Objectives

- Centralised collection of logs from multiple services.
- Real-time processing and anomaly detection.
- Detection without requiring large labelled datasets (unsupervised and statistical methods).
- Severity-based classification and alerting.
- Historical log search and anomaly analysis.
- Measurable accuracy, latency and throughput.
- No log loss when components fail or restart.

### 3. Technology Stack

| Layer | Technology |
|---|---|
| Programming language | Python 3.12, TypeScript |
| Streaming | Apache Kafka 3.9 (KRaft mode, single broker) |
| Log storage and search | Elasticsearch 8.17 (single node) |
| Structured database | PostgreSQL 16 |
| Log template mining | Drain (drain3) |
| Machine learning | Scikit-learn |
| Validation | Pydantic 2 |
| Backend API | FastAPI, WebSockets |
| Frontend | React, TypeScript, Vite, Recharts |
| Containers | Docker, Docker Compose |
| Monitoring | Prometheus, Grafana |

### 4. System Components

#### 4.1 Log Generator — Implemented
`backend/log_generator/`

Simulates five microservices (api-gateway, auth, order, payment, inventory). Traffic is modelled as
user requests that pass through the gateway to downstream services, so related logs share a
`trace_id`, latencies add up along the call chain, and downstream failures appear as 502/503 errors
at the gateway.

- Poisson request arrivals with a ±30% sinusoidal load variation.
- Log-normal latencies; slow calls logged as WARN; 0.2% baseline failure rate.
- Periodic background logs (health checks, connection pool stats, batch jobs).
- Five fault scenarios: error_burst, latency_spike, new_error, silent_service, cascading_failure.
- Ground-truth file per run, never part of the log stream.
- Reproducible with a fixed seed; real-time or fast mode; output to console, file or Kafka.

#### 4.2 Streaming Layer (Kafka) — Implemented
Decouples producers from consumers and buffers logs while consumers are down.

| Topic | Partitions | Retention | Key | Purpose |
|---|---|---|---|---|
| logs.raw | 3 | 24 h | service | All incoming log events |
| logs.deadletter | 1 | 7 days | — | Messages failing validation or storage |
| anomalies.detected | 1 | 7 days | service | Detected anomalies (Planned producer) |

The producer uses acks=all and idempotence (no loss or duplication from retries), lz4 compression
and murmur2 partitioning.

#### 4.3 Ingestion Service — Implemented
`backend/ingestion/`

Consumes `logs.raw` in batches (up to 500), validates each message against the log contract
(Pydantic, strict types), stores valid events in Elasticsearch, and sends invalid ones, with the
reason and original text, to `logs.deadletter`.

Offsets are committed only after the batch is stored and every dead-letter message is confirmed
(at-least-once delivery).

#### 4.4 Storage — Elasticsearch Implemented, PostgreSQL schema Implemented
- **Elasticsearch:** daily indices `logs-YYYY.MM.DD`, explicit mappings, idempotent writes.
  See `docs/design/elasticsearch-design.md`.
- **PostgreSQL:** services, model_registry, detection_windows, anomalies, alerts.
  See `docs/design/database-design.md`. The tables exist; they are written from Phase 6.

#### 4.5 Detection Service — Planned (Phase 6)
Consumes `logs.raw` in its own consumer group, independently of ingestion. Groups logs into
60-second windows per service, extracts features, scores each window with the active model,
stores every window and every anomaly in PostgreSQL, and publishes anomalies to
`anomalies.detected`.

#### 4.6 Severity Scoring — Planned (Phase 6)
Maps the normalised anomaly score (0–1) and configurable rules to LOW, MEDIUM, HIGH or CRITICAL.
Severity is an operational classification, separate from the ML score.

#### 4.7 Alerting — Planned (Phase 8)
Creates alerts for HIGH and CRITICAL anomalies, groups repeated anomalies of one service into one
open alert (deduplication), and notifies administrators (Telegram or email).

#### 4.8 Backend API — Planned (Phase 7)
FastAPI REST endpoints for logs, anomalies, alerts, statistics and models, plus a WebSocket for
live events. See `docs/design/api-contracts.md`.

#### 4.9 Frontend Dashboard — Planned (Phase 9)
React dashboard: overview, log search, anomalies, alerts, trends, live updates.

#### 4.10 Monitoring — Planned (Phase 10)
Prometheus and Grafana for throughput, latency, resource use and service health.

### 5. End-to-End Data Flow

1. Services (the generator) publish JSON log events to `logs.raw`, keyed by service.
2. The ingestion service validates each event; valid ones are bulk-indexed into Elasticsearch,
   invalid ones go to `logs.deadletter`; offsets are committed after storage. *(Implemented)*
3. The detection service reads the same topic independently, builds 60-second windows per service,
   extracts features and scores each window. *(Planned)*
4. Windows and anomalies are stored in PostgreSQL; anomalies are published to `anomalies.detected`. *(Planned)*
5. Alerting turns serious anomalies into deduplicated alerts and notifications. *(Planned)*
6. FastAPI serves logs (Elasticsearch) and anomalies, alerts and statistics (PostgreSQL), and pushes
   live events over WebSockets to the React dashboard. *(Planned)*

### 6. Key Design Decisions

#### 6.1 Detection as an independent service
Ingestion and detection consume `logs.raw` in different consumer groups. Each receives every log;
slow detection never delays storage, and each service can be restarted or scaled independently.

#### 6.2 Key = service
All logs of one service go to the same partition, so they are processed in order (needed for time
windows). Trade-off: with 5 services and 3 partitions, load is uneven (one partition carried 60% in
testing). Acceptable at this scale; a larger system would use more partitions or a composite key.

#### 6.3 Unit of detection
- Live system: 60-second windows per service. Windows are created for every known service even when
  no logs arrive, so a silent (crashed) service is detectable.
- Benchmark datasets: sessions (HDFS block ids) or sliding windows (BGL).

Window-level detection was chosen over line-level detection because most failures show up as changes
in patterns across many lines, not in a single line.

#### 6.4 Responsibility for parsing
Ingestion only validates the structure of events. Log template extraction (Drain) belongs to the
detection service.

#### 6.5 Delivery guarantees
At-least-once delivery from Kafka (offsets committed after storage) plus idempotent writes
(document id = event_id) gives effectively-once storage: no lost logs and no duplicates. Verified
by re-reading the full topic: no duplicates were created.

#### 6.6 Ground truth separation
Injected faults are recorded in a separate ground-truth file and never appear in log events, so the
detector cannot see the answers it is evaluated on (no label leakage).

#### 6.7 Validation and dead-letter
Invalid messages are never silently dropped. The original text and the reason are kept in
`logs.deadletter` for inspection.

### 7. Machine Learning Methodology — Planned (Phase 5)

1. Benchmark datasets: HDFS and BGL from LogHub.
2. Template extraction with Drain.
3. Feature engineering: event count vectors per session/window; for the live system also error rate,
   WARN rate, latency statistics and new-template counts.
4. Models compared: statistical baseline, PCA, Isolation Forest, One-Class SVM.
5. Training on normal data only, with time-ordered train/test splits.
6. Threshold selection and score normalisation to 0–1.
7. Comparative evaluation; no algorithm is assumed superior in advance.

### 8. Evaluation

**Detection accuracy:** precision, recall, F1, false positive rate, ROC-AUC
- Offline on labelled benchmark datasets (HDFS, BGL).
- Live on the simulated system against the generator's ground truth.

**Live evaluation details:**
- A window counts as faulty if it overlaps a ground-truth fault interval.
- Two levels: service level (was the root-cause service flagged?) and incident level (was any alert
  raised during the incident?). Needed because faults affect other services too: a silent auth-service
  also silences order and payment.
- Partially faulty edge windows (faults rarely align with minute boundaries) reported separately.
- Time to detect.

**System performance:** pipeline latency (ingested_at − timestamp), throughput, CPU and memory use,
behaviour under increasing load.

### 9. Proactive Fault Management

The system aims to support proactive fault management by identifying unusual log behaviour before it
develops into a service failure. However, anomaly detection does not by itself establish fault
prediction. Predictive claims require experiments showing that detected patterns consistently precede
independently verified failures.

### 10. Reliability and Scalability

Implemented:
- Asynchronous, decoupled components connected through Kafka.
- No log loss when the consumer is down: logs wait in Kafka (verified: an 18,190-event backlog was
  ingested after a consumer restart).
- Retries with backoff for transient storage failures.
- Containerised infrastructure with health checks.

Known limitations of the development setup:
- Single Kafka broker and single Elasticsearch node (no replication).
- Security (TLS, authentication) disabled locally.
- Kafka data not persisted across `docker compose down`.

### 11. Future Enhancements

- Distributed log collection (Fluent Bit, OpenTelemetry).
- Deep learning sequence models (e.g. LSTM-based).
- Root-cause analysis and multi-service correlation using trace_id.
- Failure prediction from historical event sequences.
- Index lifecycle management for log retention.

### 12. Conclusion

The architecture combines streaming infrastructure, validated and searchable log storage,
machine-learning detection, structured anomaly management and real-time visualisation. Phases 1–4
(design, infrastructure, log generation and ingestion) are implemented and tested; the detection,
API, alerting and dashboard layers build on these foundations.