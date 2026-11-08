"""
Per-minute summary of a generated JSONL log file, with ground-truth fault windows marked.

Usage:
    python scripts/summarize_logs.py data/processed/all_faults.jsonl --ground-truth data/ground_truth/run-XXXX.jsonl
    python scripts/summarize_logs.py data/processed/all_faults.jsonl --ground-truth data/ground_truth/run-XXXX.jsonl --service order-service
"""
import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SERVICES = ["api-gateway", "auth-service", "order-service", "payment-service", "inventory-service"]
SHORT = {"api-gateway": "gateway", "auth-service": "auth", "order-service": "order",
         "payment-service": "payment", "inventory-service": "inventory"}


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_ground_truth(path: Path | None) -> list[tuple[str, datetime, datetime]]:
    if not path:
        return []
    faults = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            faults.append((record["service"], parse_ts(record["start"]), parse_ts(record["end"])))
    return faults


def faulty_services(minute: datetime, faults: list[tuple[str, datetime, datetime]]) -> list[str]:
    """Services with a fault overlapping [minute, minute + 60 s)."""
    minute_end = minute + timedelta(minutes=1)
    return sorted({SHORT[s] for s, start, end in faults if start < minute_end and end > minute})


def main() -> None:
    parser = argparse.ArgumentParser(description="Per-minute summary of a JSONL log file.")
    parser.add_argument("logfile", type=Path)
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--service", choices=SERVICES, help="detailed view of one service")
    args = parser.parse_args()

    stats = defaultdict(lambda: {"n": 0, "error": 0, "warn": 0, "latency": []})
    with args.logfile.open(encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            minute = parse_ts(event["timestamp"]).replace(second=0, microsecond=0)
            s = stats[(minute, event["service"])]
            s["n"] += 1
            if event["level"] in ("ERROR", "FATAL"):
                s["error"] += 1
            elif event["level"] == "WARN":
                s["warn"] += 1
            if event.get("latency_ms") is not None:
                s["latency"].append(event["latency_ms"])

    minutes = sorted({minute for minute, _ in stats})
    faults = load_ground_truth(args.ground_truth)

    def pct(part: int, whole: int) -> float:
        return 100 * part / whole if whole else 0.0

    if args.service:
        print(f"{'minute':<6} {'logs':>6} {'error%':>7} {'warn%':>7} {'median_ms':>10}   fault")
        for minute in minutes:
            s = stats[(minute, args.service)]
            median = statistics.median(s["latency"]) if s["latency"] else 0.0
            marker = "  <<< FAULT" if SHORT[args.service] in faulty_services(minute, faults) else ""
            print(f"{minute:%H:%M}  {s['n']:>6} {pct(s['error'], s['n']):>6.1f}% "
                  f"{pct(s['warn'], s['n']):>6.1f}% {median:>10.1f}{marker}")
    else:
        header = "".join(f"{SHORT[s]:>16}" for s in SERVICES)
        print(f"{'minute':<6}{header}   faults")
        print(f"{'':<6}" + "".join(f"{'logs  err%':>16}" for _ in SERVICES))
        for minute in minutes:
            cells = ""
            for service in SERVICES:
                s = stats[(minute, service)]
                cells += f"{s['n']:>10} {pct(s['error'], s['n']):>4.1f}%"
            marked = faulty_services(minute, faults)
            print(f"{minute:%H:%M} {cells}   {', '.join(marked)}")


if __name__ == "__main__":
    main()