# API reference

The dashboard gets all its data from the backend API. Any other program can use it too: a script, a monitoring tool or a browser. The API is read-only except for two changes an operator makes: a verdict on an anomaly, and the status of an alert.

- **Base address:** `http://localhost:8000/api/v1`
- **Interactive documentation:** <http://localhost:8000/docs> lists every endpoint with its parameters and lets you try them in the browser.
- **Full specification:** [api-contracts.md](../design/api-contracts.md).
- **Code:** `backend/api/app/` (one file per group of endpoints in `routers/`).

Start the API with:

```powershell
uvicorn backend.api.app.main:app --port 8000
```

## Rules for every endpoint

| Topic | Rule |
|---|---|
| Times | ISO 8601 in UTC, with milliseconds and `Z`, for example `2026-11-16T14:57:03.412Z`. A time sent without a time zone is taken as UTC |
| Time range | List endpoints take `from` and `to`. Without them: the last hour. `from` must be before `to` |
| Pages | `page` (from 1) and `size` (1 to 200, default 50). The answer is `{"items": [...], "total": N, "page": P, "size": S}` |
| Lists of values | Comma-separated and not case-sensitive: `severity=high,critical` |
| Errors | `{"detail": "…"}` with status 400 (wrong parameter), 404 (not found), 422 (wrong type, for example an id that is not a UUID) or 503 (PostgreSQL or Elasticsearch not reachable) |
| Login | None: the API is meant for one local computer |
| Browsers | Requests from other web pages are allowed only from `http://localhost:5173` (setting `CORS_ORIGINS`) |

## Endpoints

| Method and path | Returns |
|---|---|
| `GET /health` | Whether PostgreSQL, Elasticsearch and Kafka are reachable |
| `GET /services` | The monitored services |
| `GET /logs` | Search in the stored log lines |
| `GET /logs/{event_id}` | One log line |
| `GET /anomalies` | Flagged minutes, newest first |
| `GET /anomalies/{id}` | One anomaly with its sample log lines |
| `PATCH /anomalies/{id}/feedback` | Set or clear the operator's verdict |
| `GET /alerts` | Alerts, by last anomaly, newest first |
| `GET /alerts/{id}` | One alert with its anomalies |
| `PATCH /alerts/{id}` | Acknowledge or resolve an alert |
| `GET /stats/summary` | The numbers of the Overview page |
| `GET /stats/timeseries` | Chart data per service over time |
| `GET /models` | Every registered model |
| `GET /models/active` | The model in use |
| `WS /ws/live` | A live stream of new anomalies and alerts |

### Health

`GET /health`

```json
{"status": "ok", "components": {"postgres": "ok", "elasticsearch": "ok", "kafka": "ok"}}
```

If one component is down, the status is `degraded`, that component is `down`, and the HTTP status is 503. Kafka counts as reachable when the `anomalies.detected` topic exists.

### Services

`GET /services`: every service with `id`, `name`, `description` and `created_at`, sorted by name.

### Logs

`GET /logs`, from Elasticsearch, newest first.

| Parameter | Meaning |
|---|---|
| `q` | Words that must all appear in the message, for example `payment failed` |
| `service` | One service, for example `payment-service` |
| `level` | One or more of `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL` |
| `trace_id` | Every line of one request |
| `from`, `to`, `page`, `size` | As above |

Elasticsearch cannot page beyond 10,000 results, so `page × size` may be at most 10,000. Narrow the time range or the filters to go further.

```text
http://localhost:8000/api/v1/logs?service=payment-service&level=ERROR&q=timeout&size=5
```

