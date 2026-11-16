# Introduction

Observatory watches the logs of a group of cloud services while they are being written, notices when a service starts behaving unusually, and tells the operator on a dashboard and on their phone, usually within a minute.

The project's full title is *Cloud Log Anomaly Detection for Proactive Fault Management*: find faults in the logs early, before they turn into outages that users notice.

## The problem

A modern application is made of many small services: a gateway, a login service, an order service, a payment service and so on. Each of them writes a stream of log lines, thousands per minute in total. When something starts to go wrong, the logs usually show it first:

- more errors than usual,
- requests getting slower,
- an error message nobody has seen before,
- a service that suddenly stops writing anything.

Nobody can read thousands of lines a minute, and fixed rules ("alert if more than 50 errors") either miss new kinds of failure or raise alarms all the time. This project learns what *normal* looks like for each service and points out the minutes that do not fit.

## What it does

- **Collects** every log line through Apache Kafka and stores it, searchable, in Elasticsearch.
- **Learns normal behaviour** with a machine-learning model trained on normal traffic only. No examples of failures are needed.
- **Judges every service every minute.** An unusual minute becomes an **anomaly** with a severity (LOW, MEDIUM, HIGH, CRITICAL) and reasons in plain language, for example `error rate 29.1%` or `no logs (normally ~805 per minute)`.
- **Turns anomalies into alerts.** Anomalies of the same service close together form one alert. It escalates if things get worse and resolves by itself after five quiet minutes.
- **Notifies** the operator on Telegram for HIGH and CRITICAL alerts: one message when the alert starts, one if it becomes critical, one when it is resolved.
- **Shows everything live** on a dashboard: a sky of services, the anomalies and their log lines, the alerts, a log search that can follow one request through all services, and the model in use.

## How it works in one minute

```text
Log generator (5 simulated services, faults injected at known times)
        │
        ▼
   Apache Kafka  (topic logs.raw)
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

1. The **log generator** simulates users sending requests through five services. It can inject faults (for example "the payment service fails 40% of calls for two minutes") and writes down exactly when each fault happened.
2. **Kafka** carries every log line. Two services read it independently, so storing and detecting never slow each other down.
3. The **ingestion service** checks each line against the agreed format and stores it in **Elasticsearch**.
4. The **detection service** turns each message into a template ("Payment failed for order <*>"), counts what happened per service in each minute and asks the model whether that minute looks normal.
5. Every anomaly is stored in **PostgreSQL** and published back to Kafka.
6. The **alerting service** groups anomalies into alerts and sends the Telegram messages.
7. The **API** serves all data to the **dashboard** and pushes new anomalies and alerts to it within about a second.

## What it can detect

The log generator has five fault scenarios. All of them were detected in the live evaluation.

| Fault | What happens in the logs | How the anomaly explains it |
|---|---|---|
| Error burst | payment-service fails 40% of its calls | `error rate 29.1%` |
| Latency spike | order-service becomes six times slower | `p95 latency 348 ms (5.86x normal)` |
| New error | inventory-service logs an error message never seen before | `1 new message type(s)` |
| Silent service | auth-service crashes and writes nothing | `no logs (normally ~805 per minute)` |
| Cascading failure | the database slows down; order, payment and inventory fail one after another | several anomalies, one alert per service |

A failure also shows up where it is felt: when the payment service fails, the gateway reports errors to its callers, and the system flags the gateway too.

## How well it works

Measured on one laptop with all services running live (Phase 10):

| Question | Result |
|---|---|
| Are injected faults found? | 15 of 15 incidents in three runs |
| False alarms during quiet periods? | 0 in 30 quiet minutes; 1 LOW anomaly in a fault-free hour (285 service-minutes), no alert |
| How fast? | An anomaly about 6 seconds after the minute in which the fault became visible ends; 8–69 seconds after the fault starts, depending on when in the minute it starts |
| How fast is a log line searchable? | Stored after 0.6 s (median), searchable within about 6 s |
| How fast is the operator told? | The anomaly is on the dashboard within 0.1 s, its alert about 1 s later; the Telegram message about 1 s after the alert opens (longer on a slow connection) |
| How much traffic? | 735 log lines per second (10 times the normal load) without falling behind |

The details, and what the numbers do not show, are in the test reports: [live evaluation](../testing/live-evaluation-results.md), [speed](../testing/latency-results.md), [load test](../testing/load-test-results.md) and [improvements](../testing/improvements-results.md).

## What it is, and what it is not

- **A complete, working system on one computer.** Kafka, PostgreSQL and Elasticsearch run in Docker; the Python services and the dashboard run on the same machine.
- **The services are simulated.** The log generator plays the part of a real application, which makes it possible to inject faults at known times and measure exactly what was found and how fast.
- **A research project as well.** Before the live system was built, several detection methods were compared on two public log datasets (HDFS and BGL). See the [research plan and results](../research/research-plan.md).
- **Not a production product.** Kafka runs as a single node, the API has no login, and one detection process must see all log partitions. These limits are written down where they apply.

## The parts

| Part | What it does | Code |
|---|---|---|
| Log generator | Simulated traffic through five services, fault scenarios, ground truth | `backend/log_generator/` |
| Ingestion | Kafka → validation → Elasticsearch; broken messages to a dead-letter topic | `backend/ingestion/` |
| Detection | Templates, one-minute windows, model, severity, reasons | `backend/detection/` |
| Alerting | Alerts, escalation, automatic resolution, Telegram | `backend/alerting/` |
| API | REST endpoints and the live WebSocket feed | `backend/api/` |
| Dashboard | The pages you are reading this in | `frontend/` |
| Infrastructure | Docker Compose for Kafka, PostgreSQL, Elasticsearch | `infrastructure/` |

## Where to go next

- **[Getting started](getting-started.md):** install everything, start the system and watch it catch its first fault.