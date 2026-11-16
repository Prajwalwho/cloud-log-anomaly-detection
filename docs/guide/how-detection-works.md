# How detection works

This page follows one log line from the moment a service writes it until it becomes part of an anomaly, and explains each decision on the way. The terms are explained in [Concepts](concepts.md); the full design, with the experiment behind every choice, is in [detection-design.md](../design/detection-design.md).

## The path at a glance

```text
log line in Kafka (logs.raw)
   │  1. read by the detection service (its own consumer group)
   ▼
template            2. Drain: "Payment failed for order <NUM>: …"
   │
   ▼
one-minute window   3. per service: counts, errors, latencies, templates
   │
   ▼
38 numbers          4. the features
   │
   ▼
score               5. PCA: how much of this minute normal behaviour cannot explain
   │
   ├─ above the threshold (6), or no logs at all (7) ─► anomaly
   │                                     8. severity and reasons from simple rules
   ▼                                    10. stored in PostgreSQL, published to Kafka
normal minute (stored, nothing else happens)
```

The code is in `backend/detection/`; the service itself is `service.py`.

## 1. Reading the logs

The detection service reads `logs.raw` as the consumer group `detection-group`, independently of ingestion, so storing logs and detecting anomalies never wait for each other. It checks only what it needs (timestamp, service, level, message) and skips lines with a timestamp more than 5 minutes in the future: such a timestamp is wrong, and it would otherwise make the service think time had jumped ahead.

## 2. From message to template

Detection does not compare raw messages; it compares **templates**. First, masks replace values that always vary:

| Mask | Replaces | Example |
|---|---|---|
| `<IP>` | IP addresses | `10.0.3.17:8080` |
| `<UUID>` | UUIDs | `4f0c9e2a-…` |
| `<HEX>` | hexadecimal numbers | `0x7ffd` |
| `<PATH>` | paths with two or more parts | `/api/checkout` |
| `<ID>` | identifiers mixing letters and digits | `u6601`, `txn_c9731bc4b8` |
| `<NUM>` | numbers | `482913`, `1840` |

Then **Drain** groups messages of the same shape into one template. Two messages belong together when at least 90% of their words match, so messages that differ in one real word, such as *succeeded* and *failed*, stay separate.

```text
Payment txn_c9731bc4b8 processed for order 482913: amount 1499.00 INR
        ↓
Payment <ID> processed for order <NUM>: amount <NUM> INR
```

Drain's templates are saved with the model. The live service starts with exactly the templates of training, so template numbers mean the same thing in training and live. A message that fits none of the 31 known templates becomes a new template, which the model counts as **unseen** and the reasons report as a **new message type**.

## 3. One-minute windows

Each line is added to the window of its service and its minute. A window collects:

- the number of lines, errors (`ERROR`, `FATAL`) and warnings (`WARN`),
- how often each template appeared,
- the latencies of the lines that carry one,
- up to 10 example lines, errors first, so that an anomaly can show the lines that matter.

When a minute is closed, every known service gets a window for it, including services that wrote nothing. An empty window is how a crashed service becomes visible.

## 4. What the model sees

Each window becomes 38 numbers:

| Numbers | What they are |
|---|---|
| 31 | how often each known template appeared |
| 1 | how many lines matched no known template ("unseen") |
| 1 | the number of lines |
| 2 | the share of errors and of warnings |
| 2 | the average and the 95th-percentile latency |
| 1 | the number of different new templates |

Counts are log-scaled (`log(1 + count)`). A template that appears 1,000 times a minute should not drown out one that appears 5 times; with log scaling a change from 5 to 50 matters as much as one from 100 to 1,000. This choice was tested: log-scaled counts gave better results on the live data than raw counts.

## 5. The model: PCA in plain words

The model is a **PCA (principal component analysis) detector**. It never sees a failure during training; it only learns what normal minutes look like.

1. **Learn the normal shape.** From normal minutes, PCA finds the few directions in which normal minutes differ from each other. For example, in a busier minute all request templates rise together; in a quieter minute they all fall together. The directions that explain 95% of the normal variation form the *normal space*.
2. **Explain a new minute.** A new minute is projected onto the normal space: "how close can normal behaviour come to this minute?"
3. **Score what is left.** The part that normal behaviour cannot explain is the **score** (the squared distance from the normal space).

A busy but healthy minute is explained almost completely: all counts are higher, in the usual proportions, so its score is low. A minute in which 30% of payments fail is not: the error share and the error templates rise in a way no normal minute ever showed, so a large part of it is left over and its score is high.

Before PCA, every number is scaled with the mean and spread seen in training, so that numbers of different sizes (a count of 1,200 lines and an error share of 0.003) are compared fairly.

**Training data:** three runs of two hours of normal traffic (different random seeds), 1,785 windows, 357 per service. **One model for all five services:** the windows' own numbers tell the services apart.

**Why PCA:** six configurations were compared on live data: PCA or One-Class SVM, raw or log-scaled counts, one model for all services or one per service. One global PCA model with log-scaled counts was best on every measure. With raw counts, PCA missed the silent service; One-Class SVM found as much but raised false alarms in 15% of quiet minutes; separate models per service gave no gain. Before that, the methods were compared on two public log datasets, HDFS and BGL ([research results](../research/research-plan.md)).

## 6. Threshold and score

