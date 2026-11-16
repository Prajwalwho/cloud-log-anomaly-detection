# Operations

Everything needed to run the system day to day: starting and stopping, checking that it is healthy, freeing disk space, retraining the model, testing and measuring. All commands are run in PowerShell from the project folder, with the Python environment active (see [Getting started](getting-started.md)).

## The infrastructure: `start.ps1`

Kafka, PostgreSQL and Elasticsearch run in Docker. One script controls them:

| Command | What it does |
|---|---|
| `.\scripts\start.ps1 up` | Starts the containers, waits until all three are healthy and the Kafka topics exist, then runs the smoke test. Ends with **Stack is up.** |
| `.\scripts\start.ps1 down` | Stops and removes the containers. PostgreSQL and Elasticsearch data is kept; Kafka's messages are cleared |
| `.\scripts\start.ps1 status` | Shows the containers and their health |
| `.\scripts\start.ps1 logs` | Follows the containers' own logs (Ctrl+C to stop). Add `kafka`, `postgres` or `elasticsearch` for one of them |
| `.\scripts\start.ps1 test` | Runs only the smoke test |
| `.\scripts\start.ps1 reset` | Deletes **all** PostgreSQL and Elasticsearch data (models, anomalies, alerts, stored logs). Asks you to type `yes` first |

The addresses: Kafka `localhost:9092`, PostgreSQL `localhost:15432`, Elasticsearch <http://localhost:9200>.

