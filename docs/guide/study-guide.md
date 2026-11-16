# Study guide

How to learn this project well enough to explain every part of it, demonstrate it live, and answer questions about it. Work through it in order. Each session takes about one to two hours.

## The project in four sentences

Say this first, in any presentation:

1. Cloud services write thousands of log lines a minute, and failures usually show in the logs first: more errors, slower calls, new error messages, or a service that goes silent.
2. This system reads every log line through Kafka, groups each service's lines into one-minute windows, and uses a PCA model trained only on normal traffic to flag minutes that do not look normal.
3. Each flagged minute gets a severity and plain-language reasons; anomalies of one service are grouped into an alert, shown live on a dashboard and sent to the operator on Telegram.
4. In live tests on one laptop it found 15 of 15 injected incidents, raised no alert in a fault-free hour, and reported a fault 8 to 69 seconds after it started.

## Study plan

Read the guide page first, then the code it points to. At the end of each session, check yourself with the *You can explain* list: say each point aloud, without looking.

### Session 1: the big picture

| Read | Where |
|---|---|
| [Introduction](introduction.md) | the guide |
| [Architecture](architecture.md) | the guide |
| [Concepts](concepts.md), sections *The data* and *The pipeline* | the guide |
| `infrastructure/docker/docker-compose.yml` | the three stores and the topic creation |

You can explain:

- the six parts and what each one reads and writes;
- why Kafka sits between the parts, and why ingestion and detection read the same topic independently;
- what is stored where: Kafka (moving), PostgreSQL (decided), Elasticsearch (said).

### Session 2: logs in, logs stored

| Read | Where |
|---|---|
| [Data contracts](../design/contracts.md) | the log event format |
| `backend/log_generator/scenarios.py` | the five faults |
| `backend/log_generator/generator.py` | requests through five services; the ground truth |
| `backend/ingestion/validator.py` | the contract checks |
| `backend/ingestion/consumer.py`, `es_sink.py` | batches, dead-letter, commit after storing, event id as document id |

You can explain:

- how one user request produces lines in several services with the same `trace_id`;
- what happens to a broken line;
- why storing a line twice does no harm (at-least-once delivery with idempotent writes).

### Session 3: detection

| Read | Where |
|---|---|
| [How detection works](how-detection-works.md) | the guide; the most important page |
| `backend/detection/preprocessing/parser.py` | masks and Drain |
| `backend/detection/windowing.py`, `watermark.py` | windows, grace period, watermark |
| `backend/detection/features/extractor.py` | the 38 features, log scaling |
| `backend/detection/live_model.py` | PCA score, threshold, 0–1 scale |
| `backend/detection/scoring/severity.py`, `judge.py` | severity rules, reasons, the "no logs" rule |
| `backend/detection/service.py` | how it all runs live; offsets committed after storing |

You can explain:

- what a template is, and why messages are masked first;
- what PCA learns, and what the score means ("the part of a minute that normal behaviour cannot explain");
- how the threshold is chosen without failure examples (99.9th percentile of training scores);
- why the model decides *whether* and fixed rules decide *how serious*;
- why the delay is "rest of the minute + about 6 seconds".

### Session 4: alerts, API and dashboard

| Read | Where |
|---|---|
| [Alerts and Telegram](alerts-and-telegram.md) | the guide |
| `backend/alerting/store.py`, `rules.py`, `notifier.py`, `background.py` | grouping, titles, messages, sending in the background |
| [API reference](api-reference.md) | the guide |
| `backend/api/app/realtime.py` | the live feed |
| [Using the dashboard](using-the-dashboard.md) | the guide |
| `frontend/src/pages/`, `frontend/src/live/LiveFeedProvider.tsx` | the pages and the WebSocket |

You can explain:

- the life of an alert: open, acknowledged, resolved; why LOW never opens one;
- the three Telegram messages, and why an alert never waits for Telegram;
- how a new anomaly reaches the screen within a second (Kafka → API → WebSocket).

### Session 5: research and results

| Read | Where |
|---|---|
| [Research plan and results](../research/research-plan.md) | RQ1, RQ2, threats to validity |
| [Detection design](../design/detection-design.md) | each decision with its evidence |
| [Live evaluation results](../testing/live-evaluation-results.md) | RQ3 |
| [Latency results](../testing/latency-results.md), [load test](../testing/load-test-results.md), [improvements](../testing/improvements-results.md) | speed, throughput, the fixes of Day 43 |

You can explain:

