# System Architecture
## Cloud Log Anomaly Detection for Proactive Fault Management

### 1. System Overview

The proposed system is a real-time cloud log monitoring and anomaly detection platform designed to identify abnormal patterns in application and infrastructure logs.

The system collects logs from multiple sources, processes them through a streaming pipeline, extracts meaningful features, and applies machine learning algorithms to identify anomalous behavior.

Detected anomalies are stored, assigned severity levels, and displayed through a centralized monitoring dashboard.

### 2. Architectural Objectives

- Centralized collection of logs from multiple services.
- Real-time log processing and anomaly detection.
- Identification of unusual log patterns without requiring extensive labeled datasets.
- Severity-based anomaly classification.
- Historical log search and anomaly analysis.
- Real-time dashboard updates and alert management.
- Measurable performance and scalability evaluation.

### 3. Technology Stack

| Layer | Technology |
|---|---|
| Programming language | Python |
| Backend API | FastAPI |
| Frontend | React, TypeScript, Vite |
| Streaming | Apache Kafka |
| Log storage and search | Elasticsearch |
| Structured database | PostgreSQL |
| Machine learning | Scikit-learn |
| Containerization | Docker, Docker Compose |
| Monitoring | Prometheus, Grafana |
| Real-time communication | WebSocket |

### 4. System Components

#### 4.1 Log Sources
Generate or collect logs from simulated cloud applications, microservices, and infrastructure components.

#### 4.2 Log Collection
Collect logs using a custom log generator initially. Fluent Bit or OpenTelemetry can be integrated as additional collection mechanisms.

#### 4.3 Streaming Layer
Apache Kafka provides a distributed event-streaming layer.

Responsibilities:
- Receive incoming log events.
- Buffer events during processing.
- Support asynchronous producer-consumer communication.
- Decouple log generation from anomaly detection.

#### 4.4 Log Processing and Preprocessing
The Python ingestion service consumes log events and performs:

- Log parsing.
- Timestamp normalization.
- Missing-value handling.
- Duplicate removal where appropriate.
- Template extraction.
- Feature extraction and vectorization.

#### 4.5 Anomaly Detection Engine

The detection engine evaluates processed logs using multiple approaches.

**Primary model: Isolation Forest**

Identifies unusual observations by isolating them through random partitioning.

**Comparison model: One-Class SVM**

Learns a boundary around normal observations and identifies observations outside that boundary.

**Baseline: Statistical Detection**

Uses statistical thresholds and deviations to establish a baseline for comparison.

The models will be evaluated experimentally rather than assuming one algorithm is universally superior.

#### 4.6 Severity Scoring

Detected anomalies receive severity levels based on anomaly scores and configurable rules.

Proposed categories:

- Low
- Medium
- High
- Critical

Severity is an operational classification and is separate from the ML anomaly score.

#### 4.7 Storage Layer

**Elasticsearch**
- Stores searchable log events.
- Supports filtering and historical log analysis.
- Enables efficient log retrieval.

**PostgreSQL**
- Stores detected anomalies.
- Stores alert records and statuses.
- Maintains structured application metadata.

#### 4.8 Backend API

FastAPI provides the application interface.

Responsibilities:
- Receive and retrieve logs.
- Retrieve anomaly records.
- Manage alerts.
- Provide statistical summaries.
- Deliver real-time updates through WebSockets.

#### 4.9 Frontend Dashboard

The React dashboard provides:

- System overview.
- Total log volume.
- Anomaly statistics.
- Severity distribution.
- Historical anomaly trends.
- Searchable log records.
- Alert management.

#### 4.10 Monitoring Infrastructure

Prometheus and Grafana will monitor application and infrastructure performance, including processing throughput, resource utilization, and service health.

### 5. End-to-End Data Flow

1. Applications or the log generator produce log events.
2. The collection component forwards events to Kafka.
3. The ingestion consumer retrieves events.
4. The preprocessing pipeline cleans and normalizes logs.
5. Feature extraction converts logs into model-compatible representations.
6. The anomaly detection engine calculates anomaly scores.
7. The severity component assigns operational severity.
8. Log events are indexed in Elasticsearch.
9. Anomaly and alert records are stored in PostgreSQL.
10. FastAPI exposes the processed information.
11. The React dashboard displays current and historical results.
12. WebSockets deliver real-time dashboard updates.

### 6. Machine Learning Methodology

The initial implementation will use unsupervised and statistical approaches.

The experimental workflow:

1. Dataset selection.
2. Data exploration.
3. Log preprocessing.
4. Feature engineering.
5. Model training.
6. Anomaly scoring.
7. Threshold selection.
8. Model evaluation.
9. Comparative analysis.

Potential benchmark datasets include HDFS, BGL, OpenStack, and Thunderbird from LogHub.

### 7. Research Evaluation Metrics

The system will be evaluated using:

- Precision
- Recall
- F1-score
- False positive rate
- Detection latency
- Processing throughput
- CPU and memory utilization
- Scalability under increasing log volume

Where labeled datasets are available, detection results will be compared against ground-truth labels.

### 8. Proactive Fault Management

The system aims to support proactive fault management by identifying unusual log behavior before it develops into a service failure.

However, anomaly detection does not automatically establish fault prediction.

Predictive claims will require experiments demonstrating that detected patterns consistently precede independently verified failures.

### 9. Reliability and Scalability

The architecture will support:

- Asynchronous log ingestion.
- Independent processing components.
- Containerized deployment.
- Configurable processing thresholds.
- Persistent log and anomaly storage.
- Performance testing under different workloads.

### 10. Future Enhancements

- Distributed log collection.
- Advanced log template mining.
- Deep learning-based anomaly detection.
- Root-cause analysis.
- Temporal anomaly correlation.
- Failure prediction using historical event sequences.
- Multi-service dependency analysis.

### 11. Conclusion

The proposed architecture combines streaming infrastructure, machine learning, searchable log storage, structured anomaly management, and real-time visualization into a unified cloud log monitoring platform.

The design supports experimental evaluation of anomaly detection accuracy, processing performance, and operational usefulness.