The **threshold** is the 99.9th percentile of the training scores: only about 1 in 1,000 normal training windows lies above it (for `live-pca 1.1.0`, 0.11% of the training windows). No labelled failures are needed to choose it.

The raw scores have no natural scale, so the dashboard shows a score from 0 to 1:

- below the threshold: `0.5 × score / threshold` (0 to 0.5),
- above it: `1 − 0.5 / (1 + log10(score / threshold))`.

The score is 0.5 at the threshold, 0.75 at ten times the threshold and 0.83 at a hundred times. The logarithm keeps differences between strong anomalies visible; an earlier formula gave every real fault the same 1.0.

## 7. The "no logs" rule

If a service writes **nothing** in a minute while other services are logging, the minute is an anomaly regardless of the model's score: `no logs (normally ~805 per minute)`, CRITICAL. A silent service is the clearest sign of a crash, and this rule makes sure it is never missed.

If **no** service writes anything (traffic stopped, or the generator is not running), the minute is idle: stored, but not an anomaly. The detection service says so once (`no logs from any service since …`).

## 8. Severity and reasons

The model says *whether* a minute is unusual. Simple, fixed rules then say *how serious* it is and *why*, by comparing the window with the service's normal values from training (its **baseline**):

| Signal | MEDIUM | HIGH | CRITICAL |
|---|---|---|---|
| Error rate | 1% or more | 5% or more | 20% or more |
| Log volume compared with normal | | 50% or less | 10% or less, or no logs |
| p95 latency compared with normal | 1.5 times | 3 times | |
| New message types | any | | |

The severity is that of the strongest signal; all signals found become the reasons, strongest first. If the model flagged the minute but no signal crosses a limit, the anomaly is **LOW** with the reason `unusual log pattern (no single signal above its limit)`.

The limits are design choices based on operational reasoning, not fitted to the test data, and were checked against the fault and fault-free runs. Keeping the model for *whether* and rules for *how serious* makes every anomaly explainable in words an operator understands.

The normal values of `live-pca 1.1.0`:

| Service | Lines per minute | p95 latency |
|---|---|---|
| api-gateway | 1,192 | 241 ms |
| auth-service | 805 | 62 ms |
| inventory-service | 932 | 38 ms |
| order-service | 483 | 59 ms |
| payment-service | 241 | 270 ms |

## 9. When a minute is judged

A minute is judged **5 seconds after it ends** (the grace period), so that lines that arrive a little late still count. When the service is up to date with Kafka, "now" is the clock. When it is catching up on a backlog (after a restart, or after the computer slept), it follows the time of the lines it has read, partition by partition, so that every minute is judged only once all its lines have been read.

Some minutes are not judged at all, because they would look like faults without being one:

- **The first minute after the service starts:** it only saw part of it.
- **A minute in which all traffic started or stopped:** half a minute of traffic looks like a volume drop on every service. One service going quiet while the others continue is still judged.
- **Any minute while the service does not have all partitions of `logs.raw`:** another detection service is running in the same group, and services on the other partitions would look silent. Detection warns and waits.

## 10. Storing and publishing

Every judged window is stored in the table `detection_windows`, and every anomaly in `anomalies` with its score, severity, reasons and example lines. Anomalies are then published to the Kafka topic `anomalies.detected`, from where the alerting service and the dashboard's live feed take them.

The lines of a minute are marked as processed in Kafka (committed) only after the minute has been stored. If the service stops in between, it reads those lines again after a restart. Storing the same window twice does no harm, so nothing is lost and nothing is counted twice.

## How long until an anomaly appears

Detection works on whole minutes, so the time from a fault's start to its anomaly is:

> **the rest of the minute in which the fault starts + about 6 seconds**, plus one more minute if the first, partly faulty minute is not yet unusual enough.

The 6 seconds are the 5-second grace period plus scoring and storing. Examples from the live runs:

| Fault starts at second | Rest of the minute | Anomaly after |
|---|---|---|
| :04.8 (silent service) | 55.2 s | 60.6 s |
| :30.4 (cascading failure) | 29.6 s | 35.5 s |
| :57 (new error type) | 3 s | 8–9 s |
| :57 (error burst) | 3 s | 68 s: 3 seconds of errors were not enough, so the next minute caught it |

On average, a fault that shows in its first minute is found about 36 seconds after it starts. The alert follows within a second, the Telegram message about a second after that.

## What it cannot do

- **A changed normal.** The model learned normal traffic at one load. At five or ten times that load it flags minutes as LOW (seen in the load test). A lasting change of normal behaviour needs a new model.
- **New, harmless messages.** A new kind of message that is perfectly fine, for example after a software update, is still a new message type (MEDIUM) until the model is retrained.
- **Very short faults.** A fault of a few seconds at the edge of a minute can disappear in the minute's totals.
- **Faults finer than a minute.** Detection cannot be faster than the minute it waits for. Shorter or overlapping windows would halve the waiting time, at the cost of noisier windows.
- **Everything stopping at once** is treated as "no traffic", not as a fault.

## How the model was checked

`train.py` tested `live-pca 1.1.0` before it was registered: all 7 injected faults of a fault run were found, and a fresh fault-free hour produced 1 false alarm in 295 windows, graded LOW. The live tests of Phase 10 confirmed this with real-time runs. See the [introduction](introduction.md#how-well-it-works) for the numbers.

## Next

- [Architecture](architecture.md): how the parts fit together, and why.
- [Getting started](getting-started.md) to try it.