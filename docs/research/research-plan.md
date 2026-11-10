# Research Plan and Results
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 2.0 (end of Phase 5). Offline research complete for RQ1 and RQ2; RQ3 and RQ4 in Phase 10.

---

## 1. Problem

Cloud systems produce large volumes of logs. Failures often show up first as changes in log patterns
(more errors, slower requests, new kinds of messages, missing logs), but these changes are hard to spot
manually. This project studies whether unsupervised and statistical methods can detect such changes
reliably, and how they perform inside a real-time pipeline.

## 2. Research Questions

**RQ1 — Model comparison (offline).** How do a statistical baseline, PCA, Isolation Forest and One-Class SVM
compare with simple baselines on standard labelled log datasets (HDFS, BGL)?

**RQ2 — Features.** How much does the feature representation matter (raw vs log-scaled counts, level
features), and does retraining on more recent data help?

**RQ3 — Live detection (Phase 10).** How well does the chosen detector find injected faults in the simulated
system, at service and incident level, per fault type, and how quickly?

**RQ4 — System performance (Phase 10).** What latency and throughput does the pipeline achieve?
(Measured so far: median 570 ms from log creation to storage; ~3,300 events/s on backlog.)

## 3. Datasets

| Dataset | Lines | Unit of detection | Units | Anomalous | Labels |
|---|---|---|---|---|---|
| HDFS v1 (LogHub) | 11,175,629 | Block id (session) | 575,061 | 16,838 (2.93%) | Per block |
| BGL (LogHub) | 4,747,963 | 15-minute window | 8,590 non-empty | 858 (9.99%) | Per line (alert = anomaly) |
| Simulated microservices | generated | 60-s window per service | — | — | Ground-truth fault intervals |

## 4. Method (offline)

1. Parse raw logs with Drain (similarity threshold 0.9, depth 4) after masking variable values
   (block ids, IPs, hex values, paths, numbers; BGL additionally dates, MAC addresses, node and I/O-node names).
   Threshold and masks were chosen by inspecting templates on the first 200,000 lines.
2. Group events into sessions (HDFS) or 15-minute windows (BGL; chosen from a comparison of 1 min–6 h).
3. Count vectors with a vocabulary learned from training normal data only, plus one "unseen" column.
4. Chronological split 60 / 20 / 20 (train / validation / test). No random split.
5. Unsupervised models trained on normal training data only.
6. Two thresholds: label-free (99.9th percentile of normal training scores) and validation-tuned (best F1).
7. Precision, recall, F1 (anomaly class), false positives, PR-AUC, ROC-AUC on the test set.
8. Baselines: line-count rule, unseen-template rule, exact lookup table of normal count vectors, and
   (BGL) number of FATAL lines.

## 5. Results

### RQ1 — test set

| Model | HDFS F1 (label-free) | HDFS PR-AUC | BGL F1 (label-free) | BGL F1 (val-tuned) | BGL PR-AUC |
|---|---|---|---|---|---|
| Lookup table (baseline) | 0.978 | 0.956 | 0.210 | 0.210 | 0.117 |
| FATAL count (baseline, BGL) | — | — | 0.000 | 0.840 | 0.726 |
| z-score | 0.002 | 0.756 | 0.426 | 0.245 | 0.456 |
| PCA | 0.965 | 0.995 | 0.333 | 0.279 | 0.463 |
| Isolation Forest | 0.000 | 0.018 | 0.000 | 0.182 | 0.434 |
| One-Class SVM | 0.971 | 0.999 | 0.300 | 0.285 | 0.301 |

**Answer.** On HDFS, behaviour is stable and repetitive (207 distinct normal count vectors); PCA and
One-Class SVM nearly match the lookup table (F1 ≈ 0.97) and rank almost perfectly. On BGL, behaviour drifts
(73.7% of normal test windows contain message types unseen in training) and all novelty-based methods degrade
to F1 0.2–0.43, while a FATAL-count rule with a validation-tuned threshold reaches 0.84. Models using
relationships between counts (PCA, OCSVM) work where behaviour is stable; z-score (one feature at a time)
and Isolation Forest (cannot split on features constant in training) fail on HDFS for explained reasons.

### RQ2 — test set (F1 label-free / PR-AUC)

| Model | Dataset | Raw counts | Log counts | Log + levels | Retrain (train+val) |
|---|---|---|---|---|---|
| PCA | BGL | 0.333 / 0.463 | 0.481 / 0.514 | 0.486 / 0.539 | 0.439 / 0.536 |
| One-Class SVM | BGL | 0.300 / 0.301 | 0.442 / 0.533 | 0.468 / 0.527 | 0.368 / 0.529 |
| PCA | HDFS | 0.965 / 0.995 | 0.803 / 0.919 | — | 0.803 / 0.919 |
| One-Class SVM | HDFS | 0.971 / 0.999 | 0.956 / 0.958 | — | 0.956 / 0.958 |

**Answer.** Representation matters but there is no universally best choice: log scaling helps on BGL
(bursty, skewed counts) and hurts on HDFS (small exact counts carry the signal). Level features help slightly.
Retraining on one more month did not counter BGL's drift (unseen share 73.7% → 66.2%; F1 lower).

### Other measured findings
- Label-free thresholds generalised better than validation-tuned ones in several cases, because the anomaly
  mix drifts between validation and test.
- The maximum training score is unusable as a threshold (extreme normal outliers); a high percentile is robust.
- One-Class SVM training time grew super-linearly (64k → 334k blocks: 5.2x data, 73x time); training on
  distinct vectors weighted by frequency cut full-data training from 188 s to 2 s.

## 6. Evaluation plan (live, Phase 10)
- A window is faulty if it overlaps a ground-truth fault interval.
- Service-level and incident-level evaluation (faults affect dependent services too).
- Partially faulty edge windows reported separately; time to detect per fault type.
- Raw and log counts both evaluated (RQ2 showed the best choice depends on the data).

## 7. Threats to validity
- Benchmark labels come from rules or operators and may contain errors (see error analysis).
- One chronological split and one random seed per experiment; variance not measured.
- The simulated system is simpler than production systems; live results show behaviour, not production
  performance.
- Thresholds tuned on one period may not transfer to another (observed drift).

## 8. References

| Reference | Status |
|---|---|
| J. Zhu, S. He, P. He, J. Liu, M. R. Lyu. Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics. ISSRE 2023. https://github.com/logpai/loghub | Verified |
| A. J. Oliner, J. Stearley. What Supercomputers Say: A Study of Five System Logs. DSN 2007. (source of BGL) | Verified |
| S. He, J. Zhu, P. He, M. R. Lyu. Experience Report: System Log Analysis for Anomaly Detection. ISSRE 2016. | Verified |
| M. Du, F. Li, G. Zheng, V. Srikumar. DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning. ACM CCS 2017. | Verified |
| Z. Jiang, J. Liu, J. Huang, Y. Li, Y. Huo, J. Gu, Z. Chen, J. Zhu, M. R. Lyu. A Large-scale Evaluation for Log Parsing Techniques: How Far are We? ISSTA 2024. (Loghub-2.0; BGL template count used for comparison) | Verified |
| Drain log parsing paper (P. He et al., ICWS 2017) | To verify before citing |
| Original HDFS log source (W. Xu et al., SOSP 2009) | To verify before citing |