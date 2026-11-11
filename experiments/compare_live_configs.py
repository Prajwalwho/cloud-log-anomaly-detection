"""
Choose the live detector configuration from data (Phase 6).

Trains each configuration on normal traffic only, then evaluates on a generated run with injected faults
and its ground truth. Window labels are per service: a window is faulty if it overlaps a fault interval of
that service. "False alarms outside incidents" counts flags in quiet periods (no fault within 2 minutes on
any service); flags on other services during an incident are expected side effects (Day 7), not counted there.

Usage (from the project root):
    python experiments/compare_live_configs.py --train data/processed/train_normal_1.jsonl data/processed/train_normal_2.jsonl data/processed/train_normal_3.jsonl --eval data/processed/all_faults.jsonl --ground-truth data/ground_truth/<run-id>.jsonl
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.evaluation.metrics import binary_metrics  # noqa: E402
from backend.detection.live_model import LiveDetector  # noqa: E402
from backend.detection.pipeline import build_windows, parse_timestamp, read_events  # noqa: E402
from backend.detection.preprocessing.parser import SERVICE_LOG_MASKS, create_template_miner  # noqa: E402

SERVICES = ("api-gateway", "auth-service", "order-service", "payment-service", "inventory-service")
RESULTS = ROOT / "experiments" / "results"

CONFIGS = {
    "A global PCA raw": dict(algorithm="pca", log_counts=False, per_service=False),
    "B global PCA log": dict(algorithm="pca", log_counts=True, per_service=False),
    "C per-service PCA raw": dict(algorithm="pca", log_counts=False, per_service=True),
    "D per-service PCA log": dict(algorithm="pca", log_counts=True, per_service=True),
    "E per-service OCSVM raw": dict(algorithm="ocsvm", log_counts=False, per_service=True),
    "F per-service OCSVM log": dict(algorithm="ocsvm", log_counts=True, per_service=True),
}


def section(title: str) -> None:
    print(f"\n{'=' * 100}\n{title}\n{'=' * 100}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare live detector configurations.")
    parser.add_argument("--train", type=Path, nargs="+", required=True)
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    args = parser.parse_args()
    pd.set_option("display.width", 200)

    # ---- training windows (one shared parser state) ----
    section("Training data (normal traffic only)")
    miner = create_template_miner(masks=SERVICE_LOG_MASKS)
    train_windows = []
    for path in args.train:
        start = time.time()
        windows = build_windows(read_events(path), miner, SERVICES)
        train_windows += windows
        print(f"  {path.name:<28} {len(windows):>5} windows   ({time.time() - start:.0f} s)")
    print(f"  total {len(train_windows)} windows; templates after training: {len(miner.drain.clusters)}")

    # ---- evaluation windows (copy of the trained parser, so training is not affected) ----
    eval_windows = build_windows(read_events(args.eval), copy.deepcopy(miner), SERVICES)
    faults = [json.loads(line) for line in args.ground_truth.open(encoding="utf-8")]
    for f in faults:
        f["start_dt"], f["end_dt"] = parse_timestamp(f["start"]), parse_timestamp(f["end"])

    n = len(eval_windows)
    faulty = np.zeros(n, bool)
    full = np.zeros(n, bool)
    record_of = [[] for _ in range(n)]
    for i, w in enumerate(eval_windows):
        for r, f in enumerate(faults):
            if f["service"] == w.service and w.start < f["end_dt"] and w.end > f["start_dt"]:
                faulty[i] = True
                record_of[i].append(r)
                full[i] |= w.start >= f["start_dt"] and w.end <= f["end_dt"]
    edge = faulty & ~full
    margin = timedelta(minutes=2)
    quiet = np.array([all(not (w.start < f["end_dt"] + margin and w.end > f["start_dt"] - margin) for f in faults)
                      for w in eval_windows])
    print(f"\nEvaluation: {n} windows; faulty {faulty.sum()} (full {full.sum()}, edge {edge.sum()}); "
          f"quiet windows {quiet.sum()}; fault records {len(faults)}")

    # ---- configurations ----
    section("Configurations")
    rows, outputs = [], {}
    for name, params in CONFIGS.items():
        start = time.time()
        detector = LiveDetector(**params).fit(train_windows)
        out = detector.predict(eval_windows)
        flag = out["is_anomaly"]
        outputs[name] = out
        m = binary_metrics(faulty, flag)
        detected = sum(any(flag[i] for i in range(n) if r in record_of[i]) for r in range(len(faults)))
        rows.append({
            "config": name, "precision": round(m.precision, 3), "recall": round(m.recall, 3), "f1": round(m.f1, 3),
            "full_recall": round(flag[full].mean(), 3), "edge_recall": round(flag[edge].mean(), 3),
            "incidents": f"{detected}/{len(faults)}",
            "false_alarms_quiet": int(flag[quiet].sum()), "quiet_fp_rate": round(flag[quiet].mean(), 4),
            "seconds": round(time.time() - start, 1),
        })
        print(f"  {name} done")
    table = pd.DataFrame(rows)
    print()
    print(table.to_string(index=False))
    RESULTS.mkdir(parents=True, exist_ok=True)
    table.to_csv(RESULTS / "live_config_comparison.csv", index=False)

    # ---- details per fault record for every configuration ----
    section("Per fault record: flagged windows / overlapping windows (time to first flag after fault start)")
    detail = []
    for r, f in enumerate(faults):
        row = {"scenario": f["scenario"], "service": f["service"]}
        idx = [i for i in range(n) if r in record_of[i]]
        for name in CONFIGS:
            flag = outputs[name]["is_anomaly"]
            hits = [i for i in idx if flag[i]]
            ttd = f"{(eval_windows[hits[0]].end - f['start_dt']).total_seconds():.0f}s" if hits else "-"
            row[name.split()[0]] = f"{len(hits)}/{len(idx)} ({ttd})"
        detail.append(row)
    print(pd.DataFrame(detail).to_string(index=False))
    print(f"\nSaved {RESULTS / 'live_config_comparison.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())