# Architecture

How the system is built: its parts, how data moves between them, where it is stored, and why it is built this way. For the meaning of single words (offset, watermark, …) see [Concepts](concepts.md); for the detection itself see [How detection works](how-detection-works.md).

## The parts and the data flow

```text
 Log generator   5 simulated services, faults, ground truth
      │  log events, key = service
      ▼
 Kafka logs.raw (3 partitions)
      │                             │
      │ ingestion-group             │ detection-group
      ▼                             ▼
 Ingestion ──► logs.deadletter   Detection ──────────► PostgreSQL
      │        (broken events)   Drain, windows,       services
      │                          PCA, severity         model_registry
      ▼                             │                  detection_windows
 Elasticsearch                      ▼                  anomalies
 logs-YYYY.MM.DD             Kafka anomalies.detected  alerts
      │                             │                     ▲
      │                             │ alerting-group      │
      │                             ▼                     │
      │                          Alerting ────────────────┤
      │                             │  └──► Telegram      │
      │                             ▼                     │
      │                      Kafka alerts.events          │
      │                             │                     │
      ▼                             ▼                     │
 API (FastAPI): REST + WebSocket ◄────────────────────────┘
      │  /api/v1
      ▼
 Dashboard (React)
```

| Part | Reads | Writes | Code |
|---|---|---|---|
| Log generator | — | `logs.raw`, a ground-truth file | `backend/log_generator/` |
| Ingestion | `logs.raw` (group `ingestion-group`) | Elasticsearch; broken events to `logs.deadletter` | `backend/ingestion/` |
| Detection | `logs.raw` (group `detection-group`), the active model | PostgreSQL (`detection_windows`, `anomalies`); `anomalies.detected` | `backend/detection/` |
| Alerting | `anomalies.detected` (group `alerting-group`) | PostgreSQL (`alerts`, links anomalies to alerts); `alerts.events`; Telegram | `backend/alerting/` |
| API | PostgreSQL, Elasticsearch, `anomalies.detected`, `alerts.events` | PostgreSQL (verdicts, alert status) | `backend/api/` |
| Dashboard | the API | — | `frontend/` |

Every part is a separate process. The three stores (Kafka, PostgreSQL, Elasticsearch) run in Docker (`infrastructure/docker/docker-compose.yml`); the Python services and the dashboard run directly on the computer.

## Where data lives

### Kafka: what is moving

| Topic | Partitions | Key | Kept for | Written by | Read by |
|---|---|---|---|---|---|
| `logs.raw` | 3 | service | 24 hours | log generator | ingestion, detection |
| `logs.deadletter` | 1 | — | 7 days | ingestion | (people, for checking) |
| `anomalies.detected` | 1 | — | 7 days | detection | alerting, API |
| `alerts.events` | 1 | service | 7 days | alerting | API |

The first three topics are created by the `kafka-init` container when the stack starts. `alerts.events` was added later and is created by the alerting service or the API on their first start. Kafka keeps no data on disk between `start.ps1 down` and `up`.

### PostgreSQL: what was decided

| Table | One row per | Written by |
|---|---|---|
| `services` | monitored service | the database set-up (the five services); detection adds any new one |
| `model_registry` | registered model version; exactly one is active | training (`--register`) |
| `detection_windows` | service and minute that was judged, with its numbers and score | detection |
| `anomalies` | flagged minute: severity, reasons, sample event ids, operator verdict | detection; alerting sets `alert_id`; API sets the verdict |
| `alerts` | alert: status, severity, counts, times, who acknowledged, Telegram status | alerting; API changes the status |

The schema is in `infrastructure/docker/postgres/init.sql`. It is created on the first start of the PostgreSQL container, and again after `start.ps1 reset`.

### Elasticsearch: what was said

