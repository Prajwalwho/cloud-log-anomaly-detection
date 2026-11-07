# System Architecture
## Cloud Log Anomaly Detection for Proactive Fault Management

### 1. System Overview

The proposed system is a real-time cloud log monitoring and anomaly detection platform designed to identify abnormal patterns in application and infrastructure logs.

The system collects logs from multiple sources, processes them through a distributed streaming pipeline, extracts meaningful features, and applies machine learning algorithms to identify anomalous behavior.

Detected anomalies are assigned severity levels, stored for historical analysis, and displayed through a centralized monitoring dashboard.

The architecture separates log ingestion, anomaly detection, storage, and API services to support independent processing, scalability, and fault isolation.

### 2. Architectural Objectives

- Centralized collection of logs from multiple services.
- Real-time log processing and anomaly detection.
- Identification of unusual log patterns without requiring extensive labeled datasets.
- Independent ingestion and detection services.
- Severity-based anomaly classification.
- Historical log search and anomaly analysis.
- Real-time dashboard updates and alert management.
- Measurable performance and scalability evaluation.

### 3. Technology Stack

| Layer | Technology |
|---|---|
| Programming language | Python 3.12 |
| Backend API | FastAPI |
| Frontend | React, TypeScript, Vite |
| Streaming | Apache Kafka |
| Kafka client libraries | confluent-kafka, aiokafka |
| Log template mining | Drain (drain3) |
| Log storage and search | Elasticsearch 8 |
| Structured database | PostgreSQL |
| Database access | SQLAlchemy, Psycopg |
| Machine learning | Scikit-learn |
| Model serialization | Joblib |
| Data processing | NumPy, Pandas |
| Containerization | Docker, Docker Compose |
| Monitoring | Prometheus, Grafana |
| Real-time communication | WebSockets |

### 4. System Components

#### 4.1 Log Sources

Generate or collect logs from simulated cloud applications, microservices, and infrastructure components.

The initial implementation will simulate multiple services, including:

- Authentication service
- Payment service
- Order service
- Inventory service
- API gateway

Each service will generate realistic log events with timestamps, log levels, messages, service identifiers, and other relevant metadata.

#### 4.2 Log Collection

Collect logs using a custom log generator initially.

Fluent Bit or OpenTelemetry can be integrated as additional collection mechanisms in future enhancements.

#### 4.3 Streaming Layer

Apache Kafka provides the distributed event-streaming layer.

Responsibilities:

- Receive incoming log events.
- Buffer events during processing.
- Support asynchronous producer-consumer communication.
- Decouple log generation from ingestion and anomaly detection.
- Allow independent consumer groups to process the same events.

The system will initially use a single-broker Kafka deployment in KRaft mode through Docker Compose.

#### 4.4 Ingestion Service

The Python ingestion service independently consumes messages from the `logs.raw` Kafka topic.

Its responsibilities include:

- Consuming incoming log events.
- Validating messages against the canonical log schema using Pydantic.
- Sending invalid messages to the `logs.deadletter` topic.
- Indexing valid log events into Elasticsearch.
- Handling retries and Elasticsearch failures.
- Managing Kafka offsets to support reliable processing.

The ingestion service is responsible for message validation and log storage.

It does not perform Drain-based log template extraction or machine learning inference.

#### 4.5 Detection Service

The detection service independently consumes the same `logs.raw` Kafka topic using a separate Kafka consumer group.

Its responsibilities include:

- Consuming incoming log events.
- Parsing and normalizing log messages.
- Extracting log templates using Drain3.
- Grouping events into detection windows.
- Extracting numerical and statistical features.
- Applying trained anomaly detection models.
- Calculating anomaly scores.
- Assigning severity levels.
- Persisting detected anomalies in PostgreSQL.
- Publishing detected anomalies to Kafka.

The detection service operates independently of the ingestion service. Both services receive their own copies of events through separate Kafka consumer groups.

#### 4.6 Log Preprocessing and Feature Extraction

The detection service performs log preprocessing before applying machine learning algorithms.

The preprocessing pipeline includes:

- Timestamp normalization.
- Log message cleaning.
- Log template extraction using Drain3.
- Handling missing or malformed feature values.
- Event counting.
- Template frequency calculation.
- Error-rate calculation.
- Latency statistics.
- Feature vector generation.

