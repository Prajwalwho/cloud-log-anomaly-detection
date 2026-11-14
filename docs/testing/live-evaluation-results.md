# Live Evaluation Results (Phase 10, RQ3)
## Cloud Log Anomaly Detection for Proactive Fault Management

Day 40. Protocol: [live-evaluation-plan.md](live-evaluation-plan.md). Raw results: `experiments/results/live/`
(`r1.json`, `r2.json`, `r3.json`, `n1.json`, `summary.md`). Model `live-pca 1.1.0`, unchanged throughout.

---

## 1. What was run

| Run | Ground truth (run id) | Faults start at second … of a minute | Notes |
|---|---|---|---|
| r1 | run-20261114-191709 | :09 (51 s of the fault in its first minute) | clean |
| r2 | run-20261114-195809 | :09 (51 s) | clean |
| r3 | run-20261114-213457 | :57 (3 s) | repeated after the laptop slept during the first attempt |
| n1 | fault-free, 22:17–23:14 UTC | — | 285 windows |

Three of the planned five fault runs were completed (n = 3). Two earlier attempts were discarded, not scored: the
laptop went to sleep (lid closed; later, screen-off on a Modern Standby laptop) and the generator stopped for 25 and
22 minutes. The runner script detected both (`generator failed`) and stopped instead of producing results.

Over the night the services processed 819,535 log events (0 invalid, 0 late), created 145 anomalies and 52 alerts;
all 52 alerts resolved automatically; 112 Telegram messages were sent, 0 failed.

## 2. Summary (mean ± standard deviation over r1–r3)

| Metric | Value |
|---|---|
| Incidents detected | **15 / 15** (100 %) |
| Detection delay (first anomaly after fault start) | 52 s ± 7 (range 8–69 s; explained in §3) |
| Alert delay | same as detection delay (the alert opens in the same second as the first anomaly) |
| Recall, minutes fully inside a fault | **100 %** |
| Recall, all faulty minutes | 84.5 % ± 7.5 (the misses are edge minutes, §4) |
| Precision, strict (only the faulty service counts) | 54.5 % ± 0.6 (reactions of other services, §5) |
| Precision counting reactions near incidents | **100 %** |
| False alarms in quiet minutes | **0** of 30 |
| Fault-free hour | 1 false alarm in 285 windows (**0.35 %**), LOW, **0 alerts** |
| Alerts per incident | 2.5 ± 0.1 (one per affected service) |
| Alerts outside incidents | 0 |

Per scenario (all detected 3/3):

| Scenario | Delay | Anomalies | Alerts | Worst severity |
|---|---|---|---|---|
| error_burst | 60 s ± 7 | 4.7 | 1.7 | critical ×3 |
| latency_spike | 60 s ± 7 | 3.3 | 1.3 | high ×3 |
| new_error | 40 s ± 28 | 5.7 | 2.0 | high ×3 |
| silent_service | 40 s ± 27 | 8.7 | 3.7 | critical ×3 |
| cascading_failure | 60 s ± 7 | 11.0 | 4.0 | critical ×3 |

## 3. Detection delay: what it consists of

Detection works on whole minutes. A minute is judged when it has closed plus the 5-second grace period. The delay
from a fault's start to the anomaly is therefore

> **time left in the minute in which the fault starts + 5 s grace + processing**, plus one more minute if that
> first, partly faulty minute is not unusual enough to be flagged.

The measurements fit this exactly:

| Run | Fault starts at | Rest of the minute | First minute flagged? | Measured delay | Remainder (grace + processing) |
|---|---|---|---|---|---|
| r1 | :09 | 51 s | yes, all scenarios | 56.6–56.8 s | ≈ 5.7 s |
| r2 | :09 | 51 s | yes, all scenarios | 55.5–55.9 s | ≈ 4.7 s |
| r3 | :57 | 3 s | new_error, silent_service (gateway): yes | 7.9–9.1 s | ≈ 5 s |
| r3 | :57 | 3 s | error_burst, latency_spike, cascading: no | 68.0–68.7 s | 63 s + ≈ 5.5 s |

Findings:
- **The system itself adds about 5 seconds** after a minute ends: the grace period, plus well under a second for
  scoring, storing, publishing and opening the alert (alert delay equals detection delay in every incident).
- The rest is waiting for the minute to end. With fault start times spread evenly over a minute, the expected delay
  is about 30 s + 5 s for faults that show in the first partial minute.