> [!WARNING]
> After `reset` the model registry is empty too. Register a model again (see [Retraining the model](#retraining-the-model)) before starting the detection service.

## Starting and stopping the services

Start the parts in this order, each in its own terminal:

| # | Service | Command | Ready when it prints |
|---|---|---|---|
| 1 | API | `uvicorn backend.api.app.main:app --port 8000` | `Application startup complete` |
| 2 | Ingestion | `python -m backend.ingestion.consumer` | `Ingestion consuming 'logs.raw' …`, then `received …` lines while logs arrive |
| 3 | Detection | `python -m backend.detection.service` | `Detection service: model …` with the active model's name and version |
| 4 | Alerting | `python -m backend.alerting.service` | `Telegram: on …` or `Telegram: off` |
| 5 | Dashboard | `npm run dev` (in `frontend`) | `Local: http://localhost:5173/` |
| 6 | Traffic | `python -m backend.log_generator.generator --kafka …` | lines of sent events |

Why this order: the alerting and detection services only see what arrives after their first start, so they must be running before the traffic. Ingestion can be started late: it catches up on everything still in Kafka.

Stop a service with **Ctrl+C** in its terminal. Every service finishes its current batch, commits what it has done and exits; on the next start it continues where it stopped.

### Which services are running

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId, CommandLine
```

On Windows each service appears twice (the launcher and the Python process). To stop all project services at once:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -match 'backend\.|scripts' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

> [!IMPORTANT]
> Run **one** copy of each service. Two detection services would split the three partitions of `logs.raw` between them; each would then see only part of the traffic, so the detection service refuses to judge and prints `this process has 1 of 3 partitions …`. Two alerting services would both send Telegram messages. Close the extra copy.

## Is everything healthy?

| Check | Where |
|---|---|
| Containers | `.\scripts\start.ps1 status`: all three `healthy` |
| Whole system | The dashboard sidebar: *All systems running*, *Live updates on* |
| API | <http://localhost:8000/api/v1/health> |
| Each service | Its terminal: regular progress lines and no `[WARN]` or `[FAIL]` lines repeating |

### Is a service keeping up? (consumer lag)

Kafka remembers, per consumer group, which message each service has reached. The difference to the newest message is the **lag**:

```powershell
docker exec cla-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group detection-group
```

Use `ingestion-group` or `alerting-group` for the other services. A lag that stays small (or 0) is healthy. A lag that keeps growing means the service is stopped or too slow.

### Skipping old messages

After a long pause, a service normally works through everything Kafka still holds (`logs.raw` keeps 24 hours). To make it start from now instead, stop the service, then move its group to the end of the topic:

```powershell
docker exec cla-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group detection-group --reset-offsets --to-latest --topic logs.raw --execute
```

The same works for `ingestion-group`. For the alerting service, use `--group alerting-group --topic anomalies.detected`.

## Laptop runs

On many laptops the screen switching off suspends every program, Docker included. Before a long run, plug in the charger and turn off sleep, as described in [Before a long run on a laptop](getting-started.md#before-a-long-run-on-a-laptop). If the laptop does sleep, the services recover by themselves when it wakes; the detection service drops the windows it had open, and nothing wrong is reported.

## Disk space

Three things use space: Elasticsearch (stored log lines, the largest), PostgreSQL (small) and Docker's virtual disk.

### Old log lines

Log lines are stored in one Elasticsearch index per day (UTC), named `logs-YYYY.MM.DD`. List them with their size:

```powershell
curl.exe -s "http://localhost:9200/_cat/indices/logs-*?h=index,docs.count,store.size"
```

Delete one day by its full name (Elasticsearch refuses deletes with `*`, as a protection):

```powershell
curl.exe -X DELETE "http://localhost:9200/logs-2026.11.09"
```

Anomalies and alerts are kept in PostgreSQL and are not affected. Their detail pages then say that the log lines are no longer stored.

### Kafka

Kafka keeps messages for a limited time (`logs.raw` 24 hours, `logs.deadletter` and `anomalies.detected` 7 days). `.\scripts\start.ps1 down` clears all of them at once.

### Docker's virtual disk (Windows)

Docker Desktop keeps its data in a virtual disk file that grows but never shrinks by itself, even after data is deleted. To give the space back to Windows:

1. Stop the services, run `.\scripts\start.ps1 down`, and quit Docker Desktop.
2. Shut down WSL:

   ```powershell
   wsl --shutdown
   ```

3. Find the disk file. It is `docker_data.vhdx` under `%LOCALAPPDATA%\Docker\wsl\disk\` (older versions: `ext4.vhdx` under `%LOCALAPPDATA%\Docker\wsl\data\`):

   ```powershell
   Get-ChildItem "$env:LOCALAPPDATA\Docker\wsl" -Recurse -Filter *.vhdx | Select-Object FullName, Length
   ```

4. Open PowerShell **as administrator** and start `diskpart`:

   ```powershell
   diskpart
   ```

5. In diskpart, one line at a time, with your file's full path:

   ```text
   select vdisk file="C:\Users\<you>\AppData\Local\Docker\wsl\disk\docker_data.vhdx"
   attach vdisk readonly
   compact vdisk
   detach vdisk
   exit
   ```

6. Start Docker Desktop again, then `.\scripts\start.ps1 up`.

## Retraining the model

Train a new model when the normal behaviour of the services changes (new endpoints, a different traffic rate). The steps are the same as in [Getting started, step 4](getting-started.md#4-train-the-detection-model-once): generate normal traffic and a fault run, then train with a **new** `--version` (a version can never be overwritten) and `--register`:

```powershell
python -m backend.detection.train --train data/processed/train_normal_1.jsonl data/processed/train_normal_2.jsonl data/processed/train_normal_3.jsonl --version 1.2.0 --eval data/processed/all_faults.jsonl --ground-truth data/ground_truth/<run-id>.jsonl --normal-eval data/processed/normal_eval_4.jsonl --register
```

`--register` makes the new model the active one; the previous versions stay in the registry and on the Models page. Restart the detection service to use it. Model packages go to `models/trained/<name>-<version>/`; a copy of each model's metadata goes to `models/metadata/`.

## Tests

```powershell
pytest
```

runs every test. Integration tests need the stack and are skipped when it is down. Without Docker:

```powershell
pytest tests/unit
```

The dashboard has its own checks, run inside `frontend`:

```powershell
npm run lint
```

```powershell
npm run build
```

## Measuring

The scripts used for the results in `docs/testing/`. Each writes its results to `experiments/results/`.

| Script | Measures | Example |
|---|---|---|
| `scripts/run_live_evaluation.ps1` | Five fault runs and a fault-free hour back to back, then evaluates them (about 4 h 40 min) | `.\scripts\run_live_evaluation.ps1` |
| `scripts/live_eval.py` | One run against its ground truth: incidents found, delays, false alarms | `python scripts/live_eval.py run data/ground_truth/eval-r1.jsonl --label r1` |
| `scripts/latency_report.py` | How long each step takes, from a log line to the dashboard and Telegram | `python scripts/latency_report.py watch --minutes 32 --label live1` |
| `scripts/load_test.py` | Whether ingestion and detection keep up at higher traffic rates | `python scripts/load_test.py --label l1` |

For a load test, start the alerting service with `--no-telegram`: a jump in traffic is a real anomaly for a model trained at normal traffic, and you do not want those messages on your phone.

The generator's `--jitter 60` delays each fault by a random 0 to 60 seconds, so faults start at different seconds of the minute:

```powershell
python -m backend.log_generator.generator --kafka --scenario all --jitter 60
```

## Troubleshooting

| What you see | What to do |
|---|---|
| Scripts say Docker is not running | Start Docker Desktop, wait until it is ready, then `.\scripts\start.ps1 up` |
| A service says Kafka, PostgreSQL or Elasticsearch is not reachable | The stack is stopped or still starting (for example after the laptop slept): `.\scripts\start.ps1 up` and wait for **Stack is up.** |
| Elasticsearch unhealthy | Docker Desktop needs about 2 GB of memory; check `.\scripts\start.ps1 logs elasticsearch` |
| "port is already allocated" | Another program uses the port; change it in `.env` |
| PostgreSQL "password authentication failed" | Another PostgreSQL may be using the port. Change `POSTGRES_PORT` in `.env`, then `.\scripts\start.ps1 reset` |
| Detection: `No active model in model_registry` | Train and register a model |
| Detection: `this process has 1 of 3 partitions …` | A second detection service is running; close one |
| Detection skips events "more than 5 min in the future" | Expected for wrong timestamps. To replay a `--fast` run, start detection with `--allow-future` |
| No alert appears for anomalies | The alerting service must run before the anomalies happen; LOW anomalies never open alerts |
| Alerting says `Telegram: off` | Fill in both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` and save it |
| The Logs page shows no lines | The ingestion service is not running; start it and it catches up |
| The dashboard says the backend API is not reachable | Start the API; the page reconnects by itself |
| `npm run dev` fails with ENOENT | Run it inside the `frontend` folder |

## Next

- [API reference](api-reference.md): every endpoint of the backend API.
- [Configuration](configuration.md): every setting and command-line option.