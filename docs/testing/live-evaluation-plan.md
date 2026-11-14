# Live Evaluation Plan (Phase 10)
## Cloud Log Anomaly Detection for Proactive Fault Management

Version 1.0 (Day 39). Answers **RQ3** (research-plan.md): *how well does the chosen detector find injected faults
in the simulated system, at service and incident level, per fault type, and how quickly?* RQ4 (latency and
throughput) is measured separately (Days 41–42).

---

## 1. Why repeated runs

The evaluation so far rests on one recorded fault run (all_faults.jsonl, replayed), one fault-free hour, and single
real-time runs per scenario. One run cannot show variance, and the research plan lists "one random seed per
experiment; variance not measured" as a threat to validity. This plan repeats the full fault run five times in
real time with different seeds and scenario orders, so every number is reported as mean ± standard deviation.

## 2. What is run

| Run | Seed | Scenario order (5 min normal traffic before the first and after each scenario) | Length |
|---|---|---|---|
| r1 | 101 | error_burst → latency_spike → new_error → silent_service → cascading_failure | 41 min |
| r2 | 102 | latency_spike → new_error → silent_service → cascading_failure → error_burst | 41 min |
| r3 | 103 | new_error → silent_service → cascading_failure → error_burst → latency_spike | 41 min |
| r4 | 104 | silent_service → cascading_failure → error_burst → latency_spike → new_error | 41 min |
| r5 | 105 | cascading_failure → error_burst → latency_spike → new_error → silent_service | 41 min |
| n1 | 201 | none (fault-free) | 60 min |

- The order rotates, so each scenario appears once in every position: an effect of position (e.g. the first fault
  after warm-up) cannot favour one scenario.
- Seeds 101–105 and 201 differ from the training runs (1–3) and the earlier evaluation runs (4, 42).
- Real time, published to Kafka, through the running detection and alerting services: the same path as production
  use, including the watermark, grace period and alert grouping.
- Model: `live-pca 1.1.0` (unchanged during the evaluation; no tuning between runs).
- Total about 4 h 40 min, unattended: `.\scripts\run_live_evaluation.ps1`. A subset (`-Runs 1,2,3`) is the minimum
  if time is short; the report then states n = 3.

## 3. Definitions

| Term | Definition |
|---|---|
| Window | One service, one minute (the detection unit) |
| Faulty window | Overlaps a ground-truth fault of the **same** service |
| Full window | Lies completely inside a fault (edge windows are only partly faulty) |
| Incident | One injected scenario; period = first fault start to last fault end (cascading_failure has three faults) |
| Near an incident | Overlaps an incident period extended by 2 min on both sides, on **any** service |
| Quiet window | Not near any incident; a flag here is a false alarm |
| Idle window | No logs and not flagged; ignored (as in the API statistics, Day 34) |
| Detection delay | `detected_at` of the first anomaly minus fault (or incident) start, wall clock |
| Alert delay | `first_seen_at` of the first alert opened from 2 min before to 4 min after the incident, minus its start |
| Evaluated period | 4 min before the first fault to 4 min after the last one, inside the run's own warm-up and final gap |

Flags on other services during an incident (e.g. the gateway returning 502 when inventory fails) are real
reactions, not detector errors. They count against the strict, service-level precision and are reported
separately as "precision counting reactions near incidents".

## 4. Metrics

Per run (scripts/live_eval.py run), then mean ± standard deviation, min and max over runs (summary):

| Group | Metric |
|---|---|
| Incidents | detected / injected; detection delay; alert delay; worst severity; anomalies per incident; alerts per incident; alerts notified (Telegram); time from incident end to auto-resolve |
| Windows | precision, recall, F1 (service level); recall on full windows; precision counting reactions near incidents |
| False alarms | flags in quiet windows (rate, severities, reasons); alerts opened outside incidents; fault-free hour: false-alarm rate and alerts |
| Per scenario | detected in how many runs; delays; anomalies; alerts; worst severities |

Expected values from earlier measurements, stated before the runs so the results can confirm or contradict them:
all 7 fault records detected; detection about 30–35 s after a fault starts (end of the current minute plus 5 s
grace); silent_service slower (about 70 s in the replay); false alarms below 1 % of quiet windows, graded LOW.

## 5. Procedure

1. `.\scripts\start.ps1 up`; terminals for the API, ingestion, detection and alerting (README, Running the pipeline).
   Detection and alerting must run **before** the first run starts.
2. Laptop on power, sleep off for the duration: `powercfg /change standby-timeout-ac 0`
   (afterwards back to e.g. `powercfg /change standby-timeout-ac 30`).
3. Nothing else may send logs during the evaluation (no other generator).
4. `.\scripts\run_live_evaluation.ps1` in a fifth terminal (venv active). It runs everything, waits 7 minutes,
   evaluates every run and writes `experiments/results/live/summary.md`.
5. Telegram receives the real alert messages of every run (about two alerts per incident); this is expected.
6. Commit `experiments/results/live/` and the ground-truth files' names in the devlog.

If a run is interrupted, re-run only that run (`-Runs 3 -SkipNormal`); results are saved per run and the summary
always uses every saved run.

## 6. Threats to validity (for the report)

- The generator and its faults are simulated; results show behaviour on this system, not production performance.
- Five runs give a rough variance estimate, not a tight confidence interval.
- The detector was chosen on earlier runs of the same generator (different seeds), which favours it.
- Detection delay depends on the 60-s window and 5-s grace: faults starting early in a minute wait longer.