- what HDFS and BGL showed, and why BGL was hard (drift: 74% of normal test windows contain message types not seen in training);
- why the live model is a global PCA with log-scaled counts (six configurations compared);
- the live results and what they do *not* show (see [Limits](#limits-say-them-yourself)).

### Session 6: run it yourself

Follow [Getting started](getting-started.md) from step 2 on your own laptop, then practise the demo below twice.

## Numbers to know

| What | Number | Source |
|---|---|---|
| Services | 5 | log generator |
| Templates in normal traffic | 31 | model metadata |
| Features per window | 38 | `extractor.py` |
| Training data | 3 runs × 2 h, 1,785 windows | model metadata |
| Threshold | 99.9th percentile of training scores (raw 9.90) | `live-pca 1.1.0` |
| PCA | components explaining 95% of normal variation | `backend/detection/live_model.py`, `backend/detection/models/pca.py` |
| Window, grace | 60 s, 5 s | detection settings |
| Alert grouping, auto-resolve | 5 min, 5 min | alerting settings |
| Incidents found (live) | 15 / 15 | live evaluation |
| Recall, minutes fully inside a fault | 100% | live evaluation |
| False alarms in quiet minutes | 0 of 30 | live evaluation |
| Fault-free hour | 1 LOW anomaly in 285 windows (0.35%), 0 alerts | live evaluation |
| Detection delay | 52 s ± 7 on average, range 8–69 s | live evaluation |
| Log line stored | 0.6 s (median) | latency results |
| Anomaly on screen after storing | 0.06 s | latency results |
| Throughput | 735 events/s (10× normal), ingestion p95 0.71 s | load test |
| HDFS F1 (PCA / One-Class SVM / lookup) | 0.965 / 0.971 / 0.978 | research |
| BGL F1 (PCA, log counts + levels) | 0.486 | research |

## Demo script (about 12 minutes)

### Before the demo

1. Laptop on the charger, sleep off (see [Before a long run on a laptop](getting-started.md#before-a-long-run-on-a-laptop)).
2. Docker Desktop running, then `.\scripts\start.ps1 up` until **Stack is up.**
3. Start the API, ingestion, detection and alerting, each in its own terminal, then `npm run dev`. Check the sidebar: *All systems running*, *Live updates on*.
4. If you want Telegram in the demo, check `Telegram: on (HIGH and above)` in the alerting terminal and have your phone at hand.
5. Start normal traffic **at least two minutes before** you begin, so that detection has judged a few normal minutes:

   ```powershell
   python -m backend.log_generator.generator --kafka --scenario error_burst --warmup 300 --gap 300
   ```

   The fault starts five minutes after this command. Time your talk so you reach step 4 below just before it starts.

### During the demo

| Step | Show | Say |
|---|---|---|
| 1 | Overview | "Five services, all healthy. Every minute, each service's logs are judged by the model." |
| 2 | Logs page; open a line, *Follow this request* | "Every line is stored and searchable. One request passes through several services; this is its path." |
| 3 | Models page | "The model learned only normal traffic: 1,785 normal minutes. Here is how it was evaluated." |
| 4 | The detection terminal | "One line per minute: the number of lines per service. Now the fault starts: payment-service fails 40% of its calls." |
| 5 | Wait about a minute; Overview | "The minute has ended, plus 5 seconds: payment-service is flagged, and its planet changes colour." |
| 6 | Anomalies page; open the anomaly | "Score above the threshold, severity, and the reason in plain words: error rate. Here are the actual error lines." |
| 7 | Alerts page; phone | "Anomalies became one alert. The operator got a Telegram message." Acknowledge it with your name. |
| 8 | The gateway's anomaly | "The gateway was flagged too: it reports payment's failures to its own callers. The system shows where the fault is felt." |
| 9 | Docs | "Everything is documented inside the application." |
| 10 | Wait or explain | "Five minutes after the last anomaly, the alert resolves itself and a final Telegram message is sent." |

### If something goes wrong

- **A service stopped:** the stack was not ready. Restart that service; it continues where it stopped.
- **No anomaly yet:** if the fault started at the very end of a minute, the next minute catches it (up to 69 s in the tests).
- **No live demo possible:** set the time range to 7 days and show the anomalies and alerts of earlier runs; they are kept in PostgreSQL. Open the evaluation reports for the numbers.

## Questions you may be asked

### About the idea

**Why not use fixed rules, such as "alert above 50 errors"?**
A fixed rule only catches what it was written for, and one threshold does not fit five services with different normal levels. The model learns each service's normal behaviour and also finds kinds of failure nobody wrote a rule for, such as a new error message or a silent service. Rules are still used, but only to grade severity and explain the anomaly.

**Why unsupervised? Why not train on failures?**
Failures are rare, varied and seldom labelled. A model trained on known failures finds only those. This one needs only normal traffic, which every system has plenty of.

**Why PCA and not deep learning?**
On the HDFS benchmark, where behaviour is stable, PCA (F1 0.965) was nearly as good as One-Class SVM (0.971), and on the live data a global PCA with log-scaled counts was the best of six configurations. It is simple, needs no GPU and no failure examples, and its score has a clear meaning that can be explained to an operator. A deep model would need far more data and would be harder to explain.

**What does the PCA score mean?**
PCA finds the few directions in which normal minutes vary (95% of the variation). A new minute is projected onto them; the part that cannot be explained by normal variation is the score (the squared prediction error). A healthy busy minute is explained; a minute where errors rise without the usual pattern is not.

**How was the threshold chosen without labels?**
The 99.9th percentile of the scores of the normal training minutes: by design, about 1 normal minute in 1,000 lies above it. No failure example is needed.

### About the system

**Why Kafka?**
It decouples the parts: each reads at its own speed, and if one stops, its messages wait. Ingestion and detection read the same topic as different consumer groups, so storing and detecting never slow each other down.

**What if a service crashes in the middle of its work?**
Every service commits its Kafka position only after its work is stored. After a restart it reads the uncommitted messages again. Repeats do no harm: logs use their event id as document id, windows are unique per service, minute and model, and an anomaly that already has an alert is ignored.

**How do you handle late or out-of-order logs?**
Windows are by the time written in the log, not by arrival. A minute is closed 5 seconds after it ends, using a watermark per Kafka partition, so a backlog after a pause is judged exactly like live traffic. Lines that arrive after their minute is closed are counted and dropped, never put in a wrong minute.

**How does a crashed service get detected if it writes nothing?**
Every service gets a window every minute, even an empty one. An empty window while the other services are logging is an anomaly by rule, CRITICAL, with the reason "no logs".

**Why one alert per service, not one per incident?**
The operator needs to see *where* it hurts. A cascading failure across four services gives four alerts. In the tests that was 2.5 alerts per incident on average.

**How fast is it, and what limits the speed?**
The minute itself: an anomaly appears about 6 seconds after the minute in which the fault became visible ends, so 8 to 69 seconds after the fault starts. After that, the anomaly is on the dashboard within a tenth of a second, and the Telegram message arrives about 2 seconds later.

**How much load can it take?**
735 log lines per second, ten times the normal load, without falling behind; at that load, storing a line took 0.71 s at p95. At that load the model, trained at normal load, flags minutes as LOW, which is expected: the traffic really is unusual.

### About the results

**How did you measure accuracy?**
The log generator injects faults at known times and writes them down (ground truth). Three live runs with all five faults in rotating order, plus a fault-free hour, were compared minute by minute with the ground truth.

**Precision was 54.5%. Is that bad?**
That is the strict count, in which only the service that was given the fault counts as correct. Most other flagged minutes are real reactions, such as the gateway reporting payment's errors. Counting reactions near incidents, precision was 100%, and there was no alert outside an incident.

**Why did BGL go so badly in the research phase?**
BGL's behaviour changed between training and test (a monitoring change in November 2005): 74% of normal test windows contain message types never seen in training. Every method that flags novelty suffers from that. It showed the main weakness of this approach, which is now stated in the limits.

**Did you change anything after testing?**
Yes. The live tests found real problems, which were fixed and re-tested on Day 43: Telegram sending moved to the background, a second detection process is now detected, minutes in which all traffic starts or stops are skipped, and a stale watermark after a lost partition is cleared. See [improvements](../testing/improvements-results.md).

## Limits: say them yourself

Examiners respect a project that knows its limits. Mention these before you are asked:

- **Simulated services.** Faults are injected into generated traffic. This makes exact measurement possible, but real systems are messier.
- **One computer.** Kafka has one broker, Elasticsearch one node, and only one detection process can run.
- **A changed normal needs retraining.** New harmless messages or a higher normal load are flagged until a new model is trained.
- **Minute resolution.** Detection cannot be faster than the minute it waits for; a few seconds of fault can vanish in a minute's totals.
- **Three runs.** The live evaluation has three fault runs (n = 3), enough to show the behaviour, not to give tight confidence intervals.
- **No login.** The API and dashboard are meant for a local machine.

## Where to look things up

| Question | Page |
|---|---|
| What does this word mean? | [Glossary](glossary.md), [Concepts](concepts.md) |
| How do I start or fix it? | [Getting started](getting-started.md), [Operations](operations.md), [FAQ](faq.md) |
| What does this setting or option do? | [Configuration](configuration.md) |
| What does the API return? | [API reference](api-reference.md) |
| Why was it built this way? | [Architecture](architecture.md), [detection design](../design/detection-design.md) |
| What happened on a given day? | [Development log](../devlog/) |

## Next

- Back to the [introduction](introduction.md).