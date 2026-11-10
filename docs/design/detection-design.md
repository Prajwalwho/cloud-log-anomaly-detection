# Detection Service Design
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 1.1 (Phase 6). Every decision below refers to the evidence it is based on.

---

## 1. Responsibilities

The detection service consumes `logs.raw` in its own consumer group (`detection-group`), builds 60-second
windows per service, extracts features, scores each window, stores every window and every anomaly in
PostgreSQL, and publishes anomalies to `anomalies.detected`.

## 2. Windowing (implemented: backend/detection/windowing.py)

| Decision | Choice | Evidence |
|---|---|---|
| Window | Tumbling 60 s per service, aligned to whole minutes (UTC) | Architecture decision (Day 0); live faults last 2–3 min |
| Empty windows | Created for every known service even with no logs | silent_service produces 0 logs (Day 7); verified in replay (Day 21) |
| Closing | A window closes when the watermark (latest time minus 5 s grace) passes its end | Pipeline delay ≤ ~1.1 s (Day 11) |
| Late events | Counted and dropped, never added to a wrong window | Replay: 0 late events (Day 21) |
| Edge windows | Partially faulty windows evaluated separately | Faults start mid-minute (Days 7, 21) |

## 3. Features (implemented: backend/detection/features/extractor.py)

| Group | Features | Evidence |
|---|---|---|
| Templates | Count per template, plus "unseen" count. Drain threshold 0.9 with SERVICE_LOG_MASKS (default masks plus alphanumeric identifiers such as user and transaction ids) | Counts carry the signal on HDFS (Days 13–16); without the identifier mask the service logs produced 36,758 templates instead of 31 (Day 21) |
| Volume and rates | log_count, error_rate, warn_rate | Error bursts (Day 7); FATAL rule strongest on BGL (Day 18) |
| Latency | mean and p95 latency | latency_spike creates no new templates or errors (Days 7, 21) |
| Novelty | number of distinct templates not in the vocabulary | new_error fault (Days 7, 21); drift (Day 18) |

Raw and log-scaled counts are both evaluated on live data (RQ2: the best representation depends on the data).

## 4. Model and thresholds

| Decision | Choice | Evidence |
|---|---|---|
| Primary model | PCA | Near-best on HDFS (F1 0.965, PR-AUC 0.995), best label-free ML on BGL with log features (0.486); fast |
| Comparison model | One-Class SVM (distinct vectors weighted by frequency) | Best ranking on HDFS (PR-AUC 0.999) |
| Not used | Isolation Forest, z-score as main detectors | IF blind to constant features; z-score unstable across representations (Days 16, 19) |
| Training data | Hours of normal traffic from the generator (several seeds, no faults) | Unsupervised setting; 5 minutes of warmup missed rare normal templates (Day 21) |
| Threshold | Label-free: 99.9th percentile of training-window scores | Generalised better than validation-tuned under drift (Days 15, 18) |

## 5. Score normalisation and severity

- Normalised score s = raw / (raw + threshold): 0–1, monotonic, and exactly 0.5 at the threshold.
  `is_anomaly` = raw > threshold (equivalently s > 0.5). The raw threshold is stored in `model_registry`.
- Severity from s (bands to be calibrated on live data):
  LOW 0.5–0.6, MEDIUM 0.6–0.75, HIGH 0.75–0.9, CRITICAL > 0.9.
- Rule override: a service with zero logs in a window where it normally logs is at least HIGH.

## 6. Template stability

- The Drain miner state learned during training is saved and loaded at startup, so template ids in live
  windows match the model's feature columns. New templates found live go to the "unseen" count.

## 7. Known limitations (from the offline research)
- Drift: new normal message types raise false positives; BGL showed a step change (Day 20). Continuous
  retraining or marking new templates as normal is future work.
- One split and one seed per offline experiment.