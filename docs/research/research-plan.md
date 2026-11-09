# Research Plan
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 1.0 (start of Phase 5)

---

## 1. Problem

Cloud systems produce large volumes of logs. Failures often show up first as changes in log
patterns (more errors, slower requests, new kinds of messages, missing logs), but these changes are
hard to spot manually. This project studies whether unsupervised and statistical methods can detect
such changes reliably, and how they perform inside a real-time pipeline.

## 2. Research Questions

**RQ1 — Model comparison (offline).**
How do a statistical baseline, PCA, Isolation Forest and One-Class SVM compare in precision, recall
and F1 on standard labelled log datasets (HDFS, BGL)?

**RQ2 — Features.**
How much does the feature representation matter (event-count vectors vs. TF-IDF weighting, and for the
live system, adding error rate, latency and new-template counts)?

**RQ3 — Live detection.**
How well does the best model detect injected faults in the simulated system: at service level and
incident level, for each fault type, and how quickly (time to detect)?

**RQ4 — System performance.**
What latency and throughput does the pipeline achieve, and what limits them?
(Initial measurement, Day 11: median 570 ms from log creation to storage; ~3,300 events/s on backlog.)

## 3. Datasets

| Dataset | Use | Unit of detection | Labels |
|---|---|---|---|
| HDFS v1 (LogHub) | RQ1, RQ2 | Session = HDFS block id | Per block (normal/anomaly) |
| BGL (LogHub) | RQ1, RQ2 | Sliding time window | Per line, aggregated per window |
| Simulated microservices (own generator) | RQ3, RQ4 | 60-second window per service | Ground-truth fault intervals |

Raw benchmark files are not stored in the repository (data/raw/ is ignored by Git).

## 4. Method (offline)

1. Parse raw logs into templates with Drain (our own parsing, not the pre-processed files).
2. Group events into sessions (HDFS) or windows (BGL).
3. Build feature vectors (event counts per template; variants for RQ2).
4. Split by time: earlier data for training, later data for testing. No random split (it leaks future
   information).
5. Train unsupervised models on normal training data only.
6. Choose thresholds without using test labels.
7. Report precision, recall, F1, false positive rate and ROC-AUC on the test set.

## 5. Evaluation (live)

- A window is faulty if it overlaps a ground-truth fault interval.
- Service level and incident level evaluation (faults affect dependent services too).
- Partially faulty edge windows reported separately.
- Time to detect per fault type.

## 6. Threats to validity (to discuss in the report)

- Benchmark labels come from rules or operators and may contain errors.
- The simulated system is simpler than real production systems; results on it show behaviour,
  not production performance.
- Thresholds tuned on one dataset may not transfer to another.

## 7. References

Reference details must be checked against the original publication before they go into the report.

| Reference | Status |
|---|---|
| Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics. ISSRE 2023. https://github.com/logpai/loghub | Title, venue and repository confirmed; check author list |
| S. He, J. Zhu, P. He, M. R. Lyu. Experience Report: System Log Analysis for Anomaly Detection. ISSRE 2016. | Confirmed |
| M. Du, F. Li, G. Zheng, V. Srikumar. DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning. ACM CCS 2017. | Confirmed |
| Drain log parsing paper (P. He et al., ICWS 2017) | To verify before citing |
| Original HDFS log source (W. Xu et al., SOSP 2009) | To verify before citing |