Drain3 converts variable log messages into structured log templates that can be analyzed more effectively.

The extracted features are used to represent the behavior of individual services over time.

#### 4.7 Anomaly Detection Engine

The detection engine evaluates processed log windows using multiple approaches.

**Primary model: Isolation Forest**

Identifies unusual observations by isolating them through random partitioning.

**Comparison model: One-Class SVM**

Learns a boundary around normal observations and identifies observations outside that boundary.

**Baseline: Statistical Detection**

Uses statistical thresholds and deviations to establish a baseline for comparison.

The models will be evaluated experimentally rather than assuming one algorithm is universally superior.

The initial approach will focus on unsupervised anomaly detection, where models learn normal behavior without requiring extensive labeled training data.

#### 4.8 Severity Scoring

Detected anomalies receive severity levels based on anomaly scores and configurable rules.

Proposed categories:

- Low
- Medium
- High
- Critical

Severity is an operational classification and is separate from the machine learning anomaly score.

The severity component will convert model outputs into understandable classifications for dashboard visualization and alert generation.

#### 4.9 Storage Layer

**Elasticsearch**

- Stores searchable log events.
- Supports filtering and historical log analysis.
- Enables efficient log retrieval.
- Stores log metadata and template information where applicable.

**PostgreSQL**

- Stores detected anomalies.
- Stores alert records and statuses.
- Maintains structured application metadata.
- Maintains model registry information.
- Stores detection window metadata and model evaluation information where required.

The Elasticsearch document identifier will be referenced by anomaly records in PostgreSQL when an anomaly is associated with a particular log document.

#### 4.10 Backend API

FastAPI provides the application interface.

Responsibilities:

- Retrieve logs from Elasticsearch.
- Retrieve anomaly records from PostgreSQL.
- Manage alerts.
- Provide statistical summaries.
- Expose service and model information.
- Deliver real-time updates through WebSockets.
- Support communication between the dashboard and backend services.

The API service will use asynchronous communication where appropriate for real-time updates.

#### 4.11 Frontend Dashboard

The React dashboard provides:

- System overview.
- Total log volume.
- Anomaly statistics.
- Severity distribution.
- Historical anomaly trends.
- Searchable log records.
- Anomaly details.
- Alert management.
- Real-time anomaly updates.

The dashboard will communicate with FastAPI through HTTP APIs and WebSockets.

#### 4.12 Monitoring Infrastructure

Prometheus and Grafana will monitor application and infrastructure performance.

Monitoring metrics will include:

- Log ingestion throughput.
- Detection processing throughput.
- Detection latency.
- Kafka consumer lag.
- API response time.
- CPU utilization.
- Memory utilization.
- Service health.

### 5. End-to-End Data Flow

The system follows this processing flow:

1. Applications or the log generator produce log events.
2. The log generator publishes events to the Kafka topic `logs.raw`.
3. The ingestion service consumes `logs.raw` using its own consumer group.
4. The detection service independently consumes `logs.raw` using a different consumer group.
5. The ingestion service validates incoming messages against the canonical log schema.
6. Invalid messages are published to `logs.deadletter`.
7. Valid messages are indexed into Elasticsearch.
8. The detection service parses and normalizes log messages.
9. Drain3 extracts log templates from incoming messages.
10. Events are grouped into detection windows.
11. Feature extraction converts each window into a model-compatible representation.
12. The anomaly detection engine calculates anomaly scores.
13. The severity component assigns operational severity.
14. Anomaly records are stored in PostgreSQL.
15. Newly detected anomalies are published to `anomalies.detected`.
16. FastAPI retrieves logs, anomalies, alerts, and statistical information.
17. The React dashboard displays current and historical results.
18. WebSockets deliver real-time anomaly updates to the dashboard.

### 6. Key Design Decisions

#### 6.1 Detection as an Independent Service

Ingestion and detection are separate services.

Both consume the `logs.raw` Kafka topic using different consumer groups, so each receives every log independently.

The ingestion service focuses on validation and log storage, while the detection service focuses on preprocessing, feature extraction, and anomaly detection.

This separation provides several advantages:

- A failure or slowdown in detection does not directly stop log ingestion and storage.
- Ingestion and detection can be scaled independently.
- Machine learning workloads do not need to run inside the ingestion service.
- Each service has a clearly defined responsibility.
- The architecture supports independent development and testing.

