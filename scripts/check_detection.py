"""
Compare the anomalies stored by the running detection service with a generator ground-truth file.
First version of the Phase 10 evaluation; uses the active model's windows in PostgreSQL.

Reports:
- per fault record: overlapping windows, flagged windows, severities, and real time-to-detect
  (detected_at of the first anomaly minus fault start; meaningful for real-time runs only);
- per incident (scenario): detected or not, time-to-detect over all services;
- false alarms in quiet windows (no fault on any service within 2 minutes), with severity and reasons;
- service-level precision / recall (dependent services reacting during an incident count as false positives).

Usage (from the project root, stack running):
    python scripts/check_detection.py data/ground_truth/<run-id>.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.config import DetectionSettings  # noqa: E402
from backend.detection.pipeline import parse_timestamp  # noqa: E402
from backend.detection.registry import active_model  # noqa: E402

QUERY = """
SELECT s.name, w.window_start, w.window_end, w.log_count, w.is_anomaly,
       a.severity, a.detected_at, a.summary->'reasons'
FROM detection_windows w
JOIN services s ON s.id = w.service_id
LEFT JOIN anomalies a ON a.window_id = w.id
WHERE w.model_id = %s AND w.window_start >= %s AND w.window_end <= %s
ORDER BY w.window_start, s.name
"""
MARGIN = timedelta(minutes=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare stored anomalies with ground truth.")
    parser.add_argument("ground_truth", type=Path)
    args = parser.parse_args()

    faults = [json.loads(line) for line in args.ground_truth.open(encoding="utf-8")]
    for f in faults:
        f["start_dt"], f["end_dt"] = parse_timestamp(f["start"]), parse_timestamp(f["end"])
    begin = min(f["start_dt"] for f in faults) - timedelta(minutes=10)
    end = max(f["end_dt"] for f in faults) + timedelta(minutes=5)

    settings = DetectionSettings()
    model = active_model(settings.postgres_conninfo)
    if model is None:
        print("[FAIL] no active model")
        return 1
    with psycopg.connect(settings.postgres_conninfo) as conn:
        rows = conn.execute(QUERY, (model["id"], begin, end)).fetchall()
    if not rows:
        print(f"[FAIL] no stored windows for model {model['version']} between {begin:%H:%M} and {end:%H:%M} UTC. "
              "Was the detection service running during this run?")
        return 1
    windows = [dict(zip(("service", "start", "end", "logs", "flag", "severity", "detected_at", "reasons"), r))
               for r in rows]
    print(f"Model {model['name']} {model['version']}; {len(windows)} windows "
          f"({begin:%H:%M}–{end:%H:%M} UTC); {len(faults)} fault records\n")

    # ---- per fault record ----
    print(f"{'scenario':<18} {'service':<18} {'flagged':>8}  {'detect after':>12}  severities")
    for f in faults:
        hits = [w for w in windows if w["service"] == f["service"] and w["start"] < f["end_dt"] and w["end"] > f["start_dt"]]
        flagged = [w for w in hits if w["flag"]]
        ttd = f"{(flagged[0]['detected_at'] - f['start_dt']).total_seconds():.0f} s" if flagged else "-"
        print(f"{f['scenario']:<18} {f['service']:<18} {len(flagged):>3}/{len(hits):<4}  {ttd:>12}  "
              f"{[w['severity'] for w in flagged]}")

    # ---- per incident ----
    print("\nIncidents (any service, first detection):")
    by_scenario = defaultdict(list)
    for f in faults:
        by_scenario[f["scenario"]].append(f)
    detected = 0
    for scenario, records in by_scenario.items():
        s_start, s_end = min(r["start_dt"] for r in records), max(r["end_dt"] for r in records)
        flagged = [w for w in windows if w["flag"] and w["start"] < s_end and w["end"] > s_start]
        if flagged:
            detected += 1
            first = min(flagged, key=lambda w: w["detected_at"])
            print(f"  {scenario:<18} detected after {(first['detected_at'] - s_start).total_seconds():>4.0f} s "
                  f"(first: {first['service']} {first['severity']}); {len(flagged)} anomaly windows")
        else:
            print(f"  {scenario:<18} NOT detected")
    print(f"  -> {detected}/{len(by_scenario)} incidents detected")

    # ---- quiet windows ----
    quiet = [w for w in windows
             if all(not (w["start"] < f["end_dt"] + MARGIN and w["end"] > f["start_dt"] - MARGIN) for f in faults)]
    alarms = [w for w in quiet if w["flag"]]
    print(f"\nQuiet windows (no fault within 2 min): {len(quiet)}; false alarms: {len(alarms)}")
    for w in alarms:
        print(f"  {w['start']:%H:%M} {w['service']:<18} {w['severity']:<8} {'; '.join(w['reasons'] or [])}")

    # ---- service-level precision / recall ----
    faulty = [any(f["service"] == w["service"] and w["start"] < f["end_dt"] and w["end"] > f["start_dt"]
                  for f in faults) for w in windows]
    tp = sum(1 for w, y in zip(windows, faulty) if w["flag"] and y)
    fp = sum(1 for w, y in zip(windows, faulty) if w["flag"] and not y)
    fn = sum(1 for w, y in zip(windows, faulty) if not w["flag"] and y)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(f"\nService level: precision {precision:.3f}  recall {recall:.3f}  (TP {tp}, FP {fp}, FN {fn}; "
          f"FP includes dependent services reacting during incidents)")
    return 0


if __name__ == "__main__":
    sys.exit(main())