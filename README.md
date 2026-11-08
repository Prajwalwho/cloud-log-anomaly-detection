# Cloud Log Anomaly Detection for Proactive Fault Management

A real-time system that collects logs from cloud services, detects abnormal patterns using machine learning, and alerts administrators before problems turn into failures.

> **Status:** In development — infrastructure ready (Phase 2 of 11). See [Roadmap](#roadmap).

---

## How it works

```
Log generator / services
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

1. Services (simulated microservices) produce structured JSON logs to Kafka.
2. The **ingestion service** validates logs and stores them in Elasticsearch.
3. The **detection service** groups logs into 60-second windows per service, extracts features (log templates via Drain, error rate, latency), and scores each window with an ML model.
4. Anomalies get a severity level and are stored in PostgreSQL; critical ones trigger alerts.
5. The **dashboard** shows live anomalies, alerts, log search and historical trends.

## Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.12, TypeScript |
| Streaming | Apache Kafka 3.9 (KRaft) |
| Log storage and search | Elasticsearch 8.17 |
| Structured database | PostgreSQL 16 |
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
```

If PowerShell blocks the scripts, run once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Managing the stack

| Command | What it does |
|---|---|
| `.\scripts\start.ps1 up` | Start all services, wait until healthy, run smoke test |
| `.\scripts\start.ps1 down` | Stop services (data kept) |
| `.\scripts\start.ps1 status` | Show container status |
| `.\scripts\start.ps1 logs` | Follow logs of all services |
| `.\scripts\start.ps1 logs kafka` | Follow logs of one service (`kafka`, `postgres`, `elasticsearch`) |
| `.\scripts\start.ps1 test` | Run the smoke test only |
| `.\scripts\start.ps1 reset` | Delete all data volumes (asks for confirmation) |

## Service ports

| Service | Address | Notes |
|---|---|---|
| Kafka | `localhost:9092` | Containers use `kafka:29092` |
| PostgreSQL | `localhost:15432` | Database `cla_db`, user `cla_user` (see `.env`) |
| Elasticsearch | `http://localhost:9200` | Security disabled for local development |

## Project structure

```
backend/
  api/            FastAPI application (REST + WebSocket)
  ingestion/      Kafka consumer → validation → Elasticsearch
  detection/      Preprocessing, features, ML models, scoring
  log_generator/  Simulated microservice logs and fault scenarios
frontend/         React + TypeScript dashboard
infrastructure/   Docker Compose, database schema, monitoring config
data/             Datasets (raw, processed, sample) — not committed
experiments/      Notebooks and model comparison results
models/           Trained models and metadata — not committed
docs/             Architecture, design contracts, research, devlog
scripts/          Setup, start and smoke-test scripts
tests/            Unit, integration and performance tests
```

## Documentation

| Document | Contents |
|---|---|
| [System architecture](docs/architecture/system-architecture.md) | Components, data flow, design decisions |
| [Data contracts](docs/design/contracts.md) | Log schema, Kafka topics, message formats |
| [Database design](docs/design/database-design.md) | Tables, relationships, indexes |
| [API contracts](docs/design/api-contracts.md) | REST endpoints and WebSocket protocol |
| [Development log](docs/devlog/) | Daily progress, decisions and problems solved |

## Roadmap

| Phase | Work | Status |
|---|---|---|
| 0 | Environment cleanup and core decisions | ✅ Done |
| 1 | Design contracts (logs, Kafka, database, API) | ✅ Done |
| 2 | Infrastructure (Kafka, PostgreSQL, Elasticsearch) | ✅ Done |
| 3 | Log generator with fault injection | ⏳ Next |
| 4 | Ingestion pipeline | Pending |
| 5 | ML research on benchmark datasets (HDFS, BGL) | Pending |
| 6 | Real-time detection service | Pending |
| 7 | Backend API | Pending |
| 8 | Alerting | Pending |
| 9 | React dashboard | Pending |
| 10 | Integration, evaluation, performance testing | Pending |
| 11 | Documentation and final report | Pending |

## Troubleshooting

| Problem | Fix |
|---|---|
| PostgreSQL "password authentication failed" | Another PostgreSQL may be using the port. Change `POSTGRES_PORT` in `.env`, then `.\scripts\start.ps1 reset` |
| "port is already allocated" / "forbidden by its access permissions" | Port is used or reserved by Windows. List reserved ranges: `netsh interface ipv4 show excludedportrange protocol=tcp` and pick a free port |
| Smoke test says Kafka topics are missing | Topics are created a few seconds after startup; use `start.ps1 up`, which waits automatically |
| Elasticsearch unhealthy | Check memory in Docker Desktop (needs ~2 GB) and run `.\scripts\start.ps1 logs elasticsearch` |

## License

See [LICENSE](LICENSE).