# Detection Service Design
## Cloud Log Anomaly Detection for Proactive Fault Management

Version: 1.5 (end of Phase 6). Every decision below refers to the evidence it is based on.

---

## 1. Responsibilities

The detection service (backend/detection/service.py) consumes `logs.raw` in its own consumer group
(`detection-group`), builds 60-second windows per service, extracts features, scores each window, grades
severity, stores every window and every anomaly in PostgreSQL, and publishes anomalies to `anomalies.detected`.
It runs independently of ingestion (`ingestion-group`), which stores the same events in Elasticsearch.

## 2. Windowing (implemented: windowing.py, watermark.py, offsets.py)

| Decision | Choice | Evidence |
|---|---|---|
| Window | Tumbling 60 s per service, aligned to whole minutes (UTC) | Architecture decision (Day 0); live faults last 2–3 min |
| Empty windows | Created for every known service even with no logs | silent_service produces 0 logs (Day 7); verified in replay (Day 21) |
| Watermark | Per-partition: minimum latest event time over partitions that still have unread data (judged against Kafka's high-water mark); if one of them has delivered nothing yet, no window closes; when all partitions are caught up, the later of wall-clock time and latest event time | Day 24: a global "latest event time" watermark dropped 13,835 events as late; "minimum over partitions seen" dropped 23,353; this rule: 0 late in a 68,345-event replay and in the Day 26 live run |
| Future timestamps | Events more than 5 min in the future are counted and skipped (same rule as ingestion); --allow-future for fast-mode test replays | Day 26: a 2030 event was skipped by detection and dead-lettered by ingestion; late stayed 0 |
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
| Novelty | number of distinct templates not in the vocabulary | new_error fault; gateway 503 messages during silent auth (Day 25) |
| Scaling | log(1 + count) for counts | Live comparison (Day 22): log counts beat raw counts |

## 4. Model and thresholds (implemented: live_model.py, package.py, registry.py)

| Decision | Choice | Evidence |
|---|---|---|
| Model | One global PCA model for all services (95% variance) | Day 22: best of 6 configurations; per-service models gave no gain |
| Not used | One-Class SVM (15% quiet false alarms on Day 22), Isolation Forest, z-score | Days 16, 19, 22 |
| Standardisation | min_std 0.01 | Live features include rates (normal error rate ~0.003) |
| Training data | 3 runs x 2 h of normal traffic (seeds 1–3), 1,785 windows | 5 minutes of warmup missed rare normal templates (Day 21) |
| Threshold | Label-free: 99.9th percentile of training-window scores | Generalised better than validation-tuned under drift (Days 15, 18) |
| Baselines | Per service: median log count and median p95 latency of training windows | Severity compares a window with its own service's normal behaviour (Day 25) |
| Packaging | Detector + Drain state + metadata; versions immutable; Drain state loaded read-only | Template ids must match feature columns (Day 23) |
| Active model | Read from model_registry at start-up; current: live-pca 1.1.0 (id 5) | Days 23, 25 |
| Measured offline | live-pca 1.1.0: fault run recall 0.952, 7/7 incidents, 0/20 quiet false alarms; fault-free run 1 false alarm in 295 windows (0.34%), graded LOW | Day 25 |
| Measured live | Real-time run with ingestion and detection: 5/5 incidents detected 32–33 s after fault start; 0 late events | Day 26 |

## 5. Score normalisation and severity (implemented: live_model.py, scoring/severity.py, scoring/judge.py)

- Score (how unusual): log-ratio normalisation for PCA.
  raw ≤ threshold: s = 0.5 · raw / threshold; raw > threshold: s = 1 − 0.5 / (1 + log10(raw / threshold)).
  0.5 at the threshold, 0.75 at 10x, 0.83 at 100x; clamped so that s > 0.5 exactly when raw > threshold.
  (The exponential formula saturated at 1.0 for every real fault, Day 24; it is kept for One-Class SVM,
  whose scores can be negative.)
- Flag (whether): the model flags the window, or the service has no logs while other services have traffic.
- Severity (how harmful): rules on what the window shows compared with the service's baseline; the highest
  signal wins, LOW if none crosses a limit. Every anomaly stores its reasons (ratios with two decimals).

| Signal | MEDIUM | HIGH | CRITICAL |
|---|---|---|---|
| Error rate | ≥ 1% | ≥ 5% | ≥ 20% |
| Log volume vs normal | | ≤ 50% | ≤ 10%, or no logs |
| p95 latency vs normal | ≥ 1.5x | ≥ 3x | |
| New message types | any | | |

- The limits are design choices based on operational reasoning, checked (not fitted) on Day 25: error burst
  and silent service CRITICAL, latency spike HIGH, new error HIGH, cascading failure escalating MEDIUM ->
  HIGH -> CRITICAL; the only fault-free false alarm was LOW.
- Score and severity can differ (e.g. score 0.81 MEDIUM vs 0.60 HIGH): unusual is not the same as harmful.

## 6. Publishing (implemented: publisher.py)

- New anomalies are published to `anomalies.detected` (key = service, acks=all, idempotent) after they are
  stored. PostgreSQL is the source of truth; failed publishes are counted and reported (Day 26: 23/23 published).
- Message: schema_version, anomaly_id, detected_at, service, window_start, window_end, anomaly_score, severity,
  model {id, name, version}, summary (incl. reasons), sample_event_ids.

## 7. Template stability

- The Drain miner state learned during training is saved and loaded at startup, so template ids in live
  windows match the model's feature columns. New templates found live go to the "unseen" count.

## 8. Known limitations and open points (Phase 10)
- Drift: new normal message types raise false positives; BGL showed a step change (Day 20). Continuous
  retraining or marking new templates as normal is future work.
- Service-level precision is limited by dependent services reacting during incidents (gateway 502/503,
  order and payment going quiet when auth is down); incident-level evaluation in Phase 10.
- Partial volume drops are not always flagged: during silent auth (Day 26), a window with 34% of normal volume
  was not flagged by the model, and severity rules only grade flagged windows. Candidate: a volume rule that
  can also flag (e.g. below 50% of baseline), to be tested against fault-free runs before adoption.
- detected_at is meaningful for time-to-detect only in real-time runs (fast-mode runs have future timestamps).
- Live evaluation runs need quiet periods (default 5-minute gaps); with 2-minute gaps no window is quiet.