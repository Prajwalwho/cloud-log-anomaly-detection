# Cloud Log Anomaly Detection for Proactive Fault Management

A real-time system that collects logs from cloud services, detects abnormal patterns using machine learning, and alerts administrators before problems turn into failures. Its dashboard is called **Observatory**.

> **Status:** The system is built, evaluated (Phases 0–10) and documented (Phase 11). The user guide is in [`docs/guide/`](docs/guide/README.md) and inside the dashboard under **Docs**. The final report comes next. See [Roadmap](#roadmap).

---

## What it does

- **Collects** every log line through Apache Kafka and stores it, searchable, in Elasticsearch.
- **Learns normal behaviour** with a PCA model trained on normal traffic only; no examples of failures are needed.
- **Judges every service every minute.** An unusual minute becomes an **anomaly** with a severity (LOW to CRITICAL) and reasons in plain language, such as `error rate 29.1%` or `no logs (normally ~805 per minute)`.
- **Groups anomalies into alerts**, escalates them, and resolves them automatically after five quiet minutes.
- **Notifies** the operator on Telegram for HIGH and CRITICAL alerts: when an alert starts, if it becomes critical, and when it is resolved.
- **Shows everything live** on a React dashboard, with log search that follows one request through all services.

```text
Log generator (5 simulated services, faults injected at known times)
        │
        ▼
   Apache Kafka  (logs.raw)
     │        │
     ▼        ▼
 Ingestion   Detection ──────► PostgreSQL (windows, anomalies, alerts, models)
     │        │
     ▼        ▼
Elasticsearch  Kafka (anomalies.detected) ──► Alerting ──► Telegram
     │                     │                     │
     └──────────►  FastAPI (REST + WebSocket)  ◄─┘
                          │
                          ▼
                   React dashboard
```

How it works, part by part: [Introduction](docs/guide/introduction.md) · [How detection works](docs/guide/how-detection-works.md) · [Architecture](docs/guide/architecture.md).

## Results

Measured on one laptop with every part running live (Phase 10, model `live-pca 1.1.0`):

| Question | Result |
|---|---|
| Are injected faults found? | 15 of 15 incidents in three runs of five fault scenarios |
| False alarms during quiet periods? | 0 in 30 quiet minutes; 1 LOW anomaly in a fault-free hour (285 service-minutes), no alert |
| How fast is a fault detected? | About 6 s after the minute in which it became visible ends: 8–69 s after the fault starts |
| How fast is the operator told? | Anomaly on the dashboard 0.06 s after it is stored; alert about 1 s later; Telegram about 1 s after the alert |
| How fast is a log line searchable? | Stored after 0.6 s (median), searchable within about 6 s |
| How much traffic? | 735 log lines per second (10 times the normal load) without falling behind |

Reports: [live evaluation](docs/testing/live-evaluation-results.md) · [speed](docs/testing/latency-results.md) · [load test](docs/testing/load-test-results.md) · [improvements](docs/testing/improvements-results.md).

## Documentation

The user guide, also shown in the dashboard at <http://localhost:5173/docs>:

| Section | Pages |
|---|---|
| Start here | [Introduction](docs/guide/introduction.md) · [Getting started](docs/guide/getting-started.md) |
| Learn | [Concepts](docs/guide/concepts.md) · [How detection works](docs/guide/how-detection-works.md) · [Architecture](docs/guide/architecture.md) |
| Use | [Using the dashboard](docs/guide/using-the-dashboard.md) · [Alerts and Telegram](docs/guide/alerts-and-telegram.md) · [Operations](docs/guide/operations.md) |
| Reference | [API reference](docs/guide/api-reference.md) · [Configuration](docs/guide/configuration.md) · [Glossary](docs/guide/glossary.md) · [FAQ](docs/guide/faq.md) |
| Study | [Study guide](docs/guide/study-guide.md): how to learn, demonstrate and present the project |

Design and research documents:

| Document | Contents |
|---|---|
| [Data contracts](docs/design/contracts.md) | Log schema, Kafka topics, message formats, alert lifecycle |
| [Database design](docs/design/database-design.md) | PostgreSQL tables, relationships, indexes |
| [Elasticsearch design](docs/design/elasticsearch-design.md) | Index naming, template, mappings, idempotency |
| [Detection design](docs/design/detection-design.md) | Windows, watermark, features, model, severity, publishing, each decision with its evidence |
| [API contracts](docs/design/api-contracts.md) | REST endpoints and WebSocket protocol |
| [System architecture](docs/architecture/system-architecture.md) | The architecture document from the design phase |
| [Research plan and results](docs/research/research-plan.md) | Research questions, method, RQ1/RQ2 results, threats to validity |
| [Testing](docs/testing/) | Test strategy, live evaluation plan and results, speed and load tests |
| [Development log](docs/devlog/) | Daily progress, decisions and problems solved |

## Quick start

You need Windows 10/11 with PowerShell, [Python 3.12](https://www.python.org/downloads/), [Node.js](https://nodejs.org/), [Docker Desktop](https://www.docker.com/products/docker-desktop/) (4 GB of memory available) and Git. A Telegram account is optional.

```powershell
git clone https://github.com/Prajwalwho/cloud-log-anomaly-detection.git
cd cloud-log-anomaly-detection
.\scripts\setup.ps1
.\scripts\start.ps1 up
backend\.venv\Scripts\Activate.ps1
```

Then train the model once and start the services, each in its own terminal:

| # | Part | Command |
|---|---|---|
| 1 | API | `uvicorn backend.api.app.main:app --port 8000` |
| 2 | Ingestion | `python -m backend.ingestion.consumer` |
| 3 | Detection | `python -m backend.detection.service` |
| 4 | Alerting | `python -m backend.alerting.service` |
| 5 | Dashboard | `npm run dev` in `frontend/` → <http://localhost:5173> |
| 6 | Traffic with a fault | `python -m backend.log_generator.generator --kafka --scenario error_burst --warmup 120 --gap 300` |

Every step, including training the model and what to expect on the screen, is in [Getting started](docs/guide/getting-started.md). Day-to-day running, disk space and troubleshooting are in [Operations](docs/guide/operations.md).

## Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.12, TypeScript |
| Streaming | Apache Kafka 3.9 (KRaft) |
| Log storage and search | Elasticsearch 8.17 |
| Structured database | PostgreSQL 16 |
| Validation | Pydantic 2 |
| Machine learning | Scikit-learn, Drain3 |
| Backend API | FastAPI, WebSockets |
| Notifications | Telegram Bot API |
| Frontend | React 19, Vite, React Router, Recharts |
| Containers | Docker, Docker Compose |

## Research results (offline, Phase 5)

Models were compared on two public benchmark datasets from [LogHub](https://github.com/logpai/loghub) (Zenodo record 8196385: `HDFS_v1.zip`, `BGL.zip`, placed in `data/raw/`), with chronological 60/20/20 splits and models trained on normal data only.

| Test set | Lookup baseline | PCA | One-Class SVM | Best simple rule |
|---|---|---|---|---|
| HDFS F1 (label-free threshold) | 0.978 | 0.965 | 0.971 | — |
| BGL F1 (label-free threshold) | 0.210 | 0.333 (0.486 with log counts + levels) | 0.300 (0.468) | FATAL count 0.840 (validation-tuned) |

- **RQ1:** on stable, repetitive logs (HDFS) PCA and One-Class SVM nearly match a lookup table; on drifting logs (BGL: 74% of normal test windows contain message types unseen in training, caused by a monitoring change on 15 Nov 2005) every novelty-based method degrades.
- **RQ2:** the best feature representation depends on the data: log-scaled counts help on bursty BGL and hurt on HDFS; retraining on one more month did not counter BGL's step-change drift.
- **RQ3 (live system):** global PCA with log-scaled counts was chosen from six configurations on live data. Its results are in [Results](#results).

Details: [research plan and results](docs/research/research-plan.md), [detection design](docs/design/detection-design.md), result files in `experiments/results/`.

## Project structure

```text
backend/
  log_generator/  Simulated microservices, fault scenarios, Kafka producer
  ingestion/      Kafka consumer, validation, dead-letter, Elasticsearch sink
  detection/      Drain parsing, windowing, features, models, severity, training,
                  model packages and registry, live detection service
  alerting/       Grouping anomalies into alerts, auto-resolve, Telegram notifications
  api/            FastAPI application: REST endpoints and the /ws/live feed
  common/         Shared helpers (Kafka topics, safe commits)
frontend/         React + TypeScript dashboard: pages, components, hooks, API client, live feed, docs
infrastructure/   Docker Compose, the database schema (and a Prometheus configuration, not in use)
data/             Datasets and ground truth (generated, not committed)
experiments/      Notebooks, experiment scripts and results
models/           Trained model packages (not committed) and metadata (committed)
docs/
  guide/          The user guide (also shown in the dashboard)
  design/         Contracts, database, Elasticsearch, detection, API
  testing/        Test strategy and results
  research/       Research plan and results
  devlog/         One file per working day
scripts/          Setup, start, smoke test, Telegram set-up and measurement tools
tests/            Unit, integration and performance tests
```

## Tests

```powershell
pytest                    # all tests (integration tests are skipped if the stack is down)
pytest tests/unit         # unit tests only, no Docker needed
```

```powershell
cd frontend
npm run lint
npm run build
```

Integration test files end in `_integration.py` or live in `tests/integration/`. They create their own data (dated 2001) and remove it afterwards.

## Roadmap

| Phase | Work | Status |
|---|---|---|
| 0 | Environment cleanup and core decisions | ✅ Done |
| 1 | Design contracts (logs, Kafka, database, API) | ✅ Done |
| 2 | Infrastructure (Kafka, PostgreSQL, Elasticsearch) | ✅ Done |
| 3 | Log generator with fault injection and ground truth | ✅ Done |
| 4 | Ingestion pipeline (validation, dead-letter, Elasticsearch) | ✅ Done |
| 5 | ML research on benchmark datasets (HDFS, BGL) | ✅ Done |
| 6 | Real-time detection service | ✅ Done |
| 7 | Backend API (REST + live WebSocket feed) | ✅ Done |
| 8 | Alerting (grouping, auto-resolve, Telegram) | ✅ Done |
| 9 | React dashboard | ✅ Done |
| 10 | Integration, live evaluation, performance testing | ✅ Done |
| 11 | Documentation (user guide in the app) | ✅ Done |
| 12 | Final report | Pending |

## License

See [LICENSE](LICENSE).