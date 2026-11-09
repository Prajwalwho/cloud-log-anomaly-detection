# Cloud Log Anomaly Detection for Proactive Fault Management

A real-time system that collects logs from cloud services, detects abnormal patterns using machine learning, and alerts administrators before problems turn into failures.

> **Status:** In development. Infrastructure, log generation and ingestion are complete (Phases 0–4). Next: ML research (Phase 5). See [Roadmap](#roadmap).

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
3. The **detection service** groups logs into 60-second windows per service and scores each window with an ML model. *(Phase 6)*
4. Anomalies get a severity level and are stored in PostgreSQL; serious ones trigger alerts. *(Phases 6, 8)*
5. The **dashboard** shows live anomalies, alerts, log search and trends. *(Phases 7, 9)*

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

Use two terminals, both with the virtual environment activated.

**Terminal 1 — ingestion service (Kafka → Elasticsearch):**
```powershell
python -m backend.ingestion.consumer
```

**Terminal 2 — send logs:**
```powershell
# 60 seconds of normal traffic
python -m backend.log_generator.generator --kafka --duration 60

# Normal traffic with a fault: 1 min normal, 2 min payment errors, 1 min normal
python -m backend.log_generator.generator --kafka --scenario error_burst --warmup 60 --gap 60

# All five fault scenarios (about 41 minutes)
python -m backend.log_generator.generator --kafka --scenario all
```

**Search the stored logs:**
```powershell
python scripts/search_logs.py --minutes 10
python scripts/search_logs.py --minutes 10 --level ERROR
python scripts/search_logs.py --minutes 10 --q "timeout"
python scripts/search_logs.py --trace <trace_id>
```

**Other tools:**

| Command | Purpose |
|---|---|
| `python -m backend.log_generator.generator --list-scenarios` | List fault scenarios |
| `python -m backend.log_generator.generator --scenario all --fast --seed 42 --output data/processed/all_faults.jsonl` | Generate a labelled dataset to a file in seconds |
| `python scripts/summarize_logs.py <file> --ground-truth <gt file>` | Per-minute summary with fault windows marked |
| `python scripts/kafka_peek.py --show 5` | Inspect logs.raw and check the keying contract |
| `python scripts/send_invalid_logs.py` | Send broken messages to test validation |
| `python scripts/pipeline_latency.py --minutes 3` | Measure pipeline latency after a live run |

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
```

Integration test files end in `_integration.py` or live in `tests/integration/`.

## Service ports

| Service | Address | Notes |
|---|---|---|
| Kafka | `localhost:9092` | Containers use `kafka:29092` |
| PostgreSQL | `localhost:15432` | Database `cla_db`, user `cla_user` (see `.env`) |
| Elasticsearch | `http://localhost:9200` | Security disabled for local development |

## Project structure

```
backend/
  log_generator/  Simulated microservices, fault scenarios, Kafka producer
  ingestion/      Kafka consumer, validation, dead-letter, Elasticsearch sink
  detection/      Preprocessing, features, ML models, scoring (Phase 5–6)
  api/            FastAPI application (Phase 7)
frontend/         React + TypeScript dashboard (Phase 9)
infrastructure/   Docker Compose, database schema, monitoring config
data/             Datasets and ground truth (generated, not committed)
experiments/      Notebooks and model comparison results
models/           Trained models and metadata (not committed)
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
| [API contracts](docs/design/api-contracts.md) | REST endpoints and WebSocket protocol |
| [Development log](docs/devlog/) | Daily progress, decisions and problems solved |

## Roadmap

| Phase | Work | Status |
|---|---|---|
| 0 | Environment cleanup and core decisions | ✅ Done |
| 1 | Design contracts (logs, Kafka, database, API) | ✅ Done |
| 2 | Infrastructure (Kafka, PostgreSQL, Elasticsearch) | ✅ Done |
| 3 | Log generator with fault injection and ground truth | ✅ Done |
| 4 | Ingestion pipeline (validation, dead-letter, Elasticsearch) | ✅ Done |
| 5 | ML research on benchmark datasets (HDFS, BGL) | ⏳ Next |
| 6 | Real-time detection service | Pending |
| 7 | Backend API | Pending |
| 8 | Alerting | Pending |
| 9 | React dashboard | Pending |
| 10 | Integration, live evaluation, performance testing | Pending |
| 11 | Documentation and final report | Pending |

## Troubleshooting

| Problem | Fix |
|---|---|
| Scripts say Docker is not running | Start Docker Desktop, wait until it is ready, then `.\scripts\start.ps1 up` |
| PostgreSQL "password authentication failed" | Another PostgreSQL may be using the port. Change `POSTGRES_PORT` in `.env`, then `.\scripts\start.ps1 reset` |
| "port is already allocated" / "forbidden by its access permissions" | Port is used or reserved by Windows. List reserved ranges: `netsh interface ipv4 show excludedportrange protocol=tcp` and pick a free port |
| Smoke test says Kafka topics are missing | Topics are created a few seconds after startup; `start.ps1 up` waits automatically |
| Elasticsearch unhealthy | Check memory in Docker Desktop (needs ~2 GB) and run `.\scripts\start.ps1 logs elasticsearch` |
| pytest "import file mismatch" | Two test files share a name; integration tests must end in `_integration.py` |

## License

See [LICENSE](LICENSE).