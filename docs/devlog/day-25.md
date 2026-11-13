# Day 25 — Severity calibration and publishing anomalies

## Done
- live_model.py: log-ratio score normalisation for PCA (default); per-service baselines (median log count,
  median p95 latency) learned in fit; older packages still load.
- scoring/severity.py: rule-based severity with reasons (error rate, log volume vs normal, p95 latency vs
  normal, new message types).
- scoring/judge.py: shared judging (model flag, no-logs rule, severity) for the live service and train.py.
- store.py: reasons stored in the anomaly summary.
- publisher.py: anomalies published to anomalies.detected after storing.
- service.py: uses judge and publisher; prints each anomaly with its reasons.
- train.py: evaluation with the same judging rules; reports severities and reasons; baselines in metadata.
- tests: test_severity_offsets.py (8), test_live_model.py (12), test_publisher.py (1); unit total 123.
- Model live-pca 1.1.0 trained, registered and active (id 5).
- docs/design/detection-design.md v1.4.

## Problem
- Day 24: nearly every anomaly was CRITICAL with score 1.000 (e.g. gateway at 4.3% and 52% error rate).
  Two causes: the exponential normalisation saturated, and severity was derived from the score.

## Decision
- The model decides WHETHER a window is anomalous; explainable rules grade HOW SEVERE, against the service's
  own baseline. Limits are design choices, checked (not fitted) against the fault and fault-free runs.

## Calibration check (train.py, all_faults run seed 42 and fault-free run seed 4)

| Fault | Severities (first window = partial edge) | Reason in first full window |
|---|---|---|
| error_burst (payment) | HIGH, CRITICAL, CRITICAL | error rate 32.8% |
| latency_spike (order) | HIGH, HIGH, HIGH | p95 latency 334 ms (5.6x normal) |
| new_error (inventory) | MEDIUM, HIGH, HIGH | error rate 11.2%; 1 new message type |
| silent_service (auth) | CRITICAL, HIGH | no logs (normally ~805 per minute) |
| cascading order | MEDIUM x4 | p95 latency 174 ms (2.9x normal) |
| cascading payment | HIGH, CRITICAL, CRITICAL | error rate 28.4% |
| cascading inventory | HIGH, HIGH | |

- Detection unchanged: recall 0.952, 7/7 incidents, 0/20 quiet false alarms.
- Fault-free run: 1 false alarm in 295 windows, graded LOW (score 0.561, "unusual log pattern").
  A HIGH/CRITICAL notification rule would not have alerted on it.

## Service run (fast, seed 11, all scenarios, run-20261113-110333)
- 33 anomalies; all 5 incidents detected within their first minute; no anomaly in any normal minute.
- Severity follows impact: gateway 3.8% errors MEDIUM, 8.7% HIGH; payment 39.4% CRITICAL.
- Silent auth: auth "no logs" CRITICAL; order and payment "log volume 1–3% of normal" CRITICAL; gateway
  23–56% errors and 2 new message types (503 / connection refused never seen in normal traffic).
- Cascading failure visible in stages and escalating: order slow (MEDIUM) 11:21 -> payment errors 11:22 ->
  inventory errors 11:23 -> payment CRITICAL 11:23.
- Scores spread 0.54–0.91 instead of 1.000.
- Kafka anomalies.detected messages verified (all fields, UTC "Z" timestamps, reasons, 10 sample event ids).

## Observations
- Score and severity measure different things (order 0.814 MEDIUM vs payment 0.599 HIGH): unusual is not the
  same as harmful.
- Display bug: "p95 latency 175 ms (3.0x normal)" graded MEDIUM because the ratio is just under 3 and the text
  rounds to one decimal. Fix (two decimals) on Day 26.
- detected_at precedes window_start in fast-mode runs (timestamps up to 23 min in the future): time-to-detect
  must be measured on real-time runs only.
- Robustness gap: the service reads logs.raw directly and accepts far-future timestamps, which could advance
  the watermark. Guard on Day 26.

## Problems faced
- First Kafka read found no messages: it ran before the service had published (TimeoutException = no message
  within the timeout, not an error).