- A new error type or a silent service shows within **3 seconds of fault** in a minute (r3: 8–9 s). An error-rate
  or latency change needs more of the minute: with 3 s it was not flagged, with 51 s it always was.
- The predicted "30–35 s" was not confirmed as a mean: all faults of a run start at the same second of the minute
  (scenarios are spaced in whole minutes), so three runs sampled only two positions (:09 twice, :57 once).
  The reported mean of 52 s describes these positions, not a typical fault. This is a limitation of the protocol
  (§7), not of the detector.

## 4. Recall: which minutes are missed

Every minute lying completely inside a fault was flagged (100 %). The misses are edge minutes that contain only a
few seconds of a fault:
- r1/r2: the last minute of a 2-minute fault contains 9 s of it (fault 12:09–14:09 → minute 14:00 has 9 s); it was
  usually not flagged (error_burst 2/3, silent_service 2/3, cascading payment 2/3).
- r3: the first minute contains 3 s; gradual faults were flagged one minute later (§3).

For an operator these misses do not matter: the incident is detected and alerted in the neighbouring minute.

## 5. Precision: why the strict value is 55 % and the incident value 100 %

Every flag lay within 2 minutes of an incident (incident precision 100 %), but almost half were on a service other
than the injected one. These are real effects of the fault, as the generator models them, not detector errors:
- **api-gateway** reports the downstream failure (502/503 to the caller) during error_burst, new_error and
  silent_service; it was often the first service flagged.
- **silent_service**: when auth-service stops, the gateway rejects requests that need authentication, so
  order-service and payment-service receive far less traffic (log volume 1–10 % of normal) and are flagged
  correctly as volume drops.
- **cascading_failure**: all four involved services are faulty by design.

A strict window-level score counts these as false positives. The incident-level view, and the operator's view
(one alert per affected service, §6), is the more meaningful measure here.

## 6. Alerts and notifications

- One alert per affected service: 1–2 for single-service faults, 3–4 for silent_service and cascading_failure.
  Anomalies were grouped (2.5 alerts for 6.7 anomalies per incident).
- HIGH and CRITICAL alerts were sent to Telegram (opened, escalated, resolved); MEDIUM ones were not (r2: gateway
  during latency_spike, order-service during cascading_failure).
- Every alert resolved automatically, 5.1–6.4 minutes after the incident ended (median ≈ 6 min: the last anomaly
  often comes from the edge minute after the fault, then 5 quiet minutes, then up to 30 s until the next check); one
  stayed open 9.7 min because a later anomaly of the same service extended it.
- LOW anomalies (3 during the night) never opened an alert.

## 7. Comparison with the expectations written before the runs

| Expectation (plan §4) | Result | |
|---|---|---|
| All 7 fault records detected | all incidents 15/15; every fault record had flagged minutes | confirmed |
| Detection about 30–35 s after a fault starts | 8–69 s; ≈ 5 s after the minute ends (§3) | refined: the mean depends on the fault's position in the minute |
| silent_service slower (~70 s in the replay) | 9 s (gateway) to 68 s (auth's own minute) | partly: the gateway reports it earlier than auth's own silence |
| False alarms below 1 % of quiet windows, graded LOW | 0/30 quiet minutes; 1/285 (0.35 %) LOW in the fault-free hour, no alert | confirmed |

## 8. Threats to validity

- n = 3 fault runs (5 planned) and only two fault positions within the minute; standard deviations are rough.
- 30 quiet minutes in the fault runs; the false-alarm rate rests mainly on the fault-free hour (285 windows).
- Simulated services and faults; the detector was chosen on earlier runs of the same generator (other seeds).
- Telegram counts depend on network availability (no failures occurred).

## 9. Consequences

1. **Protocol**: give each scenario a random start offset within the minute (generator option), so the delay is
   measured over all positions; then repeat with 5 runs.
2. **Detector**: shorter or overlapping windows (e.g. 60-s windows every 30 s, or 30-s windows) would roughly
   halve the waiting part of the delay; to be weighed against noisier windows and more storage (Day 43).
3. **Reporting**: present detection delay as "≈ 5 s after the minute closes; 8–69 s after fault start depending on
   its position", and precision at both levels.
4. **Robustness**: a long pause (computer asleep) made the ingestion service crash on its next commit. Fixed on
   Day 40 for all three consumers (devlog day-40).