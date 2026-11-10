"""
Replay a generated JSONL log file through the live windowing engine and feature extractor (no Kafka),
to check against the ground truth that windows and features show each fault before going live.

The template vocabulary is learned from windows BEFORE the first fault (normal traffic only), so
"new_templates" means: not seen during normal operation.

Usage (from the project root):
    python experiments/replay_windows.py data/processed/all_faults.jsonl --ground-truth data/ground_truth/<run-id>.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.features.extractor import WindowFeatureExtractor  # noqa: E402
from backend.detection.preprocessing.parser import SERVICE_LOG_MASKS, create_template_miner  # noqa: E402
from backend.detection.windowing import WindowAggregator  # noqa: E402

SERVICES = ("api-gateway", "auth-service", "order-service", "payment-service", "inventory-service")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay logs through the windowing engine.")
    parser.add_argument("logfile", type=Path)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--window", type=float, default=60.0)
    parser.add_argument("--grace", type=float, default=5.0)
    args = parser.parse_args()

    faults = [json.loads(line) for line in args.ground_truth.open(encoding="utf-8")]
    first_fault = min(parse_ts(f["start"]) for f in faults)

    miner = create_template_miner(masks=SERVICE_LOG_MASKS)
    agg = WindowAggregator(args.window, services=SERVICES)
    grace = timedelta(seconds=args.grace)
    windows, events, last_ts = [], 0, None

    with args.logfile.open(encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            ts = parse_ts(event["timestamp"])
            template_id = miner.add_log_message(event["message"])["cluster_id"]
            agg.add(event["service"], ts, event["level"], template_id, event.get("latency_ms"))
            windows += agg.close_until(ts - grace)
            events += 1
            last_ts = ts
    windows += agg.close_until(last_ts + timedelta(seconds=args.window) + grace)   # flush the end

    training = [w for w in windows if w.end <= first_fault]
    extractor = WindowFeatureExtractor().fit(training)

    print(f"Events: {events:,}   windows closed: {len(windows):,}   late events: {agg.late_events}   "
          f"templates: {len(miner.drain.clusters)}   vocabulary (normal warmup): {len(extractor.vocabulary_)}")
    print(f"Empty windows: {sum(w.log_count == 0 for w in windows)}")

    rows = []
    for w in windows:
        s = extractor.summary(w)
        rows.append({"service": w.service, "start": w.start, "end": w.end, "logs": w.log_count,
                     "error_%": round(100 * w.error_count / w.log_count, 1) if w.log_count else 0.0,
                     "warn_%": round(100 * w.warn_count / w.log_count, 1) if w.log_count else 0.0,
                     "p95_ms": round(s["p95_latency_ms"], 1) if s["p95_latency_ms"] is not None else None,
                     "new_tpl": s["new_templates"]})
    table = pd.DataFrame(rows)

    for fault in faults:
        start, end = parse_ts(fault["start"]), parse_ts(fault["end"])
        part = table[(table["service"] == fault["service"]) &
                     (table["end"] > start - timedelta(minutes=2)) & (table["start"] < end + timedelta(minutes=2))].copy()
        part["fault"] = ((part["start"] < end) & (part["end"] > start)).map({True: "<<<", False: ""})
        part["start"] = part["start"].dt.strftime("%H:%M")
        print(f"\n{fault['scenario']} — {fault['service']} ({start:%H:%M:%S}–{end:%H:%M:%S}): {fault['description']}")
        print(part.drop(columns=["service", "end"]).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())