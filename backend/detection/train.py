"""
Train the live detector and save it as a model package (Phase 6, detection-design.md).

Steps:
  1. Parse normal training runs with Drain (service log masks) and build 60-s windows.
  2. Fit the LiveDetector (default: global PCA, log counts, label-free 99.9th-percentile threshold,
     log-ratio score normalisation, per-service baselines).
  3. Save the package (detector + Drain state + metadata) and reload it.
  4. Optional: score a fault run (--eval/--ground-truth) with the same judging rules as the live service;
     check the reloaded package reproduces the in-memory scores exactly; report detection and severities.
  5. Optional: score a fresh fault-free run (--normal-eval): every anomaly there is a false alarm.
  6. Optional: register the model as the active model in PostgreSQL (--register).

Usage (from the project root, one line):
  python -m backend.detection.train --train data/processed/train_normal_1.jsonl data/processed/train_normal_2.jsonl
      data/processed/train_normal_3.jsonl --version 1.1.0 --eval data/processed/all_faults.jsonl
      --ground-truth data/ground_truth/<run>.jsonl --normal-eval data/processed/normal_eval_4.jsonl --register
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .config import DetectionSettings
from .evaluation.live_eval import evaluate_flags, label_windows
from .live_model import GLOBAL, LiveDetector
from .package import load_package, save_package, write_metadata
from .pipeline import build_windows, read_events
from .preprocessing.parser import DEFAULT_DEPTH, DEFAULT_SIM_THRESHOLD, SERVICE_LOG_MASKS, create_template_miner
from .registry import active_model, register_model
from .scoring.judge import judge_windows

METADATA_DIR = Path("models/metadata")


def judged(detector: LiveDetector, windows: list) -> list:
    """Judge windows and return the results in the same order as `windows`."""
    results, _ = judge_windows(detector, windows)
    by_window = {id(r.window): r for r in results}
    return [by_window[id(w)] for w in windows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the live detector and save a model package.")
    parser.add_argument("--train", type=Path, nargs="+", required=True, help="normal-traffic JSONL files")
    parser.add_argument("--name", default="live-pca")
    parser.add_argument("--version", required=True)
    parser.add_argument("--algorithm", choices=["pca", "ocsvm"], default="pca")
    parser.add_argument("--raw-counts", action="store_true", help="use raw counts (default: log counts)")
    parser.add_argument("--per-service", action="store_true", help="one model per service (default: global)")
    parser.add_argument("--eval", type=Path, help="JSONL run with injected faults")
    parser.add_argument("--ground-truth", type=Path, help="ground truth for --eval")
    parser.add_argument("--normal-eval", type=Path, help="fresh fault-free JSONL run")
    parser.add_argument("--register", action="store_true", help="register as the active model in PostgreSQL")
    args = parser.parse_args(argv)

    settings = DetectionSettings()
    services = settings.service_list
    package_dir = Path(settings.models_dir) / f"{args.name}-{args.version}"
    if package_dir.exists():
        print(f"[FAIL] {package_dir} already exists; choose a new --version")
        return 1
    if args.eval and not args.ground_truth:
        print("[FAIL] --eval needs --ground-truth")
        return 1

    # ---- 1. training windows ----
    print("Training data:")
    miner = create_template_miner(masks=SERVICE_LOG_MASKS)
    windows = []
    for path in args.train:
        start = time.time()
        part = build_windows(read_events(path), miner, services, settings.window_s, settings.grace_s)
        windows += part
        print(f"  {path.name:<28} {len(part):>5} windows  ({time.time() - start:.0f} s)")
    print(f"  {len(windows)} windows, {len(miner.drain.clusters)} templates")

    # ---- 2. fit ----
    detector = LiveDetector(algorithm=args.algorithm, log_counts=not args.raw_counts,
                            per_service=args.per_service).fit(windows)
    training_flags = detector.predict(windows)["is_anomaly"]
    print(f"Fitted: {args.algorithm}, {'log' if not args.raw_counts else 'raw'} counts, "
          f"{'per-service' if args.per_service else 'global'}, {detector.normalisation} normalisation; "
          f"{len(detector.extractor.feature_names)} features; training windows flagged: "
          f"{training_flags.sum()} ({100 * training_flags.mean():.2f}%)")
    print("Baselines (median per training window):")
    for service, b in detector.baselines.items():
        p95 = f"{b['p95_latency_ms']:.0f} ms" if b["p95_latency_ms"] is not None else "-"
        print(f"  {service:<18} {b['log_count']:>6.0f} logs   p95 latency {p95}")

    # ---- 3. save and reload ----
    metadata = {
        "name": args.name, "version": args.version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "configuration": {"algorithm": args.algorithm, "log_counts": not args.raw_counts,
                          "per_service": args.per_service, "percentile": detector.percentile,
                          "min_std": detector.min_std, "normalisation": detector.normalisation,
                          "window_s": settings.window_s, "grace_s": settings.grace_s},
        "parser": {"masks": [list(m) for m in SERVICE_LOG_MASKS], "sim_threshold": DEFAULT_SIM_THRESHOLD,
                   "depth": DEFAULT_DEPTH, "templates": len(miner.drain.clusters)},
        "features": detector.extractor.feature_names,
        "thresholds": detector.thresholds, "spreads": detector.spreads, "baselines": detector.baselines,
        "training": {"files": [p.name for p in args.train], "windows": len(windows),
                     "windows_per_service": dict(Counter(w.service for w in windows)),
                     "training_flag_rate": float(training_flags.mean())},
        "evaluation": {},
    }
    save_package(package_dir, detector, miner, metadata)
    loaded_detector, loaded_miner, _ = load_package(package_dir)
    print(f"Saved and reloaded package {package_dir}")

    # ---- 4. fault run ----
    if args.eval:
        faults = [json.loads(line) for line in args.ground_truth.open(encoding="utf-8")]
        w_memory = build_windows(read_events(args.eval), copy.deepcopy(miner), services,
                                 settings.window_s, settings.grace_s)
        w_package = build_windows(read_events(args.eval), copy.deepcopy(loaded_miner), services,
                                  settings.window_s, settings.grace_s)
        out_memory, out_package = detector.predict(w_memory), loaded_detector.predict(w_package)
        same = (len(w_memory) == len(w_package)
                and np.array_equal(out_memory["is_anomaly"], out_package["is_anomaly"])
                and np.allclose(out_memory["raw"], out_package["raw"]))
        print(f"{'[OK]' if same else '[FAIL]'} reloaded package reproduces in-memory scores and flags exactly")
        if not same:
            return 1

        results = judged(loaded_detector, w_package)
        flags = np.array([r.is_anomaly for r in results])
        result = evaluate_flags(w_package, flags, faults)
        labels = label_windows(w_package, faults)
        severities_in_faults = Counter(r.severity for i, r in enumerate(results) if r.is_anomaly and labels["faulty"][i])
        metadata["evaluation"]["fault_run"] = {"file": args.eval.name, "ground_truth": args.ground_truth.name,
                                               "severities_of_faulty_windows": dict(severities_in_faults), **result}
        print(f"\nFault run: precision {result['precision']:.3f}  recall {result['recall']:.3f}  F1 {result['f1']:.3f}  "
              f"incidents {result['incidents_detected']}/{result['incidents']}  "
              f"quiet false alarms {result['quiet_false_alarms']}/{result['quiet_windows']}")
        for r_index, record in enumerate(result["per_record"]):
            idx = [i for i in range(len(w_package)) if r_index in labels["record_of"][i]]
            grades = [results[i].severity for i in idx if results[i].is_anomaly]
            ttd = f"{record['time_to_detect_s']:.0f} s" if record["time_to_detect_s"] is not None else "-"
            print(f"  {record['scenario']:<18} {record['service']:<18} {record['flagged']}/{record['windows']} "
                  f"windows, first flag after {ttd:<6} severities {grades}")
        print("  Reasons in full fault windows (first window of each record):")
        for r_index, record in enumerate(result["per_record"]):
            idx = [i for i in range(len(w_package)) if r_index in labels["record_of"][i] and labels["full"][i]]
            if idx and results[idx[0]].is_anomaly:
                print(f"    {record['scenario']:<18} {record['service']:<18} {results[idx[0]].severity:<8} "
                      + "; ".join(results[idx[0]].reasons))

    # ---- 5. fresh fault-free run ----
    if args.normal_eval:
        w_normal = build_windows(read_events(args.normal_eval), copy.deepcopy(loaded_miner), services,
                                 settings.window_s, settings.grace_s)
        results_normal = judged(loaded_detector, w_normal)
        alarms = [r for r in results_normal if r.is_anomaly]
        per_service = {s: sum(1 for r in alarms if r.window.service == s) for s in services}
        metadata["evaluation"]["normal_run"] = {
            "file": args.normal_eval.name, "windows": len(w_normal), "false_alarms": len(alarms),
            "false_alarm_rate": len(alarms) / len(w_normal) if w_normal else 0.0,
            "false_alarms_per_service": per_service,
            "false_alarm_severities": dict(Counter(r.severity for r in alarms)),
        }
        print(f"\nFault-free run: {len(alarms)} false alarms in {len(w_normal)} windows "
              f"({100 * len(alarms) / max(len(w_normal), 1):.2f}%)")
        for r in alarms:
            print(f"  {r.window.start:%H:%M} {r.window.service:<18} {r.severity:<8} score {r.score:.3f}: "
                  + "; ".join(r.reasons))

    write_metadata(package_dir, metadata)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    (METADATA_DIR / f"{args.name}-{args.version}.json").write_text(
        json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    print(f"\nMetadata written to {package_dir / 'metadata.json'} and {METADATA_DIR}")

    # ---- 6. register ----
    if args.register:
        model_id = register_model(
            settings.postgres_conninfo,
            name=args.name, version=args.version, algorithm=args.algorithm, file_path=str(package_dir),
            parameters=metadata["configuration"], threshold=detector.thresholds.get(GLOBAL),
            training_data=", ".join(metadata["training"]["files"]), training_samples=len(windows),
            metrics=metadata["evaluation"], activate=True,
        )
        active = active_model(settings.postgres_conninfo)
        print(f"Registered model id {model_id}; active model: {active['name']} {active['version']} (id {active['id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())