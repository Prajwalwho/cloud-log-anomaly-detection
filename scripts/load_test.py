"""
Load test (Phase 10, Day 42): run the generator at increasing traffic rates, back to back, and measure for each step
whether ingestion and detection keep up. Rules: backend/detection/evaluation/load.py; results:
docs/testing/load-test-results.md. Output: experiments/results/load/<label>.json and .md (+ generator logs).

Before starting: stack up, venv active; ingestion, detection and alerting running (alerting with Telegram off:
traffic jumps are real anomalies for a model trained at 20 requests per second). The API is not needed.

Usage (from the project root):
    python scripts/load_test.py --label l1                          # 20, 50, 100, 200 requests/s, 5 min each
    python scripts/load_test.py --label l2 --rates 200 400 --minutes 3

A request produces about 3 log events, so 200 requests/s is about 600 events/s (36,000 per minute).
Each step is measured from its second minute (the first one mixes the old and the new rate).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from confluent_kafka import Consumer, TopicPartition

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.detection.config import DetectionSettings  # noqa: E402
from backend.detection.evaluation.latency import distribution  # noqa: E402
from backend.detection.evaluation.load import lag_summary, parse_generator_output, step_verdict  # noqa: E402
from backend.ingestion.config import settings as ingestion_settings  # noqa: E402
from latency_report import clock_offset, ingest_latency  # noqa: E402

OUT_DIR = ROOT / "experiments" / "results" / "load"
SAMPLE_S = 5.0
DRAIN_TIMEOUT_S = 600.0
SETTLE = timedelta(seconds=60)          # measure each step from its second minute

WINDOWS_SQL = """
SELECT window_end, created_at, is_anomaly FROM detection_windows
WHERE window_end > %(start)s AND window_end <= %(end)s
"""


class LagProbe:
    """Ingestion lag: events in logs.raw not yet committed by the ingestion group (read-only, never joins it)."""

    def __init__(self) -> None:
        self.topic = ingestion_settings.kafka_topic_logs
        self.consumer = Consumer({"bootstrap.servers": ingestion_settings.kafka_bootstrap_servers,
                                  "group.id": ingestion_settings.ingestion_group_id, "enable.auto.commit": False})
        partitions = self.consumer.list_topics(self.topic, timeout=10).topics[self.topic].partitions
        self.partitions = [TopicPartition(self.topic, p) for p in sorted(partitions)]

    def lag(self) -> int:
        total = 0
        for tp in self.consumer.committed(self.partitions, timeout=10):
            low, high = self.consumer.get_watermark_offsets(TopicPartition(self.topic, tp.partition), timeout=10)
            total += max(0, high - (tp.offset if tp.offset >= 0 else low))
        return total

    def close(self) -> None:
        self.consumer.close()


def docker_stats() -> dict[str, dict]:
    """CPU and memory of the stack's containers right now (empty if docker is not available)."""
    try:
        out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}};{{.CPUPerc}};{{.MemUsage}}"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    stats = {}
    for line in out.splitlines():
        parts = line.split(";")
        if len(parts) == 3 and parts[0].startswith("cla-"):
            stats[parts[0]] = {"cpu": parts[1], "memory": parts[2].split("/")[0].strip()}
    return stats


def run_step(rate: float, seconds: float, seed: int, log_path: Path, probe: LagProbe) -> dict:
    command = [sys.executable, "-m", "backend.log_generator.generator", "--kafka", "--rate", f"{rate:g}",
               "--duration", f"{seconds:g}", "--seed", str(seed)]
    start = datetime.now(timezone.utc)
    lags: list[int] = []
    containers: dict = {}
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=log, text=True)
        began = time.monotonic()
        while process.poll() is None:
            try:
                lags.append(probe.lag())
            except Exception as exc:                       # a failed sample is skipped, not fatal
                print(f"    [WARN] lag sample failed: {exc}")
            if not containers and time.monotonic() - began > seconds / 2:
                containers = docker_stats()
            elapsed = time.monotonic() - began
            if lags and int(elapsed) % 60 < SAMPLE_S:
                print(f"    {elapsed / 60:4.1f} min  ingestion lag {lags[-1]:>7,} events")
            time.sleep(SAMPLE_S)
    end = datetime.now(timezone.utc)
    generator = parse_generator_output(log_path.read_text(encoding="utf-8", errors="replace"))
    return {"rate": rate, "planned_s": seconds, "start": start, "end": end, "lags": lags,
            "containers": containers, "generator": generator, "exit_code": process.returncode,
            "log": str(log_path.relative_to(ROOT))}


def wait_for_drain(probe: LagProbe) -> float | None:
    """Seconds until ingestion has stored everything (None if it did not within DRAIN_TIMEOUT_S)."""
    began = time.monotonic()
    while time.monotonic() - began < DRAIN_TIMEOUT_S:
        if probe.lag() == 0:
            return round(time.monotonic() - began, 1)
        time.sleep(2)
    return None


