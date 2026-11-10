"""
Parse the raw BGL log with Drain into a per-line event table.

BGL line format (space separated):
    label  unix_ts  date  node  time  node  type  component  level  content...
"label" is "-" for normal lines; any other value is an alert category (the line is an anomaly).

Outputs (data/processed/, not committed):
    bgl_events.npz       per line: timestamp (s), alert flag, level code, template id, alert category code
    bgl_templates.csv    template_id, template, count
    bgl_parse_info.json  parser settings and run statistics

Usage (from the project root):
    python experiments/parse_bgl.py --limit 200000     # quick check first
    python experiments/parse_bgl.py                    # full run (a few minutes)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.preprocessing.parser import (  # noqa: E402
    DEFAULT_DEPTH,
    DEFAULT_MASKS,
    DEFAULT_SIM_THRESHOLD,
    create_template_miner,
    templates_of,
)

# BGL-specific masks, applied before the generic ones:
# - NODE: node names such as R02-M1-N0-C:J12-U11
# - HEX: bare hexadecimal values without "0x" (6+ hex characters containing at least one digit),
#   as in CPU register dumps ("00000000:9a94a344 ... lr:00009f44"). Without this mask every dump
#   becomes its own template. Kept BGL-only: in the shared default it would turn long decimal
#   numbers (e.g. HDFS sizes, generator order ids) into <HEX> and change existing templates.
BGL_MASKS = (
    (r"\bR\d{2}-M\d-[\w:-]+", "NODE"),
    (r"\b(?=[0-9a-fA-F]*\d)[0-9a-fA-F]{6,}\b", "HEX"),
) + DEFAULT_MASKS
PROGRESS_EVERY = 500_000


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse BGL with Drain.")
    parser.add_argument("--input", type=Path, default=ROOT / "data/raw/BGL/BGL.log")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--limit", type=int, help="parse only the first N lines (quick check)")
    parser.add_argument("--sim", type=float, default=DEFAULT_SIM_THRESHOLD)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"[FAIL] {args.input} not found. Download BGL first (Day 17, Step 1).")
        return 1

    miner = create_template_miner(args.sim, args.depth, masks=BGL_MASKS)
    timestamps, alerts, level_codes, template_ids, category_codes = [], [], [], [], []
    levels: dict[str, int] = {}
    categories: dict[str, int] = {"-": 0}
    category_counts: Counter = Counter()
    lines = malformed = 0
    start = last_report = time.time()

    with args.input.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if args.limit and lines >= args.limit:
                break
            lines += 1
            parts = line.rstrip("\n").split(maxsplit=9)
            if len(parts) < 9:
                malformed += 1
                continue
            try:
                ts = int(parts[1])
            except ValueError:
                malformed += 1
                continue

            label, level = parts[0], parts[8]
            content = parts[9] if len(parts) > 9 and parts[9].strip() else "<empty>"

            result = miner.add_log_message(content)
            timestamps.append(ts)
            alerts.append(label != "-")
            level_codes.append(levels.setdefault(level, len(levels)))
            template_ids.append(result["cluster_id"])
            category_codes.append(categories.setdefault(label, len(categories)))
            if label != "-":
                category_counts[label] += 1

            if lines % PROGRESS_EVERY == 0:
                now = time.time()
                print(f"  {lines:>12,} lines   {len(miner.drain.clusters):>5} templates   "
                      f"{PROGRESS_EVERY / (now - last_report):>8,.0f} lines/s   {now - start:>6.0f} s")
                last_report = now

    elapsed = time.time() - start
    templates = templates_of(miner)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_limit{args.limit}" if args.limit else ""

    np.savez_compressed(
        args.out_dir / f"bgl_events{suffix}.npz",
        timestamp=np.array(timestamps, dtype=np.int64),
        alert=np.array(alerts, dtype=bool),
        level=np.array(level_codes, dtype=np.int16),
        template=np.array(template_ids, dtype=np.int32),
        category=np.array(category_codes, dtype=np.int16),
        level_names=np.array(list(levels), dtype=str),
        category_names=np.array(list(categories), dtype=str),
    )
    with (args.out_dir / f"bgl_templates{suffix}.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["template_id", "template", "count"])
        for t in templates:
            writer.writerow([t.template_id, t.template, t.count])

    parsed = len(timestamps)
    n_alerts = int(sum(alerts))
    first = datetime.fromtimestamp(min(timestamps), tz=timezone.utc) if timestamps else None
    last = datetime.fromtimestamp(max(timestamps), tz=timezone.utc) if timestamps else None
    info = {
        "lines_read": lines, "lines_malformed": malformed, "lines_parsed": parsed,
        "alert_lines": n_alerts, "templates": len(templates),
        "first_utc": first.isoformat() if first else None, "last_utc": last.isoformat() if last else None,
        "drain_sim_threshold": args.sim, "drain_depth": args.depth,
        "masks": [name for _, name in BGL_MASKS], "seconds": round(elapsed, 1),
    }
    (args.out_dir / f"bgl_parse_info{suffix}.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    print(f"\nParsed {parsed:,} of {lines:,} lines in {elapsed:.0f} s   malformed: {malformed:,}")
    print(f"Alert lines: {n_alerts:,} ({100 * n_alerts / max(parsed, 1):.2f}%)   Templates: {len(templates)}")
    if first:
        print(f"Time span: {first:%Y-%m-%d %H:%M} -> {last:%Y-%m-%d %H:%M} UTC "
              f"({(last - first).total_seconds() / 86400:.1f} days)")
    print("Levels:", ", ".join(f"{name}={level_codes.count(code):,}" for name, code in levels.items()))
    print("Top alert categories:", ", ".join(f"{c}={n:,}" for c, n in category_counts.most_common(8)))
    print("\nTop 10 templates:")
    for t in sorted(templates, key=lambda t: t.count, reverse=True)[:10]:
        print(f"  {t.template_id:>4}  {t.count:>9,}  {t.template[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())