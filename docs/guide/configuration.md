# Configuration

Every setting of the system, and every command-line option of its programs. The defaults are the values the system was built and measured with; most people never change any of them.

## How settings work

All settings live in one file, `.env`, in the project folder. `scripts/setup.ps1` creates it from `.env.example`. Git ignores `.env`, because it holds passwords and the Telegram token.

- Each service reads `.env` **when it starts**. After a change, restart the services that use the setting.
- A setting missing from `.env` uses the default shown on this page. `.env.example` lists only the settings most people need.
- Names are not case-sensitive: `ALERT_GROUP_GAP_S` and `alert_group_gap_s` are the same setting.
- A variable set in the terminal (`$env:NAME = "value"`) wins over `.env` for programs started from that terminal.
- Start every service **from the project folder**: `.env` is looked for in the current folder.

The settings are defined, with their defaults, in the `config.py` of each service.

## Connections

Used by every service that talks to these stores.

| Setting | Default | Used by | Meaning |
|---|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | all | Where Kafka is |
| `POSTGRES_HOST` | `localhost` | detection, alerting, API | PostgreSQL's host |
| `POSTGRES_PORT` | `15432` | detection, alerting, API, Docker | PostgreSQL's port (15432 avoids a local PostgreSQL on 5432) |
| `POSTGRES_DB` | `cla_db` | detection, alerting, API, Docker | Database name |
| `POSTGRES_USER` | `cla_user` | detection, alerting, API, Docker | User name |
| `POSTGRES_PASSWORD` | `change_me` | detection, alerting, API, Docker | Password |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | ingestion, API | Where Elasticsearch is |
| `ELASTICSEARCH_PORT` | `9200` | Docker | The port Elasticsearch is published on |
| `ELASTICSEARCH_INDEX_PREFIX` | `logs` | ingestion, API | Daily indices are named `<prefix>-YYYY.MM.DD` |

The settings marked *Docker* are also read by `start.ps1` when it creates the containers. PostgreSQL takes its database name, user and password only when its data volume is created; to change them later, run `.\scripts\start.ps1 reset` (this deletes all data).

## Kafka topics and consumer groups

| Setting | Default | Used by |
|---|---|---|
| `KAFKA_TOPIC_LOGS` | `logs.raw` | generator, ingestion, detection |
| `KAFKA_TOPIC_DEADLETTER` | `logs.deadletter` | ingestion |
| `KAFKA_TOPIC_ANOMALIES` | `anomalies.detected` | detection, alerting, API |
| `KAFKA_TOPIC_ALERTS` | `alerts.events` | alerting, API |
| `INGESTION_GROUP_ID` | `ingestion-group` | ingestion |
| `DETECTION_GROUP_ID` | `detection-group` | detection |
| `ALERTING_GROUP_ID` | `alerting-group` | alerting |
| `API_GROUP_ID` | `api-group` | API (a name only: the live feed reads every partition itself and commits nothing) |

> [!WARNING]
> The topics `logs.raw`, `logs.deadletter` and `anomalies.detected` are created by Docker with these names. Renaming them in `.env` alone breaks the pipeline.

## Log generator

| Setting | Default | Meaning |
|---|---|---|
| `GENERATOR_RATE` | `20` | Average user requests per second (about 3 log lines each) |
| `GENERATOR_SEED` | empty | Random seed; empty means different traffic every run |

## Ingestion

| Setting | Default | Meaning |
|---|---|---|
| `INGESTION_BATCH_SIZE` | `500` | At most this many messages are stored and committed together |
| `INGESTION_POLL_TIMEOUT_S` | `1.0` | How long to wait for a batch to fill |

## Detection

| Setting | Default | Meaning |
|---|---|---|
| `MODELS_DIR` | `models/trained` | Where model packages are read from |
| `WINDOW_S` | `60` | Window length in seconds |
| `GRACE_S` | `5` | How long after a minute ends it is judged |
| `SERVICES` | the five services | Comma-separated: the services that get a window every minute, with or without logs |

> [!CAUTION]
> The model was trained with 60-second windows. Changing `WINDOW_S` without training a new model makes its scores meaningless.

## Alerting

