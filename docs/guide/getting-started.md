# Getting started

Install everything, start the system, and watch it catch its first fault. The first time takes about 30 minutes, mostly downloads; after that, starting the system takes about two minutes.

> [!NOTE]
> The commands are for **Windows with PowerShell**, which the project was built and tested on. Run every command from the project folder (the one that contains `README.md`) unless a step says otherwise.

## What you need

| Software | Why | Get it |
|---|---|---|
| Windows 10 or 11 with PowerShell | Scripts and commands | already installed |
| Python 3.12 | The services | `winget install -e --id Python.Python.3.12` or [python.org](https://www.python.org/downloads/) |
| Node.js with npm | The dashboard | [nodejs.org](https://nodejs.org/) (LTS version) |
| Docker Desktop | Kafka, PostgreSQL and Elasticsearch | [docker.com](https://www.docker.com/products/docker-desktop/); give it at least 4 GB of memory |
| Git | Getting the code | [git-scm.com](https://git-scm.com/) |
| Telegram (optional) | Alerts on your phone | the Telegram app |

## 1. Get the code and set it up (once)

```powershell
git clone https://github.com/Prajwalwho/cloud-log-anomaly-detection.git
```

```powershell
cd cloud-log-anomaly-detection
```

If PowerShell refuses to run scripts ("running scripts is disabled on this system"), allow scripts you create or download for your user once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then run the setup script:

```powershell
.\scripts\setup.ps1
```

It checks that Python 3.12, Node.js, npm, Git and Docker are installed, creates the Python environment in `backend\.venv`, installs the Python and dashboard packages, creates your settings file `.env` from `.env.example`, and downloads the Docker images. It is safe to run again: an existing environment and `.env` are kept.

> [!IMPORTANT]
> `.env` holds your passwords and, later, your Telegram token. It is never committed to Git. Check with `git check-ignore .env`, which must print `.env`.

## 2. Start the infrastructure

Open **Docker Desktop** and wait until it says *Engine running*. Then:

```powershell
.\scripts\start.ps1 up
```

The script starts Kafka, PostgreSQL and Elasticsearch, waits until they are healthy, creates the Kafka topics and runs a smoke test. Wait for the last lines:

```text
[OK] Kafka at localhost:9092: topics present, produce/consume works
[OK] PostgreSQL: all 5 tables present, 5 services seeded
[OK] Elasticsearch 8.17.0 at http://localhost:9200: cluster green, write/read works

Stack is up.
```

> [!WARNING]
> Start the services in the next steps only after **Stack is up.** Elasticsearch takes the longest to start; a service started earlier stops with "not reachable".

## 3. Prepare a terminal

Each part of the system runs in its own terminal window. In **every** new terminal, first activate the Python environment:

```powershell
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .\backend\.venv\Scripts\Activate.ps1)
```

The prompt then starts with `(.venv)`. Without this step Python cannot find the project's packages.

## 4. Train the detection model (once)

The detection service needs a model that has learned what normal traffic looks like. These commands create normal training data, a test run with faults, train the model, test it and register it as the active model.

Create three two-hour runs of normal traffic. With `--fast` each takes only seconds:

```powershell
python -m backend.log_generator.generator --duration 7200 --fast --seed 1 --output data/processed/train_normal_1.jsonl
```

```powershell
python -m backend.log_generator.generator --duration 7200 --fast --seed 2 --output data/processed/train_normal_2.jsonl
```

```powershell
python -m backend.log_generator.generator --duration 7200 --fast --seed 3 --output data/processed/train_normal_3.jsonl
```

Create a run with all five faults, and a fresh normal hour to count false alarms:

```powershell
python -m backend.log_generator.generator --scenario all --fast --seed 42 --output data/processed/all_faults.jsonl
```

```powershell
python -m backend.log_generator.generator --duration 3600 --fast --seed 4 --output data/processed/normal_eval_4.jsonl
```

The fault run prints a line like `Run run-20261116-145356: ground truth written to data\ground_truth\run-20261116-145356.jsonl`. Use that file name in place of `<run-id>` below, then train, check and register the model:

```powershell
python -m backend.detection.train --train data/processed/train_normal_1.jsonl data/processed/train_normal_2.jsonl data/processed/train_normal_3.jsonl --version 1.1.0 --eval data/processed/all_faults.jsonl --ground-truth data/ground_truth/<run-id>.jsonl --normal-eval data/processed/normal_eval_4.jsonl --register
```

It prints the training data, checks that the saved model gives exactly the same results after reloading (`[OK] reloaded package reproduces …`), shows which faults were found and how many false alarms the normal hour produced, and ends with `Registered model id …; active model: live-pca 1.1.0`.

> [!TIP]
> A model version can never be overwritten. To train again, use a new version number, for example `--version 1.2.0`.

## 5. Telegram (optional)

Without Telegram everything works; the alerting service only prints what it would have sent. To get alerts on your phone:

1. In Telegram, open **@BotFather**, send `/newbot`, choose a name and a username ending in `bot`, and copy the token it gives you.
2. Open your new bot and send it any message.
3. Open `.env` and fill in the token: `TELEGRAM_BOT_TOKEN=<your token>`. Leave `TELEGRAM_CHAT_ID=` empty for now and save.
4. Find your chat id and put it after `TELEGRAM_CHAT_ID=` in `.env`:

   ```powershell
   python scripts/telegram_setup.py
   ```

5. Send yourself a test message:

   ```powershell
   python scripts/telegram_setup.py --send
   ```

## 6. Start the services

Open five terminals and prepare each one as in step 3. Start the services in this order and wait for each one's start-up line before the next.

**Terminal 1, the API:**

```powershell
uvicorn backend.api.app.main:app --port 8000
```

Wait for `Application startup complete.`

**Terminal 2, ingestion:**

```powershell
python -m backend.ingestion.consumer
```

Wait for `Press Ctrl+C to stop.`

**Terminal 3, detection:**

```powershell
python -m backend.detection.service
```

Wait for `Detection service: model live-pca 1.1.0 …`

**Terminal 4, alerting:**

```powershell
python -m backend.alerting.service
```

Wait for the line ending in `Telegram: on (HIGH and above). Ctrl+C to stop.`, or `Telegram: off` without step 5.

**Terminal 5, the dashboard.** This one does not need step 3:

```powershell
cd frontend
```

```powershell
npm run dev
```

Open <http://localhost:5173>. The sidebar should say *All systems running* and *Live updates on*.

> [!IMPORTANT]
> Run **one** detection service only. Detection must see the logs of every service; a second copy splits them and both copies stop judging until one is closed. They say so with a warning.

## 7. Send traffic with a fault

Open a sixth terminal, prepare it as in step 3, and start two minutes of normal traffic, two minutes of payment errors, and five more minutes of normal traffic:

```powershell
python -m backend.log_generator.generator --kafka --scenario error_burst --warmup 120 --gap 300
```

What to expect:

| When | Where | What you see |
|---|---|---|
| Right away | Terminal 2 | `received … stored …` counting up |
| Every minute | Terminal 3 | One line per minute with the number of logs per service |
| About a minute after the fault starts | Terminal 3, Overview | `payment-service HIGH … error rate …`; the payment-service star changes colour and flares |
| A second later | Terminal 4, Alerts page, Telegram | A new alert for payment-service, and a message on your phone |
| About 5–6 minutes after the fault ends | Alerts page, Telegram | The alert is resolved, with a final message |

The gateway is often flagged too, because it reports the payment failures to its callers. Open the anomaly on the Anomalies page to see its reasons and the log lines behind it.

## 8. Stop everything

Press **Ctrl+C** in each terminal, then stop the containers:

```powershell
.\scripts\start.ps1 down
```

Anomalies, alerts and stored logs are kept (PostgreSQL and Elasticsearch). Kafka's messages are cleared.

## Before a long run on a laptop

On many laptops, switching the screen off or closing the lid suspends every program, including Docker. A run then stops for as long as the laptop sleeps.

1. Plug in the charger. The `-ac` settings below only apply on the charger. This must print `2`:

   ```powershell
   (Get-CimInstance Win32_Battery).BatteryStatus
   ```

2. Keep the screen on and the laptop awake during the run:

   ```powershell
   powercfg /change monitor-timeout-ac 0
   ```

   ```powershell
   powercfg /change standby-timeout-ac 0
   ```

3. Afterwards, restore the usual settings:

   ```powershell
   powercfg /change monitor-timeout-ac 10
   ```

   ```powershell
   powercfg /change standby-timeout-ac 30
   ```

If the laptop does sleep, the services recover by themselves when it wakes, but the run's timing is no longer meaningful.

## If something goes wrong

| What you see | What to do |
|---|---|
| A service stops with "… not reachable … Start the stack" | The infrastructure is not running or not ready: `.\scripts\start.ps1 up` and wait for **Stack is up.** |
| Detection: `No active model in model_registry` | Train and register a model (step 4) |
| Detection: `this process has 1 of 3 partitions …` | A second detection service is running. Close one (see below) |
| The dashboard says the backend API is not reachable | Start the API (terminal 1) |
| The Logs page shows no lines | The ingestion service is not running; start it and it catches up |
| `npm run dev` fails with ENOENT | Run it inside the `frontend` folder |
| Telegram says off | Both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` must be filled in `.env`, and the file saved |

To see which project services are running (on Windows each appears twice, as the launcher and the Python process):

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId, CommandLine
```

To stop all of them at once:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -match 'backend\.|scripts' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

## Next

- [Concepts](concepts.md): the words used on the dashboard and in these pages.
- [Using the dashboard](using-the-dashboard.md): what every page shows.
- [Operations](operations.md): running the system day to day, and what to do when something goes wrong.