def evaluate(step: dict, conninfo: str, offset: float) -> dict:
    start, end = step["start"] + SETTLE, step["end"]
    ingest = ingest_latency([(start, end)], backlog_ms=None)["distribution"]
    offset_td = timedelta(seconds=offset)
    with psycopg.connect(conninfo) as conn:
        rows = conn.execute(WINDOWS_SQL, {"start": start, "end": end}).fetchall()
    detect = distribution([(created - offset_td - window_end).total_seconds() for window_end, created, _ in rows])
    lag = lag_summary(step["lags"])
    keeps_up, reasons = step_verdict(step["planned_s"], step["generator"], ingest, detect, lag)
    events = step["generator"]["events"]
    return {
        "rate": step["rate"], "start": step["start"].isoformat(), "end": step["end"].isoformat(),
        "events": events,
        "events_per_s": round(events / step["planned_s"], 1) if events else None,
        "generator": step["generator"], "ingest": ingest, "ingestion_lag": lag, "detect": detect,
        "windows": len(rows), "anomalous_windows": sum(1 for *_, flagged in rows if flagged),
        "containers": step["containers"], "keeps_up": keeps_up, "reasons": reasons, "log": step["log"],
    }


def secs(d: dict | None, key: str) -> str:
    return f"{d[key]:.2f} s" if d else "—"


def write_report(label: str, results: list[dict], drain_s: float | None, minutes: float) -> None:
    lines = [f"# Load test: {label}", "",
             f"{len(results)} steps of {minutes:g} min, back to back; each measured from its second minute. "
             f"Ingestion drained {'in ' + str(drain_s) + ' s' if drain_s is not None else 'NOT within 10 min'} "
             f"after the last step.", "",
             "| Requests/s | Events/s | Log → stored p50 | p95 | max | Max ingestion lag | Minute end → judged p50 "
             "| p95 | Flagged windows | Keeps up |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lag = r["ingestion_lag"]["max"]
        lines.append(
            f"| {r['rate']:g} | {r['events_per_s'] or '—'} | {secs(r['ingest'], 'p50')} | {secs(r['ingest'], 'p95')} "
            f"| {secs(r['ingest'], 'max')} | {f'{lag:,}' if lag is not None else '—'} | {secs(r['detect'], 'p50')} "
            f"| {secs(r['detect'], 'p95')} | {r['anomalous_windows']} of {r['windows']} "
            f"| {'yes' if r['keeps_up'] else 'NO: ' + '; '.join(r['reasons'])} |")
    names = sorted({name for r in results for name in r["containers"]})
    if names:
        lines += ["", "Containers at mid-step (CPU / memory):", "",
                  "| Requests/s | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for r in results:
            cells = [f"{r['containers'][n]['cpu']} / {r['containers'][n]['memory']}" if n in r["containers"] else "—"
                     for n in names]
            lines.append(f"| {r['rate']:g} | " + " | ".join(cells) + " |")
    text = "\n".join(lines) + "\n"
    (OUT_DIR / f"{label}.md").write_text(text, encoding="utf-8")
    print("\n" + text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the pipeline at increasing traffic rates.")
    parser.add_argument("--label", required=True)
    parser.add_argument("--rates", type=float, nargs="+", default=[20, 50, 100, 200],
                        help="requests per second, one step each (default: %(default)s)")
    parser.add_argument("--minutes", type=float, default=5.0, help="length of each step (default: %(default)s)")
    args = parser.parse_args()
    settings = DetectionSettings()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        probe = LagProbe()
        offset = clock_offset(settings.postgres_conninfo)
    except Exception as exc:
        print(f"[FAIL] stack not reachable ({exc}). Start it: .\\scripts\\start.ps1 up")
        return 1
    if probe.lag() > 1000:
        print(f"[WARN] ingestion is {probe.lag():,} events behind before the test. Is the ingestion service running?")

    total = len(args.rates) * args.minutes + 2
    print(f"Load test {args.label}: {', '.join(f'{r:g}' for r in args.rates)} requests/s, {args.minutes:g} min each "
          f"(about {total:.0f} min). Started {datetime.now():%H:%M}.")
    steps = []
    try:
        for i, rate in enumerate(args.rates):
            print(f"\n  Step {i + 1}/{len(args.rates)}: {rate:g} requests/s")
            step = run_step(rate, args.minutes * 60, 400 + i, OUT_DIR / f"{args.label}-gen-{rate:g}.log", probe)
            g = step["generator"]
            print(f"    generator: {g['events'] or 0:,} events in {g['elapsed_s'] or 0:.0f} s, "
                  f"{g['delivered'] or 0:,} delivered, {g['failed'] or 0} failed (exit code {step['exit_code']})")
            steps.append(step)
    except KeyboardInterrupt:
        print("\nStopped; evaluating the finished steps.")

    print("\nWaiting for ingestion to catch up...")
    drain_s = wait_for_drain(probe)
    probe.close()
    print(f"  {'caught up in ' + str(drain_s) + ' s' if drain_s is not None else 'NOT caught up within 10 min'}; "
          f"waiting 75 s for the last minutes to be judged...")
    time.sleep(75)

    results = [evaluate(step, settings.postgres_conninfo, offset) for step in steps]
    payload = {"label": args.label, "created_at": datetime.now(timezone.utc).isoformat(), "minutes": args.minutes,
               "db_clock_offset_s": round(offset, 3), "drain_s": drain_s, "steps": results}
    (OUT_DIR / f"{args.label}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(args.label, results, drain_s, args.minutes)
    print(f"Saved experiments/results/load/{args.label}.json and .md")
    return 0


if __name__ == "__main__":
    sys.exit(main())