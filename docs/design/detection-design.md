# Detection Service Design
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 1.3 (Phase 6). Every decision below refers to the evidence it is based on.

---

## 1. Responsibilities

The detection service (backend/detection/service.py) consumes `logs.raw` in its own consumer group
(`detection-group`), builds 60-second windows per service, extracts features, scores each window, stores every
window and every anomaly in PostgreSQL, and (Day 25) publishes anomalies to `anomalies.detected`.

## 2. Windowing (implemented: windowing.py, watermark.py, offsets.py)

| Decision | Choice | Evidence |
|---|---|---|
| Window | Tumbling 60 s per service, aligned to whole minutes (UTC) | Architecture decision (Day 0); live faults last 2–3 min |
| Empty windows | Created for every known service even with no logs | silent_service produces 0 logs (Day 7); verified in replay (Day 21) |
| Watermark | Per-partition: minimum latest event time over partitions that still have unread data (judged against Kafka's high-water mark); if one of them has delivered nothing yet, no window closes; when all partitions are caught up, wall-clock time | Day 24: a global "latest event time" watermark dropped 13,835 events as late; "minimum over partitions seen" dropped 23,353; this rule: 0 late in a 68,345-event replay |
| Closing | A window closes when the watermark minus 5 s grace passes its end | Pipeline delay ≤ ~1.1 s (Day 11) |
| Late events | Counted and dropped, never added to a wrong window | The late counter exposed the watermark bug (Day 24) |
| Offsets | Committed only for events whose windows are closed and stored | A restart replays open windows instead of losing them |
| Start-up | The first (partial) window after start is not scored | Avoids a false low-volume anomaly |
| No traffic | If all services are empty in a window, windows are stored without anomalies and one warning is printed | Generator stopped / pipeline idle is not an outage of each service |
| Edge windows | Partially faulty windows evaluated separately | Faults start mid-minute (Days 7, 21) |

## 3. Features (implemented: features/extractor.py)

| Group | Features | Evidence |
|---|---|---|
| Templates | Count per template, plus "unseen" count. Drain threshold 0.9 with SERVICE_LOG_MASKS | Without the identifier mask the service logs produced 36,758 templates instead of 31 (Day 21) |
| Volume and rates | log_count, error_rate, warn_rate | Error bursts (Day 7); FATAL rule strongest on BGL (Day 18) |
| Latency | mean and p95 latency | latency_spike creates no new templates or errors (Days 7, 21) |
| Novelty | number of distinct templates not in the vocabulary | new_error fault (Days 7, 21); drift (Day 18) |
| Scaling | log(1 + count) for counts | Live comparison (Day 22): log counts beat raw counts |

## 4. Model and thresholds (implemented: live_model.py, package.py, registry.py)

| Decision | Choice | Evidence |
|---|---|---|
| Model | One global PCA model for all services (95% variance) | Day 22: best of 6 configurations; per-service models gave no gain |
| Not used | One-Class SVM (15% quiet false alarms on Day 22), Isolation Forest, z-score | Days 16, 19, 22 |
| Standardisation | min_std 0.01 | Live features include rates (normal error rate ~0.003) |
| Training data | 3 runs x 2 h of normal traffic (seeds 1–3), 1,785 windows | 5 minutes of warmup missed rare normal templates (Day 21) |
| Threshold | Label-free: 99.9th percentile of training-window scores | Generalised better than validation-tuned under drift (Days 15, 18) |
| Packaging | Detector + Drain state + metadata; versions immutable; Drain state loaded read-only | Template ids must match feature columns (Day 23) |
| Active model | Read from model_registry at start-up | Day 23 |
| Measured | live-pca 1.0.0: fault run recall 0.952, 7/7 incidents; fault-free run 0.34% false alarm windows | Day 23 |

## 5. Score normalisation and severity (implemented: live_model.py, scoring/severity.py)

- spread = threshold − median(training scores).
  raw ≤ threshold: s = 0.5 · exp((raw − threshold) / spread); raw > threshold: s = 1 − 0.5 · exp(−(raw − threshold) / spread).
  s is in [0, 1], monotonic, 0.5 at the threshold; clamped so that s > 0.5 exactly when raw > threshold.
- Severity bands: LOW > 0.5, MEDIUM > 0.6, HIGH > 0.75, CRITICAL > 0.9.
- Rule override: a known service with zero logs (while others have traffic) is flagged and at least HIGH.
- Known issue (Day 24): real faults saturate the score at ~1.0 (nearly all CRITICAL, e.g. 4% and 52% gateway
  error rates both CRITICAL). Severity calibration is Day 25.

## 6. Template stability

- The Drain miner state learned during training is saved and loaded at startup, so template ids in live
  windows match the model's feature columns. New templates found live go to the "unseen" count.

## 7. Known limitations
- Drift: new normal message types raise false positives; BGL showed a step change (Day 20). Continuous
  retraining or marking new templates as normal is future work.
- Service-level precision is limited by dependent services reacting during incidents (gateway 502/503,
  order and payment going quiet when auth is down); incident-level evaluation in Phase 10.