#### 6.2 Kafka Topics

The initial system will use three Kafka topics.

| Topic | Producer | Consumer(s) | Purpose |
|---|---|---|---|
| `logs.raw` | Log generator / applications | Ingestion, Detection | All incoming log events |
| `logs.deadletter` | Ingestion | Manual inspection | Messages that fail schema validation |
| `anomalies.detected` | Detection | API / Alerting | Newly detected anomalies |

The ingestion and detection services will use separate consumer groups when consuming `logs.raw`.

This ensures that both services receive every published log event independently.

#### 6.3 Unit of Detection

**Live system**

Logs are grouped into fixed 60-second windows per service.

Each window is converted into a feature vector containing information such as:

- Log template counts.
- Error rate.
- Warning count.
- Event frequency.
- Latency statistics.

The detection model evaluates each service window and calculates an anomaly score.

**Benchmark datasets**

Different datasets require different grouping strategies.

- HDFS: Sessions grouped by HDFS block IDs.
- BGL: Sliding windows over sequential log events.

The grouping strategy will follow the structure and labeling methodology of each benchmark dataset.

Window-level detection was chosen over line-level detection because many operational failures appear as changes in patterns across multiple log events rather than in a single log line.

#### 6.4 Responsibility for Parsing

The ingestion service only validates incoming messages against the canonical log schema.

Log cleaning, normalization, and template extraction using Drain3 are performed by the detection service's preprocessing module.

This separation avoids duplicating log parsing responsibilities and keeps the ingestion pipeline lightweight.

### 7. Machine Learning Methodology

The initial implementation will use unsupervised and statistical approaches.

The experimental workflow:

1. Dataset selection.
2. Data exploration.
3. Log preprocessing.
4. Log template extraction.
5. Feature engineering.
6. Training and testing data preparation.
7. Model training.
8. Anomaly scoring.
9. Threshold selection.
10. Model evaluation.
11. Comparative analysis.

Potential benchmark datasets include HDFS, BGL, OpenStack, and Thunderbird from LogHub.

The initial model comparison will include:

- Statistical baseline.
- Isolation Forest.
- One-Class SVM.

Models will be evaluated using appropriate dataset-specific grouping and ground-truth labels where available.

### 8. Research Evaluation Metrics

The system will be evaluated using:

- Precision.
- Recall.
- F1-score.
- False positive rate.
- Detection latency.
- Processing throughput.
- CPU and memory utilization.
- Scalability under increasing log volume.

Where labeled datasets are available, detection results will be compared against ground-truth labels.

Live evaluation will additionally use controlled fault-injection scenarios with recorded ground-truth information.

### 9. Proactive Fault Management

The system aims to support proactive fault management by identifying unusual log behavior before it develops into a service failure.

However, anomaly detection does not automatically establish fault prediction.

Predictive claims will require experiments demonstrating that detected patterns consistently precede independently verified failures.

The initial project will focus on detecting abnormal behavior and generating timely alerts. Future predictive capabilities will depend on experimental evidence.

### 10. Reliability and Scalability

The architecture will support:

- Asynchronous log ingestion.
- Independent ingestion and detection services.
- Separate Kafka consumer groups.
- Configurable processing thresholds.
- Kafka message buffering.
- Dead-letter handling for invalid messages.
- Retry mechanisms for storage failures.
- Persistent log and anomaly storage.
- Containerized deployment.
- Performance testing under different workloads.

The system will be evaluated under increasing log volumes to identify throughput limits, processing delays, and resource requirements.

### 11. Future Enhancements

- Distributed log collection.
- Advanced log template mining.
- Deep learning-based anomaly detection.
- Root-cause analysis.
- Temporal anomaly correlation.
- Failure prediction using historical event sequences.
- Multi-service dependency analysis.
- Automated alert notification through email or Telegram.
- Distributed deployment and horizontal scaling.

### 12. Conclusion

The proposed architecture combines distributed event streaming, independent log ingestion and anomaly detection services, machine learning, searchable log storage, structured anomaly management, and real-time visualization into a unified cloud log monitoring platform.

The design supports experimental evaluation of anomaly detection accuracy, processing performance, scalability, and operational usefulness.

By separating ingestion from detection and using window-based analysis, the system provides a structured foundation for identifying unusual cloud application behavior and supporting proactive fault management.