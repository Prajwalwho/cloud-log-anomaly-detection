# Cloud Log Anomaly Detection for Proactive Fault Management

A real-time system that collects logs from cloud services, detects abnormal patterns using machine learning, and alerts administrators before problems turn into failures.

> **Status:** In development. Infrastructure, log generation, ingestion, ML research, the real-time detection service and the backend API are complete (Phases 0–7). Next: Alerting (Phase 8). See [Roadmap](#roadmap).

---

## How it works

```
Log generator (5 simulated microservices, fault injection)
        │
        ▼
   Apache Kafka  (logs.raw)
     │        │
     ▼        ▼
 Ingestion   Detection ──────► PostgreSQL (windows, anomalies, alerts, models)
     │        │
     ▼        ▼
Elasticsearch  Kafka (anomalies.detected) ──► Alerting (Telegram / email)
     │                     │
     └──────► FastAPI ◄────┘
                 │  REST + WebSocket
                 ▼
          React dashboard
```

1. The **log generator** simulates user requests through five microservices and can inject faults at known times, recording the ground truth.
2. The **ingestion service** validates every log against the contract and stores it in Elasticsearch; invalid messages go to a dead-letter topic.
3. The **detection service** reads the same Kafka topic independently, parses messages into templates (Drain), groups logs into 60-second windows per service and scores each window with a PCA model.
4. Every anomaly gets a **severity** (LOW–CRITICAL) with human-readable **reasons**, is stored in PostgreSQL and published to `anomalies.detected`; serious ones will trigger alerts. *(alerting: Phase 8)*
5. The **API** serves logs, anomalies, alerts, statistics and models over REST, and pushes new anomalies to browsers over a WebSocket within about a second.
6. The **dashboard** shows live anomalies, alerts, log search and trends. *(Phase 9)*

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
| Frontend | React, Vite, Recharts |
| Containers | Docker, Docker Compose |
| Monitoring | Prometheus, Grafana (planned) |

## Prerequisites

- Windows 10/11 with PowerShell
- [Python 3.12](https://www.python.org/downloads/) (`winget install -e --id Python.Python.3.12`)
- [Node.js](https://nodejs.org/) and npm
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with at least 4 GB of memory available
- Git

## Quick start

```powershell
git clone <repository-url>
cd cloud-log-anomaly-detection

# One-time setup: venv, dependencies, .env, Docker images
.\scripts\setup.ps1

# Start the infrastructure (waits for health checks and runs a smoke test)
.\scripts\start.ps1 up

# Activate the Python environment in every new terminal
backend\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the scripts, run once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Running the pipeline

Use one terminal per component, all with the virtual environment activated. The detection service needs a trained, active model (see [Training the detection model](#training-the-detection-model)).

**Ingestion (Kafka → Elasticsearch):**
```powershell
python -m backend.ingestion.consumer
```

**Detection (Kafka → PostgreSQL + anomalies.detected):**
```powershell
python -m backend.detection.service
```
Each closed minute is printed with log counts per service; anomalies are shown with severity and reasons, e.g.
`! payment-service CRITICAL (score 0.84): error rate 42.2%`.

**API (REST + WebSocket):**
```powershell
uvicorn backend.api.app.main:app --reload --reload-dir backend/api --port 8000
```
Interactive documentation: <http://localhost:8000/docs>. Watch the live feed in a terminal:
```powershell
python scripts/watch_live.py
```

**Send logs:**
```powershell
# 60 seconds of normal traffic
python -m backend.log_generator.generator --kafka --duration 60

# Normal traffic with a fault: 1 min normal, 2 min payment errors, 1 min normal
python -m backend.log_generator.generator --kafka --scenario error_burst --warmup 60 --gap 60

# All five fault scenarios (about 41 minutes)
python -m backend.log_generator.generator --kafka --scenario all
```

**Check detection against the ground truth** (the generator prints the ground-truth file name):
```powershell
python scripts/check_detection.py data/ground_truth/<run-id>.jsonl
```

**Other tools:**

| Command | Purpose |
|---|---|
| `python -m backend.log_generator.generator --list-scenarios` | List fault scenarios |
| `python -m backend.log_generator.generator --scenario all --fast --seed 42 --output data/processed/all_faults.jsonl` | Generate a labelled dataset to a file in seconds |
| `python scripts/search_logs.py --minutes 10 --level ERROR` | Search stored logs from the terminal |
| `python scripts/summarize_logs.py <file> --ground-truth <gt file>` | Per-minute summary with fault windows marked |
| `python scripts/kafka_peek.py --show 5` | Inspect logs.raw and check the keying contract |
| `python scripts/send_invalid_logs.py` | Send broken messages to test validation |
| `python scripts/send_future_log.py` | Send one event dated 2030 (robustness test: both services must reject it) |
| `python scripts/pipeline_latency.py --minutes 3` | Measure pipeline latency after a live run |
| `python scripts/check_detection.py <gt file>` | Compare stored anomalies with ground truth |
| `python scripts/watch_live.py` | Print the API's live feed |
| `python experiments/replay_windows.py <file> --ground-truth <gt file>` | Replay a log file through windowing and features (no Kafka) |
| `python -m backend.detection.service --idle-exit 30 --group <name> --allow-future` | Replay what is in Kafka with a fresh consumer group (fast-mode runs need `--allow-future`) |

## Backend API

Base URL `http://localhost:8000/api/v1` — full contract in [api-contracts.md](docs/design/api-contracts.md). Times are UTC; list endpoints default to the last hour (`from`, `to`) and are paginated (`page`, `size` ≤ 200).

| Endpoint | Purpose |
|---|---|
| `GET /health` | PostgreSQL, Elasticsearch, Kafka status (503 `degraded` if one is down) |
| `GET /services` | Monitored services |
| `GET /logs`, `GET /logs/{event_id}` | Log search: full text `q`, `service`, `level`, `trace_id` |
| `GET /anomalies`, `GET /anomalies/{id}` | Anomalies with filters; detail includes the sample log lines |
| `PATCH /anomalies/{id}/feedback` | Mark `CONFIRMED` / `FALSE_POSITIVE` (or clear) |
| `GET /alerts`, `GET /alerts/{id}`, `PATCH /alerts/{id}` | Alerts; acknowledge or resolve |
| `GET /stats/summary`, `GET /stats/timeseries` | Dashboard numbers and chart data |
| `GET /models`, `GET /models/active` | Model registry |
| `WS /ws/live` | Pushes `anomaly.created`, `alert.updated` and `ping` |

Examples:
```
http://localhost:8000/api/v1/anomalies?severity=HIGH,CRITICAL
http://localhost:8000/api/v1/logs?level=ERROR&q=timeout&size=5
http://localhost:8000/api/v1/stats/timeseries?metric=error_rate&interval=1m&service=payment-service
```

## Training the detection model

The live model is trained on normal traffic only, saved as an immutable **model package** (model, Drain parser state, metadata) and registered as the **active model** in PostgreSQL. The detection service loads the active model at start-up.

```powershell
# 1. Normal training traffic: three runs of 2 hours with different seeds (seconds each)
python -m backend.log_generator.generator --duration 7200 --fast --seed 1 --output data/processed/train_normal_1.jsonl
python -m backend.log_generator.generator --duration 7200 --fast --seed 2 --output data/processed/train_normal_2.jsonl
python -m backend.log_generator.generator --duration 7200 --fast --seed 3 --output data/processed/train_normal_3.jsonl

# 2. Evaluation data: a fault run with ground truth, and a fresh fault-free run
python -m backend.log_generator.generator --scenario all --fast --seed 42 --output data/processed/all_faults.jsonl
python -m backend.log_generator.generator --duration 3600 --fast --seed 4 --output data/processed/normal_eval_4.jsonl

# 3. Train, check, evaluate and register (one line; use the ground-truth file printed in step 2)
python -m backend.detection.train --train data/processed/train_normal_1.jsonl data/processed/train_normal_2.jsonl data/processed/train_normal_3.jsonl --version 1.1.0 --eval data/processed/all_faults.jsonl --ground-truth data/ground_truth/<run-id>.jsonl --normal-eval data/processed/normal_eval_4.jsonl --register
```

`train.py` checks that the reloaded package reproduces the in-memory scores exactly, reports detection per fault with severities and reasons, and the false-alarm rate on the fault-free run. Packages go to `models/trained/<name>-<version>/` (not committed); a copy of each model's metadata is committed in `models/metadata/`. A version can never be overwritten — use a new `--version`.

## Research results (offline, Phase 5)

Models were compared on two public benchmark datasets from [LogHub](https://github.com/logpai/loghub) (Zenodo record 8196385: `HDFS_v1.zip`, `BGL.zip`, placed in `data/raw/`), with chronological 60/20/20 splits and models trained on normal data only.

| Test set | Lookup baseline | PCA | One-Class SVM | Best simple rule |
|---|---|---|---|---|
| HDFS F1 (label-free threshold) | 0.978 | 0.965 | 0.971 | — |
| BGL F1 (label-free threshold) | 0.210 | 0.333 (0.486 with log counts + levels) | 0.300 (0.468) | FATAL count 0.840 (validation-tuned) |

- **RQ1:** on stable, repetitive logs (HDFS) PCA and One-Class SVM nearly match a lookup table; on drifting logs (BGL: 74% of normal test windows contain message types unseen in training, caused by a monitoring change on 15 Nov 2005) every novelty-based method degrades.
- **RQ2:** the best feature representation depends on the data — log-scaled counts help on bursty BGL and hurt on HDFS; retraining on one more month did not counter BGL's step-change drift.
- **Live system (Phase 6):** global PCA with log counts was chosen from six configurations. Model `live-pca 1.1.0`: all injected incidents detected, about 33 s after a fault starts in a real-time run; 0.34% false-alarm windows on a fault-free hour, graded LOW.

Details: [research plan and results](docs/research/research-plan.md), [detection design](docs/design/detection-design.md), result files in `experiments/results/`.

## Managing the stack

| Command | What it does |
|---|---|
| `.\scripts\start.ps1 up` | Start all services, wait until healthy, run smoke test |
| `.\scripts\start.ps1 down` | Stop services (PostgreSQL and Elasticsearch data kept; Kafka data cleared) |
| `.\scripts\start.ps1 status` | Show container status |
| `.\scripts\start.ps1 logs` | Follow logs of all services (Ctrl+C to stop) |
| `.\scripts\start.ps1 logs kafka` | Follow logs of one service (`kafka`, `postgres`, `elasticsearch`) |
| `.\scripts\start.ps1 test` | Run the smoke test only |
| `.\scripts\start.ps1 reset` | Delete all data volumes (asks for confirmation) |

## Tests

```powershell
pytest                    # all tests (integration tests are skipped if the stack is down)
pytest tests/unit         # unit tests only, no Docker needed
pytest -k api             # API tests only
```

Integration test files end in `_integration.py` or live in `tests/integration/`. Integration tests create their own data (dated 2001) and remove it afterwards.

## Service ports

| Service | Address | Notes |
|---|---|---|
| Kafka | `localhost:9092` | Containers use `kafka:29092` |
| PostgreSQL | `localhost:15432` | Database `cla_db`, user `cla_user` (see `.env`) |
| Elasticsearch | `http://localhost:9200` | Security disabled for local development |
| API | `http://localhost:8000` | Started with uvicorn (see above) |

## Project structure

```
backend/
  log_generator/  Simulated microservices, fault scenarios, Kafka producer
  ingestion/      Kafka consumer, validation, dead-letter, Elasticsearch sink
  detection/      Drain parsing, windowing, features, models, severity, training,
                  model packages and registry, live detection service
  api/            FastAPI application: REST endpoints and the /ws/live feed
frontend/         React + TypeScript dashboard (Phase 9)
infrastructure/   Docker Compose, database schema, monitoring config
data/             Datasets and ground truth (generated, not committed)
experiments/      Notebooks, experiment scripts and model comparison results
models/           Trained model packages (not committed) and metadata (committed)
docs/             Architecture, design documents, research, devlog
scripts/          Setup, start, smoke test and pipeline tools
tests/            Unit and integration tests
```

## Documentation

| Document | Contents |
|---|---|
| [System architecture](docs/architecture/system-architecture.md) | Components, data flow, design decisions, evaluation |
| [Data contracts](docs/design/contracts.md) | Log schema, Kafka topics, message formats |
| [Database design](docs/design/database-design.md) | PostgreSQL tables, relationships, indexes |
| [Elasticsearch design](docs/design/elasticsearch-design.md) | Index naming, template, mappings, idempotency |
| [Detection design](docs/design/detection-design.md) | Windows, watermark, features, model, severity, publishing — each decision with its evidence |
| [API contracts](docs/design/api-contracts.md) | REST endpoints and WebSocket protocol |
| [Research plan and results](docs/research/research-plan.md) | Research questions, method, RQ1/RQ2 results, threats to validity |
| [Development log](docs/devlog/) | Daily progress, decisions and problems solved |

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
| 8 | Alerting | ⏳ Next |
| 9 | React dashboard | Pending |
| 10 | Integration, live evaluation, performance testing | Pending |
| 11 | Documentation and final report | Pending |

## Troubleshooting

| Problem | Fix |
|---|---|
| Scripts say Docker is not running | Start Docker Desktop, wait until it is ready, then `.\scripts\start.ps1 up` |
| A service reports Kafka, PostgreSQL or Elasticsearch unreachable | The stack is probably stopped (e.g. after the laptop slept): `.\scripts\start.ps1 status`, then `.\scripts\start.ps1 up` |
| PostgreSQL "password authentication failed" | Another PostgreSQL may be using the port. Change `POSTGRES_PORT` in `.env`, then `.\scripts\start.ps1 reset` |
| "port is already allocated" / "forbidden by its access permissions" | Port is used or reserved by Windows. List reserved ranges: `netsh interface ipv4 show excludedportrange protocol=tcp` and pick a free port |
| Smoke test says Kafka topics are missing | Topics are created a few seconds after startup; `start.ps1 up` waits automatically |
| Elasticsearch unhealthy | Check memory in Docker Desktop (needs ~2 GB) and run `.\scripts\start.ps1 logs elasticsearch` |
| pytest "import file mismatch" | Two test files share a name; integration tests must end in `_integration.py` |
| Detection: "No active model in model_registry" | Train and register a model (see [Training the detection model](#training-the-detection-model)) |
| A service should only process new logs | Stop it, then move its consumer group to the end of the topic: `docker exec cla-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group detection-group --reset-offsets --to-latest --topic logs.raw --execute` (same for `ingestion-group`) |
| Detection skips events "more than 5 min in the future" | Expected for invalid timestamps. For replays of `--fast` runs (timestamps in the future by design) start the service with `--allow-future` |
| `check_detection.py` shows `0/0` windows for a fault | The run was not finished or the detection service was not running during it |
| API shows nothing for old data | List endpoints default to the last hour; add `from` (and `to`), e.g. `?from=2026-11-13T00:00:00Z` |
| `watch_live.py` cannot connect | Start the API first (uvicorn command above) |
| API restarts when editing other code | Start uvicorn with `--reload-dir backend/api` |

## License

See [LICENSE](LICENSE).