Every valid log event is one document in a daily index `logs-YYYY.MM.DD` (by the event's UTC date), with the event id as the document id. The index template fixes the field types and rejects unknown fields. New documents become searchable within 5 seconds. Old days are deleted as whole indices (see [Operations](operations.md#old-log-lines)).

## One fault, end to end

What happens when payment-service starts failing, with the median times measured in the live runs:

1. The generator writes failing payment calls to `logs.raw`.
2. **Ingestion** stores each line in Elasticsearch, 0.6 s after it was written. It is searchable on the Logs page within about 6 s.
3. **Detection** adds each line to the current minute of payment-service. About 5 s after the minute ends (the grace period), it judges the minute: the error rate is far above normal, the score passes the threshold, severity HIGH.
4. Detection stores the window and the anomaly in PostgreSQL, *then* publishes the anomaly to `anomalies.detected`.
5. The **API** receives the anomaly and pushes it to every open dashboard: on the screen 0.06 s later.
6. **Alerting** opens an alert for payment-service (about 0.7–1 s after the anomaly), publishes it on `alerts.events`, and hands the Telegram message to its background sender, which sends it about 1 s later.
7. More failing minutes join the same alert. Five minutes after the last one, alerting resolves the alert and, if Telegram was told about it, sends the final message.

From the fault's start to the anomaly takes the rest of the current minute plus about 6 seconds: 8 to 69 seconds in the live runs. Details: [latency results](../testing/latency-results.md).

## Design decisions

| Decision | Why |
|---|---|
| **Kafka between every step** | The generator, storage and detection run at their own speed. If a service stops, its messages wait in Kafka, and it catches up when it starts again. |
| **Ingestion and detection read the same topic independently** | Storing logs and judging them never slow each other down; a slow Elasticsearch cannot delay an alert. |
| **Logs keyed by service** | All lines of one service arrive in order on one partition. |
| **At-least-once, with idempotent writes** | Every service commits its Kafka offset only after its work is stored. After a crash, the uncommitted messages are read again. Repeats are harmless: Elasticsearch documents use the event id, a window is stored once per service, minute and model, and an anomaly that already has an alert is ignored. |
| **PostgreSQL is the source of truth** | Anomalies are stored before they are published. A dashboard that missed a live event loads it again from the API. |
| **Event time, not arrival time** | A minute is judged by the timestamps in the logs, closed with a per-partition watermark and a 5-second grace period. A backlog after a pause is therefore judged exactly like live traffic. |
| **One detection process** | Each process must see all partitions, otherwise a service it cannot see would look silent. A second process makes both stop judging, with a warning. |
| **The API listens to every partition itself** | A consumer group shares messages between its members; the live feed must instead give *every* API instance *every* event. The API assigns itself all partitions at the end of the topics; history comes from the REST endpoints. |
| **Telegram in the background** | Storing and showing alerts never waits for a slow network. |
| **The dashboard talks to one address** | The Vite dev server forwards `/api` (REST and WebSocket) to port 8000, so the browser never makes a cross-origin request. |

Each decision, with the evidence behind it, is in the design documents listed at the end of this page.

## When something stops

| What stops | What happens | What to do |
|---|---|---|
| Ingestion | Logs wait in Kafka. Detection, alerts and the dashboard keep working; only the Logs page and the sample log lines are missing | Start it again: it catches up |
| Elasticsearch | Ingestion retries, then stops without committing. The API answers log requests with 503 | Start the stack, then ingestion |
| Detection | No new anomalies. Logs keep being stored | Start it again: it judges the backlog minute by minute |
| Alerting | Anomalies still appear; no alerts, no Telegram | Start it again: it continues with the anomalies it has not processed |
| The API | The dashboard shows *Backend unreachable*. The pipeline keeps working | Start it again; the dashboard reconnects |
| The computer sleeps | Everything pauses. On waking, every service rejoins Kafka; detection discards its open minutes and rebuilds them from Kafka | Nothing; the timing of that period is not meaningful |

## Limits

- **One computer.** Kafka has one broker and no replication; Elasticsearch has one node.
- **No login.** The API and the dashboard are meant for a local machine.
- **One detection process.** Detection cannot be spread over several machines in its current form.
- **Simulated services.** The logs come from the generator; real services would need their logs sent to `logs.raw` in the same format ([data contracts](../design/contracts.md)).

## Further reading

| Document | Contents |
|---|---|
| [Data contracts](../design/contracts.md) | The log event format, Kafka topics and messages |
| [Database design](../design/database-design.md) | Tables, relationships, indexes |
| [Elasticsearch design](../design/elasticsearch-design.md) | Index naming, template, mappings |
| [Detection design](../design/detection-design.md) | Windows, watermark, features, model, severity, each with its evidence |
| [API contracts](../design/api-contracts.md) | The full API specification |
| [System architecture](../architecture/system-architecture.md) | The original architecture document from the design phase |

## Next

- [Using the dashboard](using-the-dashboard.md): what every page shows.