See [Alerts and Telegram](alerts-and-telegram.md#settings) for what each one does.

| Setting | Default |
|---|---|
| `ALERT_GROUP_GAP_S` | `300` |
| `ALERT_MIN_SEVERITY` | `MEDIUM` |
| `ALERT_RESOLVE_AFTER_S` | `300` |
| `ALERT_RESOLVE_CHECK_S` | `30` |
| `NOTIFY_MIN_SEVERITY` | `HIGH` |
| `TELEGRAM_BOT_TOKEN` | empty (secret) |
| `TELEGRAM_CHAT_ID` | empty |

## API

| Setting | Default | Meaning |
|---|---|---|
| `POSTGRES_POOL_MAX` | `10` | At most this many open database connections |
| `DEPENDENCY_TIMEOUT_S` | `3` | How long a health check or a database wait may take |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated web pages allowed to call the API from a browser |
| `LIVE_KAFKA_ENABLED` | `true` | The live feed; tests without Kafka switch it off |
| `LIVE_PING_S` | `30` | Seconds between `ping` messages on the live feed |
| `LIVE_QUEUE_SIZE` | `100` | Messages kept per browser; a browser that falls further behind is disconnected |

## Command-line options

Options change one run only; they are not saved.

### Services

| Program | Option | Meaning |
|---|---|---|
| ingestion, detection, alerting | `--group NAME` | Use another consumer group, for example to read everything in Kafka again without touching the normal group |
| ingestion, detection, alerting | `--idle-exit SECONDS` | Stop after this many seconds without messages (for replays and tests) |
| ingestion | `--sink counting` | Count the events instead of storing them (for speed tests) |
| detection | `--allow-future` | Accept timestamps more than 5 minutes in the future; only for replays of `--fast` runs |
| alerting | `--no-telegram` | Store and publish alerts but send no Telegram messages |

For example, to replay everything still in Kafka through detection with a fresh group, and stop when done:

```powershell
python -m backend.detection.service --group detection-replay --idle-exit 30 --allow-future
```

### Log generator

`python -m backend.log_generator.generator [options]`

| Option | Default | Meaning |
|---|---|---|
| `--kafka` | off | Send the events to Kafka |
| `--output FILE` | — | Write the events to a JSON-lines file |
| `--pretty` | off | Readable console output instead of JSON |
| `--duration SECONDS` | `10` | How long to generate; `0` = until Ctrl+C. Extended automatically to fit the scenarios |
| `--rate N` | `20` | User requests per second |
| `--seed N` | none | Same seed, same traffic |
| `--fast` | off | Generate as fast as possible instead of in real time (for files) |
| `--scenario NAME …` | none | Faults to inject, in order; `all` = all five |
| `--warmup SECONDS` | `300` | Normal traffic before the first fault |
| `--gap SECONDS` | `300` | Normal traffic after each fault |
| `--jitter SECONDS` | `0` | Delay each fault by a random 0 to this many seconds |
| `--ground-truth FILE` | `data/ground_truth/<run_id>.jsonl` | Where the record of the faults goes |
| `--list-scenarios` | — | List the scenarios and exit |

The scenarios:

| Scenario | Fault | Length |
|---|---|---|
| `error_burst` | payment-service fails 40% of its calls | 2 min |
| `latency_spike` | order-service becomes 6 times slower | 2 min |
| `new_error` | inventory-service logs a never-seen error in 15% of its calls | 2 min |
| `silent_service` | auth-service stops logging | 2 min |
| `cascading_failure` | order-service 3 times slower; after 1 min payment-service fails 30%, after 1.5 min inventory-service 20% | 3 min |

`--scenario all` with the default warm-up and gaps takes about 41 minutes.

### Training

`python -m backend.detection.train [options]`

| Option | Meaning |
|---|---|
| `--train FILE …` | Normal-traffic files to learn from (required) |
| `--version V` | The new model's version (required; never reused) |
| `--name NAME` | Model name (default `live-pca`) |
| `--algorithm pca\|ocsvm` | Model type (default `pca`) |
| `--raw-counts` | Use raw counts instead of log-scaled counts |
| `--per-service` | One model per service instead of one for all |
| `--eval FILE`, `--ground-truth FILE` | A fault run and its ground truth, to report what is detected |
| `--normal-eval FILE` | A fresh fault-free run, to report false alarms |
| `--register` | Store the model in PostgreSQL and make it the active one |

The model in use (`live-pca 1.1.0`) was trained with the defaults; the other choices are kept for comparison (see *Why PCA* in [How detection works](how-detection-works.md#5-the-model-pca-in-plain-words)).

## Scripts

All in `scripts/`, run from the project folder with the Python environment active.

| Script | What it does |
|---|---|
| `setup.ps1` | One-time set-up: Python environment, packages, `.env`, dashboard packages, Docker images |
| `start.ps1` | Start, stop, check and reset the containers (see [Operations](operations.md#the-infrastructure-startps1)) |
| `smoke_test.py` | Checks Kafka, PostgreSQL and Elasticsearch (run by `start.ps1 up`) |
| `telegram_setup.py [--send]` | Finds your Telegram chat id; sends a test message |
| `watch_live.py` | Prints the API's live feed |
| `search_logs.py` | Searches stored logs from the terminal (`--service`, `--level`, `--q`, `--trace`, `--minutes`, `--size`) |
| `kafka_peek.py` | Shows messages in a topic and checks the keys (`--topic`, `--show`) |
| `summarize_logs.py FILE` | A per-minute summary of a log file, with `--ground-truth` faults marked |
| `check_detection.py GT_FILE` | Compares stored anomalies with a run's ground truth |
| `send_invalid_logs.py` | Sends broken messages, to test the dead-letter topic |
| `send_future_log.py` | Sends one event dated in the future; ingestion and detection must both reject it |
| `pipeline_latency.py --minutes N` | Time from a log line being written to being stored in Elasticsearch, for the last N minutes |
| `live_eval.py`, `run_live_evaluation.ps1`, `latency_report.py`, `load_test.py` | The measurements of Phase 10 (see [Operations](operations.md#measuring)) |

One more tool is in `experiments/`: `python experiments/replay_windows.py FILE --ground-truth GT_FILE` replays a log file through the windows and features, without Kafka.

## Next

- [Glossary](glossary.md): every term in one list.