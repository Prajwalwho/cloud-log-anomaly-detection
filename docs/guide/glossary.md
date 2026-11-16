# Glossary

Every term used in this guide, in one short line each. Where a term needs more than a line, the link leads to the full explanation.

| Term | Meaning |
|---|---|
| **Acknowledge** | An operator marks an alert as *being looked at*; their name is stored. See [Alerts and Telegram](alerts-and-telegram.md#the-life-of-an-alert) |
| **Active alert** | An alert that is open or acknowledged, not yet resolved |
| **Active model** | The one registered model the detection service uses. See [Model](concepts.md#model) |
| **Alert** | Anomalies of one service that belong together, as one thing to act on. See [Alert](concepts.md#alert) |
| **Anomaly** | A minute of one service that the model judged unusual. See [Anomaly](concepts.md#anomaly) |
| **Anomaly score** | How unusual a minute is, from 0 to 1; above 0.5 is an anomaly. See [Score and threshold](concepts.md#anomaly-score-and-threshold) |
| **API** | The backend program that serves the data to the dashboard. See [API reference](api-reference.md) |
| **At-least-once** | Every message is processed at least once; after a crash some are processed twice, none are lost |
| **Baseline** | A service's normal numbers (lines per minute, p95 latency), learned in training and used in the reasons. See [Baseline](concepts.md#baseline) |
| **BGL** | A public dataset of supercomputer logs (Blue Gene/L), used in the research phase |
| **Cascading failure** | One fault causing others in turn; also the name of one fault scenario |
| **Commit** | A consumer telling Kafka "I have processed everything up to here". See [Consumer group and offset](concepts.md#consumer-group-and-offset) |
| **Consumer group** | A name under which a program reads a Kafka topic; Kafka remembers the group's position |
| **Consumer lag** | How many messages a consumer group is behind the newest one. See [Operations](operations.md#is-a-service-keeping-up-consumer-lag) |
| **Contract** | The agreed format of a log event and of the messages between the services. See [data contracts](../design/contracts.md) |
| **Dashboard** | The web pages at <http://localhost:5173>, named *Observatory*. See [Using the dashboard](using-the-dashboard.md) |
| **Dead-letter topic** | `logs.deadletter`: where ingestion puts events that break the contract, with the reason |
| **Drain** | The algorithm that finds the templates of log messages |
| **Elasticsearch** | The store that keeps every log line searchable |
| **Error rate** | The share of a minute's lines at level `ERROR` or `FATAL` |
| **Escalate** | An alert's severity rising, for example from HIGH to CRITICAL |
| **Event time** | The time written in a log line, as opposed to the time it arrived. Windows are by event time |
| **False alarm (false positive)** | A flagged minute in which nothing was wrong |
| **Fault scenario** | A fault the log generator can inject, for example `error_burst`. See [Configuration](configuration.md#log-generator-1) |
| **Feature** | One of the 38 numbers that describe a window for the model. See [How detection works](how-detection-works.md#4-what-the-model-sees) |
| **Grace period** | The 5 seconds detection waits after a minute ends, for late lines. See [Grace period and watermark](concepts.md#grace-period-and-watermark) |
| **Ground truth** | The generator's record of which fault happened when. See [Ground truth](concepts.md#ground-truth) |
| **HDFS** | A public dataset of Hadoop file-system logs, used in the research phase |
| **Idempotent** | Doing it twice has the same effect as doing it once; this makes repeats after a crash harmless |
| **Incident** | One fault as it happened, often causing several anomalies and alerts. See [Incident](concepts.md#incident) |
| **Index** | A collection of documents in Elasticsearch; one per day, `logs-YYYY.MM.DD` |
| **Ingestion** | The service that validates log events and stores them in Elasticsearch |
| **Kafka** | The message system that carries all data between the parts. See [Kafka topic](concepts.md#kafka-topic) |
| **Key** | The value that decides a message's partition; for log events, the service name |
| **Live feed** | The WebSocket that pushes new anomalies and alerts to the dashboard. See [Live feed](concepts.md#live-feed) |
| **Log event** | One log line as structured JSON. See [Log event](concepts.md#log-event) |
| **Log generator** | The program that simulates the five services and injects faults |
| **Log-scaled counts** | Counts replaced by log(1 + count), so that a jump from 0 to 10 matters as much as one from 100 to 1,000 |
| **Masking** | Replacing numbers, ids, addresses and paths in a message by placeholders such as `<NUM>`, before Drain |
| **Model package** | A trained model saved with its Drain state and metadata, in `models/trained/<name>-<version>/` |
| **Model registry** | The PostgreSQL table of all registered models |
| **New message type** | A message that matches none of the templates learned in training |
| **Normal space** | The few directions in which normal minutes differ from each other, found by PCA |
| **Notification** | A Telegram message about an alert. See [Notification](concepts.md#notification) |
| **Offset** | A message's position in a partition |
| **p95 latency** | The time within which 95% of a minute's calls finished |
| **Partition** | A part of a Kafka topic; `logs.raw` has three. See [Partition and key](concepts.md#partition-and-key) |
| **PCA** | Principal component analysis: the model that learns what normal minutes look like. See [How detection works](how-detection-works.md#5-the-model-pca-in-plain-words) |
| **PostgreSQL** | The database of judged minutes, anomalies, alerts and models |
| **Reason** | A plain-language explanation of an anomaly, for example `error rate 14.7%`. See [Reason](concepts.md#reason) |
| **Recall** | The share of injected faults (or faulty minutes) that were found |
| **Resolve** | Close an alert: automatically after 5 quiet minutes, or by an operator |
| **Service** | One of the five simulated programs that write logs. See [Service](concepts.md#service) |
| **Severity** | LOW, MEDIUM, HIGH or CRITICAL: how serious an anomaly or alert is. See [Severity](concepts.md#severity) |
| **SPE** | Squared prediction error: PCA's raw score, the part of a minute that normal behaviour cannot explain |
| **Template** | A message with its variable parts replaced, for example `Payment failed for order <NUM>`. See [Template](concepts.md#template) |
| **Threshold** | The raw score above which a minute is an anomaly: the 99.9th percentile of the training minutes |
| **Topic** | A named stream of messages in Kafka |
| **Trace ID** | The id shared by every line of one user request |
| **Verdict** | An operator's *Real problem* or *False alarm* on an anomaly |
| **Watermark** | Detection's idea of "now", used to decide which minutes are complete. See [Grace period and watermark](concepts.md#grace-period-and-watermark) |
| **WebSocket** | A connection over which the server can send messages to the browser at any time |
| **Window** | Everything one service logged in one minute. See [Window](concepts.md#window) |

## Next

- [FAQ](faq.md): common questions and their answers.