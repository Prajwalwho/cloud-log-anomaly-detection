"""
Parse the raw HDFS v1 log with Drain into templates and per-block event sequences.

Outputs (data/processed/, not committed):
    hdfs_templates.csv    template_id, template, count
    hdfs_sequences.csv    BlockId, Label, first_ts, length, events (template ids in log order),
                          sorted by first_ts (chronological, for time-based train/test splits)
    hdfs_parse_info.json  parser settings and run statistics (reproducibility)

Usage (from the project root):
    python experiments/parse_hdfs.py --limit 200000     # quick check first
    python experiments/parse_hdfs.py                    # full run (~10-20 min)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.preprocessing.parser import (  # noqa: E402
    DEFAULT_DEPTH,
    DEFAULT_MASKS,
    DEFAULT_SIM_THRESHOLD,
    create_template_miner,
    templates_of,
)

LINE_RE = re.compile(r"^(\d{6}) (\d{6}) (\d+) (\w+) ([^:]+): (.*)$")
BLOCK_RE = re.compile(r"blk_-?\d+")
PROGRESS_EVERY = 500_000


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse HDFS v1 with Drain.")
    parser.add_argument("--input", type=Path, default=ROOT / "data/raw/HDFS_v1/HDFS.log")
    parser.add_argument("--labels", type=Path, default=ROOT / "data/raw/HDFS_v1/preprocessed/anomaly_label.csv")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--limit", type=int, help="parse only the first N lines (for a quick check)")
    parser.add_argument("--sim", type=float, default=DEFAULT_SIM_THRESHOLD, help="Drain similarity threshold")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help="Drain tree depth")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"[FAIL] {args.input} not found. Download HDFS v1 first (Day 12).")
        return 1

    miner = create_template_miner(args.sim, args.depth)
    sequences: dict[str, list[int]] = defaultdict(list)
    first_ts: dict[str, str] = {}
    lines = unparsed = no_block = 0
    start = last_report = time.time()

    with args.input.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if args.limit and lines >= args.limit:
                break
            lines += 1
            match = LINE_RE.match(line)
            if not match:
                unparsed += 1
                continue
            date, clock, _pid, _level, _component, content = match.groups()
            block_match = BLOCK_RE.search(content)
            if not block_match:
                no_block += 1
                continue

            result = miner.add_log_message(content)
            block = block_match.group(0)
            sequences[block].append(result["cluster_id"])
            first_ts.setdefault(block, date + clock)

            if lines % PROGRESS_EVERY == 0:
                now = time.time()
                rate = PROGRESS_EVERY / (now - last_report)
                print(f"  {lines:>12,} lines   {len(miner.drain.clusters):>4} templates   "
                      f"{rate:>8,.0f} lines/s   {now - start:>6.0f} s")
                last_report = now

    elapsed = time.time() - start

    # ---- labels ----
    labels: dict[str, str] = {}
    with args.labels.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            labels[row["BlockId"]] = row["Label"]

    # ---- write outputs ----
    args.out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_limit{args.limit}" if args.limit else ""
    templates = templates_of(miner)

    templates_path = args.out_dir / f"hdfs_templates{suffix}.csv"
    with templates_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["template_id", "template", "count"])
        for t in templates:
            writer.writerow([t.template_id, t.template, t.count])

    sequences_path = args.out_dir / f"hdfs_sequences{suffix}.csv"
    with sequences_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["BlockId", "Label", "first_ts", "length", "events"])
        for block in sorted(sequences, key=lambda b: first_ts[b]):   # chronological order
            events = sequences[block]
            writer.writerow([block, labels.get(block, "Unknown"), first_ts[block], len(events),
                             " ".join(map(str, events))])

    info = {
        "input": str(args.input.relative_to(ROOT)) if args.input.is_relative_to(ROOT) else str(args.input),
        "lines_read": lines,
        "lines_unparsed": unparsed,
        "lines_without_block": no_block,
        "blocks": len(sequences),
        "templates": len(templates),
        "drain_sim_threshold": args.sim,
        "drain_depth": args.depth,
        "masks": [name for _, name in DEFAULT_MASKS],
        "seconds": round(elapsed, 1),
    }
    info_path = args.out_dir / f"hdfs_parse_info{suffix}.json"
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")

    # ---- summary ----
    print(f"\nParsed {lines:,} lines in {elapsed:.0f} s ({lines / max(elapsed, 1e-9):,.0f} lines/s)")
    print(f"Unparsed: {unparsed:,}   without block id: {no_block:,}")
    print(f"Blocks: {len(sequences):,}   Templates: {len(templates)}")
    print("\nTop 10 templates:")
    for t in sorted(templates, key=lambda t: t.count, reverse=True)[:10]:
        print(f"  {t.template_id:>3}  {t.count:>10,}  {t.template}")
    print(f"\nWrote {templates_path.name}, {sequences_path.name}, {info_path.name} to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())