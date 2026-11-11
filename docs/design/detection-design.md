# Detection Service Design
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 1.2 (Phase 6). Every decision below refers to the evidence it is based on.

---

## 1. Responsibilities

The detection service consumes `logs.raw` in its own consumer group (`detection-group`), builds 60-second
windows per service, extracts features, scores each window, stores every window and every anomaly in
PostgreSQL, and publishes anomalies to `anomalies.detected`.

## 2. Windowing (implemented: backend/detection/windowing.py, pipeline.py)

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
| Templates | Count per template, plus "unseen" count. Drain threshold 0.9 with SERVICE_LOG_MASKS | Without the identifier mask the service logs produced 36,758 templates instead of 31 (Day 21) |
| Volume and rates | log_count, error_rate, warn_rate | Error bursts (Day 7); FATAL rule strongest on BGL (Day 18) |
| Latency | mean and p95 latency | latency_spike creates no new templates or errors (Days 7, 21) |
| Novelty | number of distinct templates not in the vocabulary | new_error fault (Days 7, 21); drift (Day 18) |
| Scaling | **log(1 + count) for counts** | Live comparison (Day 22): log counts beat raw counts (B vs A, D vs C) |

## 4. Model and thresholds (implemented: backend/detection/live_model.py)

| Decision | Choice | Evidence |
|---|---|---|
| Model | **One global PCA model for all services** (95% variance) | Day 22: best of 6 configurations (recall 0.952, F1 0.714, 7/7 incidents, 0 quiet false alarms); per-service models gave no gain |
| Not used | One-Class SVM (15% quiet false alarms on Day 22), Isolation Forest, z-score | Days 16, 19, 22 |
| Standardisation | min_std 0.01 | Live features include rates (normal error rate ~0.003); offline value 0.5 would hide them |
| Training data | 3 runs x 2 h of normal traffic (seeds 1–3), 1,785 windows | Unsupervised setting; 5 minutes of warmup missed rare normal templates (Day 21) |
| Threshold | Label-free: 99.9th percentile of training-window scores | Generalised better than validation-tuned under drift (Days 15, 18) |

## 5. Score normalisation and severity

- spread = threshold − median(training scores).
  raw ≤ threshold: s = 0.5 · exp((raw − threshold) / spread); raw > threshold: s = 1 − 0.5 · exp(−(raw − threshold) / spread).
  s is in [0, 1], monotonic, exactly 0.5 at the threshold, and valid for any score scale (Day 22: the earlier
  formula raw / (raw + threshold) produced values above 1 for negative One-Class SVM scores).
- `is_anomaly` = raw > threshold (equivalently s > 0.5). Threshold and spread are stored with the model.
- Severity from s (bands to be calibrated on live data): LOW 0.5–0.6, MEDIUM 0.6–0.75, HIGH 0.75–0.9,
  CRITICAL > 0.9.
- Rule override: a service with zero logs in a window where it normally logs is at least HIGH
  (PCA alone caught the silent service in 2 of 3 windows on Day 22).

## 6. Template stability

- The Drain miner state learned during training is saved and loaded at startup, so template ids in live
  windows match the model's feature columns. New templates found live go to the "unseen" count.

## 7. Known limitations
- Drift: new normal message types raise false positives; BGL showed a step change (Day 20). Continuous
  retraining or marking new templates as normal is future work.
- Service-level precision is limited by dependent services reacting during incidents (gateway 502s);
  incident-level evaluation in Phase 10.
- Day 22 evaluation had only 20 quiet windows; the false alarm rate is measured on a separate fault-free run.