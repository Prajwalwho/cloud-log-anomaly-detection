# Concepts

The words used throughout the dashboard, the logs of the services and these pages, each with an example from a real run. Read this page once; the other pages assume these meanings.

## The data

### Service

One of the five simulated microservices: `api-gateway`, `auth-service`, `order-service`, `payment-service` and `inventory-service`. Every request from a user enters through the gateway, which calls the others. The log generator plays all five.

### Log event

One line written by a service, as structured JSON. Every event has the same fields (the *contract*, see [contracts.md](../design/contracts.md)):

```json
{
  "schema_version": "1.0",
  "event_id": "4f0c…",
  "timestamp": "2026-11-16T14:57:03.412Z",
  "service": "payment-service",
  "host": "node-3",
  "level": "ERROR",
  "message": "Payment failed for order 482913: card processor timeout after 1840 ms",
  "trace_id": "9a1f03c2b7e4d851",
  "endpoint": "POST /internal/payments",
  "status_code": 504,
  "latency_ms": 1840.2,
  "metadata": {}
}
```

- **level**: `DEBUG`, `INFO`, `WARN`, `ERROR` or `FATAL`. *Errors* are `ERROR` and `FATAL`.
- **trace_id**: the same for every line of one user request, so a request can be followed through all services (the Logs page's *Follow this request*).
- **latency_ms**: how long the call took, where the service measured it.

A line that breaks the contract (a missing field, a timestamp more than 5 minutes in the future) is not stored; it goes to the **dead-letter** topic `logs.deadletter` with the reason.

### Template

The fixed part of a message, with the variable parts replaced. The detection service finds templates with **Drain**, a well-known log-parsing algorithm. Before Drain sees a message, numbers, identifiers, paths and similar values are masked:

```text
Payment failed for order 482913: card processor timeout after 1840 ms
Payment failed for order 771204: card processor timeout after 2210 ms
        ↓
Payment failed for order <NUM>: card processor timeout after <NUM> ms
```

The normal traffic of the five services produces 31 templates. A message that matches none of them is a **new message type**, often the first sign of a new kind of failure.

### Window

Everything one service logged in one minute (UTC, from :00 to :59). For each window the detection service counts the lines, errors and warnings, how often each template appeared, the latencies, and the number of new message types. Every service gets a window every minute, even one with no lines: a crashed service is visible only as an empty window.

## Detection

### Anomaly score and threshold

The model gives each window a **score**: how far the window is from normal behaviour. The **threshold** was set during training so that only about 1 in 1,000 normal windows lies above it. The dashboard shows the score on a scale from 0 to 1:

| Score | Meaning |
|---|---|
| below 0.5 | normal (below the threshold) |
| 0.5 | exactly at the threshold |
| 0.75 | 10 times the threshold |
| 0.83 | 100 times the threshold |

### Anomaly

A window above the threshold, or a window with **no logs** while the other services are logging. Every anomaly has a severity and reasons. It is stored in PostgreSQL, shown on the Anomalies page and sent to the alerting service.

### Severity

How serious an anomaly is: **LOW**, **MEDIUM**, **HIGH** or **CRITICAL**. The model decides *whether* a window is unusual; simple rules decide *how serious* it is, by comparing the window with the service's normal values:

| Signal | MEDIUM | HIGH | CRITICAL |
|---|---|---|---|
| Error rate | 1% or more | 5% or more | 20% or more |
| Log volume compared with normal | | 50% or less | 10% or less, or no logs |
| p95 latency compared with normal | 1.5 times | 3 times | |
| New message types | any | | |

The severity is that of the strongest signal. **LOW** means the model flagged the window but no single signal crosses a limit: the minute is unusual as a whole.

### Reason

The signals behind a severity, in plain words, strongest first. They are the anomaly's explanation, for example:

- `error rate 29.1%`
- `p95 latency 172 ms (2.90x normal)`
- `log volume 12% of normal (96 vs ~805)`
- `no logs (normally ~805 per minute)`
- `1 new message type(s)`
- `unusual log pattern (no single signal above its limit)` (LOW)

### Baseline

A service's normal values, learned from the training data: the median number of lines per minute and the median p95 latency. For example, auth-service normally writes about 805 lines per minute. The reasons compare against these numbers.

### Model

The trained detector, saved as a **model package** (the model, Drain's templates and a metadata file) and registered in PostgreSQL. Exactly one model is **active**; the detection service loads it at start-up. The current model is `live-pca 1.1.0`. A model version is never overwritten. See [How detection works](how-detection-works.md).

## Alerts

### Alert

What an operator acts on: anomalies of **one service** that belong together. An anomaly joins the service's open alert if it comes within 5 minutes of that alert's last anomaly; otherwise it opens a new one. The alert's severity is the highest seen so far, and its title comes from the strongest reason, for example *Error rate increase in payment-service* or *auth-service stopped logging*.

- **LOW** anomalies never open an alert, but can join one that is already open.
- An alert moves from **OPEN** to **ACKNOWLEDGED** (someone is looking at it) to **RESOLVED**.
- It is resolved automatically after **5 minutes without new anomalies**, or by an operator.

### Notification

A Telegram message about an alert. There are at most three per alert: when it reaches **HIGH**, when a notified alert becomes **CRITICAL**, and when a notified alert is **resolved**. MEDIUM alerts are shown on the dashboard only.

### Incident

One fault as it happened, for example "payment-service failed 40% of its calls for two minutes from 19:22:09". One incident usually causes several anomalies on several services (the gateway reports the failures of the services it calls) and therefore several alerts, one per affected service.

### Ground truth

The record the log generator writes of every fault it injected: scenario, service, start and end. Comparing the stored anomalies with the ground truth is how detection was measured. The services themselves never see it.

## The pipeline

### Kafka topic

A named stream of messages in Kafka:

| Topic | Carries | Kept for |
|---|---|---|
| `logs.raw` | every log event (3 partitions) | 24 hours |
| `logs.deadletter` | events that broke the contract | 7 days |
| `anomalies.detected` | every anomaly, from detection to alerting and the API | 7 days |
| `alerts.events` | every new or changed alert, from alerting to the API | 7 days |

### Partition and key

A topic is split into **partitions** so that work can be shared. Log events are sent with the **service name as key**, so all lines of one service land in the same partition, in order. `logs.raw` has three partitions for five services.

### Consumer group and offset

Each service that reads a topic does so as a **consumer group** (`ingestion-group`, `detection-group`, `alerting-group`). Kafka remembers, per group and partition, how far the group has read: its committed **offset**. Because ingestion and detection are different groups, both read every log event independently. After a restart, a service continues from its committed offset, so nothing is skipped.

A service commits only what it has fully processed. Detection, for example, commits a line only after the minute it belongs to has been judged and stored. After a crash the uncommitted lines are simply read again, which is safe because every service handles repeats correctly.

> [!IMPORTANT]
> Run only **one** detection service. Two processes in the same group split the partitions between them, and each would see only some services. Detection notices this, warns, and stops judging until one is closed.

### Grace period and watermark

A minute is judged a little after it ends, so that late lines can still arrive: the **grace period** is 5 seconds. The **watermark** is the detection service's idea of "now": the clock when it is up to date with Kafka, or, while it is catching up after a pause, the time of the latest line read from the slowest partition. A backlog is therefore judged minute by minute, never before all its lines have been read.

### Live feed

The API's WebSocket (`/api/v1/ws/live`) pushes every new anomaly and every new or changed alert to the open dashboards, usually within a tenth of a second for anomalies. The sidebar shows *Live updates on* while it is connected.

## Next

- [How detection works](how-detection-works.md): a log line's journey from the service to an anomaly, step by step.