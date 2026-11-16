# FAQ

Questions that come up when using, testing or presenting the system. For problems with a quick fix, see also the troubleshooting table in [Operations](operations.md#troubleshooting).

## About detection

### Why does it not need examples of failures?

The model learns only what normal minutes look like and flags whatever does not fit. Real failures are rare, varied and seldom labelled, so a method that needs failure examples would only find the failures it has already seen. This one also finds new kinds, such as an error message that never appeared before. See [How detection works](how-detection-works.md).

### Why one-minute windows?

A minute holds enough lines for stable numbers (an error rate from 240 lines means something; from 4 lines it does not), and it is short enough that an anomaly appears within about a minute of a fault. Shorter windows would be noisier, longer ones slower.

### How long after a fault does the anomaly appear?

The rest of the current minute, plus about 6 seconds: 8 to 69 seconds in the live runs, depending on when in the minute the fault starts. The alert follows about a second later, the Telegram message about a second after that. See [How detection works](how-detection-works.md#how-long-until-an-anomaly-appears).

### The fault was in payment-service. Why is the gateway flagged too?

Because the gateway really is affected: it calls payment-service and reports its failures to its own callers as errors. The system shows where a fault is *felt*, not only where it starts. The anomaly's reasons, and *Follow this request* on the Logs page, show which service failed first.

### Why did one fault give several alerts?

Alerts are per service. A fault that affects payment-service and the gateway gives two alerts; a cascading failure across four services gives four. In the live runs, there were 2.5 alerts per incident on average.

### Why is a LOW anomaly not an alert?

A LOW anomaly is a minute that is statistically unusual but has no strong reason behind it, for example a quiet minute that is slightly out of pattern. On its own it is not worth anyone's attention. It still appears on the Anomalies page, and it joins an alert that is already open for its service.

### Why are some minutes not judged?

- **The first minute after detection starts:** it began before the first line was read, so it is incomplete.
- **Minutes in which all traffic started or stopped** (for example when you start or stop the generator): every service would look like a volume drop.
- **Minutes without any traffic at all:** stored, but never flagged.

For minutes in which traffic started or stopped, the detection service prints `traffic … during this minute; not judged`.

### I stopped one service's logs on purpose. Will that be flagged?

Yes, and it should be: a service that suddenly writes nothing while the others continue is exactly what the *silent service* fault looks like. It is flagged CRITICAL with the reason `no logs (normally ~… per minute)`.

### Can I change what counts as HIGH or CRITICAL?

The severity rules (for example "error rate of 20% or more is CRITICAL") are in `backend/detection/scoring/severity.py`, explained in [How detection works](how-detection-works.md#8-severity-and-reasons). The threshold comes from training: train a new model version to change it. Which severities open alerts and send Telegram messages is set in `.env` (see [Configuration](configuration.md#alerting)).

### How good is it?

15 of 15 injected incidents found in the live runs, no false alarm in 30 quiet minutes, and one LOW anomaly (no alert) in a fault-free hour. See [How well it works](introduction.md#how-well-it-works).

## About using it

### The Logs page is empty, but anomalies appear. Why?

Log lines come from Elasticsearch, which only the ingestion service fills. Anomalies come from the detection service, which reads Kafka directly. Start the ingestion service; it catches up on everything still in Kafka (`logs.raw` keeps 24 hours).

### The API shows nothing for yesterday. Why?

The list endpoints show the last hour unless you give a time range: add `from` (and `to`), for example `?from=2026-11-13T00:00:00Z`. On the dashboard, choose a longer time range at the top.

### Can several people open the dashboard at once?

Yes. Every open dashboard gets the same live updates, and a verdict or an alert change made in one appears in all the others.

### How do I start completely fresh?

`.\scripts\start.ps1 reset` deletes all PostgreSQL and Elasticsearch data, then `.\scripts\start.ps1 up`. Register a model again before starting detection (see [Operations](operations.md#retraining-the-model)).

### What happens if the laptop sleeps during a run?

Everything pauses, and every service carries on when the laptop wakes. Nothing is lost, but the timing of that period is not meaningful, so measurements must not include it. See [Before a long run on a laptop](getting-started.md#before-a-long-run-on-a-laptop).

### Could it watch real services instead of the generator?

Yes, in principle: real services would have to send their logs to `logs.raw` in the same format ([data contracts](../design/contracts.md)), and a new model would have to be trained on their normal traffic, because a model only knows the services and messages it was trained on. Set `SERVICES` in `.env` to their names.

### Can it run without Docker?

Not as it is: Kafka, PostgreSQL and Elasticsearch are started with Docker Compose. They could run installed directly on the computer, with the connection settings in `.env` pointed at them.

### Is the Telegram token safe?

It is read only from `.env`, which Git ignores, and it is never printed: the services print `Telegram: on` or `off`, never the token. If it is ever exposed, revoke it with @BotFather (see [Alerts and Telegram](alerts-and-telegram.md#setting-up-telegram)).

## Small problems

### Windows says a port is "forbidden by its access permissions"

Windows reserves some port ranges. List them, then choose a free port in `.env`:

```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```

### `telegram_setup.py` finds no messages

The bot only shows recent messages. Send your bot a new message, then run the script again within a few minutes.

### `check_detection.py` shows `0/0` windows for a fault

The run was not finished yet, or the detection service was not running during it.

### `watch_live.py` cannot connect, or says "closed by the server"

Start (or restart) the API first.

### The API restarts whenever I edit other code

Start uvicorn with `--reload --reload-dir backend/api`, so it only watches its own folder. Without `--reload` it never restarts by itself.

### The smoke test says Kafka topics are missing

The topics are created a few seconds after Kafka starts. `start.ps1 up` waits for them; if you ran the smoke test by hand, run it again.

### pytest says "import file mismatch"

Two test files have the same name. Integration test files must end in `_integration.py`.

### A new folder does not show up in `git status`

A pattern in a `.gitignore` may match it. Check which one:

```powershell
git check-ignore -v <path>
```

## Next

- Back to the [introduction](introduction.md).