Each item is a log event in the contract format (see [Concepts](concepts.md#log-event)).

`GET /logs/{event_id}`: one log event, or 404 when it is not (or no longer) stored.

### Anomalies

`GET /anomalies`, newest first.

| Parameter | Meaning |
|---|---|
| `service` | One service |
| `severity` | One or more of `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `feedback` | One or more of `CONFIRMED`, `FALSE_POSITIVE`, `NONE` (not reviewed) |
| `from`, `to`, `page`, `size` | As above; the time is when the anomaly was detected |

```text
http://localhost:8000/api/v1/anomalies?severity=HIGH,CRITICAL&feedback=NONE
```

An item:

```json
{
  "id": "6d0e…",
  "service": "payment-service",
  "detected_at": "2026-11-16T14:58:05.371Z",
  "window_start": "2026-11-16T14:57:00.000Z",
  "window_end": "2026-11-16T14:58:00.000Z",
  "anomaly_score": 0.84,
  "severity": "HIGH",
  "model": {"id": 3, "name": "live-pca", "version": "1.1.0"},
  "summary": {
    "log_count": 238, "error_rate": 0.147, "warn_rate": 0.012,
    "avg_latency_ms": 402.5, "p95_latency_ms": 1610.0, "new_templates": 0,
    "raw_score": 1450.2, "threshold": 9.9, "rule": null,
    "reasons": ["error rate 14.7%"]
  },
  "alert_id": "3f2c…",
  "feedback": null
}
```

The `summary` holds the minute's numbers, the model's raw score and threshold, the special rule that fired (`no_logs`, otherwise `null`), and the reasons, strongest first. `anomaly_score` is the raw score on the 0–1 scale: 0.5 at the threshold, 0.84 here at about 146 times it (see [How detection works](how-detection-works.md#6-threshold-and-score)). `alert_id` is empty for an anomaly that belongs to no alert (for example a LOW one).

`GET /anomalies/{id}` adds `sample_event_ids` and `sample_logs`: up to 10 log lines of that minute, errors first, read from Elasticsearch. If Elasticsearch is not reachable, `sample_logs` is empty and `sample_logs_error` says why. Lines that are no longer stored are left out.

`PATCH /anomalies/{id}/feedback` sets the verdict. Send `null` to clear it:

```json
{"feedback": "CONFIRMED"}
```

The answer is the changed anomaly.

### Alerts

`GET /alerts`, by the time of their last anomaly, newest first.

| Parameter | Meaning |
|---|---|
| `status` | One or more of `OPEN`, `ACKNOWLEDGED`, `RESOLVED` |
| `severity` | One or more of `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `service` | One service |
| `from`, `to`, `page`, `size` | As above; the time is that of the alert's last anomaly |

An item:

```json
{
  "id": "3f2c…",
  "service": "payment-service",
  "severity": "HIGH",
  "title": "Error rate increase in payment-service",
  "message": "error rate 14.7%",
  "status": "OPEN",
  "occurrence_count": 3,
  "first_seen_at": "2026-11-16T14:58:05.371Z",
  "last_seen_at": "2026-11-16T15:00:05.402Z",
  "acknowledged_at": null,
  "acknowledged_by": null,
  "resolved_at": null,
  "notification_sent": true
}
```

`occurrence_count` is the number of anomalous minutes; `first_seen_at` and `last_seen_at` are when its first and last anomaly were detected; `message` is the reasons of the latest anomaly; `notification_sent` says whether the Telegram message went out.

`GET /alerts/{id}` adds `anomalies`: every anomaly of the alert, newest first.

`PATCH /alerts/{id}` changes the status:

```json
{"status": "ACKNOWLEDGED", "acknowledged_by": "your name"}
```

```json
{"status": "RESOLVED"}
```

Allowed changes: `OPEN` → `ACKNOWLEDGED`, `OPEN` → `RESOLVED`, `ACKNOWLEDGED` → `RESOLVED`. Anything else, for example re-opening a resolved alert, is answered with 400. The change is pushed to every open dashboard as `alert.updated`.

### Statistics

These read the judged minutes in PostgreSQL. Minutes in which no service had any traffic are left out.

`GET /stats/summary` (`from`, `to`):

```json
{
  "total_logs": 172840,
  "total_windows": 300,
  "total_anomalies": 7,
  "open_alerts": 1,
  "error_rate": 0.0061,
  "by_severity": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 1},
  "by_service": [{"service": "payment-service", "anomalies": 4, "error_rate": 0.031}]
}
```

`open_alerts` counts alerts with the status `OPEN` at any time; everything else counts the chosen range.

`GET /stats/timeseries`:

| Parameter | Meaning |
|---|---|
| `metric` | `log_count`, `error_rate`, `avg_latency_ms`, `anomaly_score` (the highest in each step) or `anomaly_count` |
| `interval` | `1m`, `5m` (default) or `1h` |
| `service` | Only this service (default: all) |
| `from`, `to` | As above. At most 2,000 points per service |

```text
http://localhost:8000/api/v1/stats/timeseries?metric=error_rate&interval=1m&service=payment-service
```

The answer has one series per service, each a list of points `{"t": time, "v": value}`.

### Models

`GET /models`: every registered model, newest first. `GET /models/active`: the model in use, or 404 if none is active. Each has its `name`, `version`, `algorithm`, `threshold`, `training_data`, `training_samples`, `trained_at`, `is_active`, and two objects: `parameters` (its settings: algorithm, log-scaled counts, threshold percentile, score normalisation, window and grace period) and `metrics` (its evaluation on the fault run and on the fault-free run).

## The live feed

`ws://localhost:8000/api/v1/ws/live` is a WebSocket. The server sends messages; the client only listens.

```text
{"type": "anomaly.created", "data": { …an anomaly item… }}
{"type": "alert.created",   "data": { …an alert item… }}
{"type": "alert.updated",   "data": { …an alert item… }}
{"type": "ping",            "data": {}}
```

- A message arrives for every new anomaly, every new alert, and every change of an alert (a new anomaly joined it, it escalated, was acknowledged or resolved, or its Telegram message was sent).
- `ping` comes every 30 seconds, so the client knows the connection is alive.
- Only events from after the connection opened are sent. For history, use the REST endpoints.
- A client that does not read fast enough is disconnected (code 1013, "try again later"), so it cannot slow down the others. It should reconnect, as the dashboard does (after 1, 2, 4 … up to 30 seconds).

To watch the feed in a terminal:

```powershell
python scripts/watch_live.py
```

## Next

- [Configuration](configuration.md): every setting and command-line option.