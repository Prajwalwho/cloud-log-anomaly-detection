"""
Speed of the pipeline (Phase 10, Day 41): how long each step takes, from a log line being written to a Telegram
message and the dashboard. Definitions: backend/detection/evaluation/latency.py; results:
docs/testing/latency-results.md. Output: experiments/results/latency/.

Usage (from the project root, venv active, stack running):

    # 1. stored data of earlier runs (ground-truth files written by the generator)
    python scripts/latency_report.py report --label night --ground-truth data/ground_truth/eval-r1.jsonl \
        data/ground_truth/eval-r2.jsonl data/ground_truth/eval-r3.jsonl

    # 2. a live run: record the dashboard's feed while it runs (API running), then report with it
    python scripts/latency_report.py watch --minutes 32 --label live1
    python scripts/latency_report.py report --label live1 --ground-truth data/ground_truth/speed-1.jsonl \
        --feed experiments/results/latency/feed-live1.jsonl

Only measure periods in which every service was running live: logs read from a backlog (a service started late or
the computer slept) take minutes by design. Such logs (over 60 s) are counted and reported, not mixed in.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.config import DetectionSettings  # noqa: E402
from backend.detection.evaluation.latency import (  # noqa: E402
    AlertTiming, AnomalyTiming, alert_stages, detection_stage, distribution, feed_stages, incident_chain,
)
from backend.detection.evaluation.live_run import FaultRecord, incidents_of  # noqa: E402
from backend.detection.pipeline import parse_timestamp  # noqa: E402
from backend.ingestion.config import settings as ingestion_settings  # noqa: E402

OUT_DIR = ROOT / "experiments" / "results" / "latency"
PAD = timedelta(minutes=4)          # same evaluated period as live_eval.py
BACKLOG_MS = 60_000
FEED_URL = "ws://localhost:8000/api/v1/ws/live"

LAG_MAPPING = {
    "lag_ms": {
        "type": "long",
        "script": {"source": "emit(doc['ingested_at'].value.toInstant().toEpochMilli()"
                             " - doc['timestamp'].value.toInstant().toEpochMilli())"},
    }
}

ANOMALIES_SQL = """
SELECT s.name, a.window_end, a.detected_at
FROM anomalies a JOIN services s ON s.id = a.service_id
WHERE a.detected_at >= %(start)s AND a.detected_at < %(end)s
"""
ALERTS_SQL = """
SELECT s.name, al.first_seen_at, al.created_at, al.notified_at
FROM alerts al JOIN services s ON s.id = al.service_id
WHERE al.first_seen_at >= %(start)s AND al.first_seen_at < %(end)s
"""

STAGE_NAMES = {
    "ingest": "Log created → stored in Elasticsearch",
    "detect": "Minute ends → anomaly stored",
    "alert": "Anomaly → alert opened",
    "telegram": "Alert opened → Telegram message sent",
    "anomaly.created": "Anomaly → shown on the dashboard (live feed)",
    "alert.created": "Anomaly → new alert shown on the dashboard",
}


# --------------------------------------------------------------------------- watch
async def _watch(url: str, seconds: float, out_path: Path) -> int:
    import websockets                                   # only needed for this subcommand

    deadline = time.monotonic() + seconds
    until = datetime.now() + timedelta(seconds=seconds)
    count = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as out:
        while time.monotonic() < deadline:
            try:
                async with websockets.connect(url) as ws:
                    print(f"Connected to {url}; recording until {until:%H:%M} (local time).")
                    while time.monotonic() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.monotonic()))
                        except asyncio.TimeoutError:
                            break
                        received = datetime.now(timezone.utc)
                        event = json.loads(raw)
                        kind, data = event.get("type"), event.get("data") or {}
                        if kind == "anomaly.created":
                            reference = data.get("detected_at")
                        elif kind == "alert.created":
                            reference = data.get("first_seen_at")
                        else:
                            continue                    # pings and alert updates
                        delay = (received - parse_timestamp(reference)).total_seconds() if reference else None
                        record = {"type": kind, "service": data.get("service"), "received_at": received.isoformat(),
                                  "reference_at": reference, "delay_s": round(delay, 3) if delay is not None else None}
                        out.write(json.dumps(record) + "\n")
                        out.flush()
                        count += 1
                        print(f"  {received:%H:%M:%S} UTC  {kind:<16} {record['service']:<18} "
                              f"{record['delay_s'] if record['delay_s'] is not None else '?'} s")
            except OSError as exc:
                print(f"  [WARN] cannot reach {url} ({exc}); retrying in 5 s. Is the API running?")
                await asyncio.sleep(5)
            except Exception as exc:                     # connection closed: reconnect
                print(f"  [WARN] live feed closed ({exc.__class__.__name__}); reconnecting in 5 s")
                await asyncio.sleep(5)
    print(f"\n{count} events recorded in {out_path.relative_to(ROOT)}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    out_path = OUT_DIR / f"feed-{args.label}.jsonl"
    try:
        return asyncio.run(_watch(args.url, args.minutes * 60, out_path))
    except KeyboardInterrupt:
        print(f"\nStopped. Events so far are in {out_path.relative_to(ROOT)}")
        return 0


# --------------------------------------------------------------------------- report
def load_faults(paths: list[Path]) -> list[list[FaultRecord]]:
    runs = []
    for path in paths:
        raw = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
        if not raw:
            sys.exit(f"[FAIL] {path} has no fault records")
        runs.append([FaultRecord(r["scenario"], r["service"], parse_timestamp(r["start"]), parse_timestamp(r["end"]))
                     for r in raw])
    return runs


def ingest_latency(periods: list[tuple[datetime, datetime]], backlog_ms: int | None = BACKLOG_MS) -> dict:
    """Percentiles of (ingested_at - timestamp), computed by Elasticsearch over every log in the periods.

    Logs older than backlog_ms when stored are counted separately and left out; None keeps every log (load test).
    """
    from elasticsearch import Elasticsearch

    es = Elasticsearch(ingestion_settings.elasticsearch_url, request_timeout=180)
    query = {"bool": {"should": [{"range": {"timestamp": {"gte": s.isoformat(), "lt": e.isoformat()}}}
                                 for s, e in periods], "minimum_should_match": 1}}
    response = es.search(
        index=f"{ingestion_settings.elasticsearch_index_prefix}-*", size=0, query=query,
        runtime_mappings=LAG_MAPPING, track_total_hits=True,
        aggs={
            "live": {"filter": {"range": {"lag_ms": {"lt": backlog_ms}}} if backlog_ms else {"match_all": {}},
                     "aggs": {"stats": {"stats": {"field": "lag_ms"}},
                              "pct": {"percentiles": {"field": "lag_ms", "percents": [50, 95, 99]}}}},
            "backlog": {"filter": {"range": {"lag_ms": {"gte": backlog_ms}}} if backlog_ms else {"match_none": {}}},
        },
    ).body
    live, backlog = response["aggregations"]["live"], response["aggregations"]["backlog"]["doc_count"]
    if not live["doc_count"]:
        return {"distribution": None, "backlog": backlog}
    stats, pct = live["stats"], live["pct"]["values"]
    return {
        "distribution": {"n": live["doc_count"], "mean": round(stats["avg"] / 1000, 3),
                         "min": round(stats["min"] / 1000, 3), "p50": round(pct["50.0"] / 1000, 3),
                         "p95": round(pct["95.0"] / 1000, 3), "p99": round(pct["99.0"] / 1000, 3),
                         "max": round(stats["max"] / 1000, 3)},
        "backlog": backlog,
    }


def clock_offset(conninfo: str) -> float:
    """Database clock minus host clock, in seconds (median of 5 readings, each centred on its round trip)."""
    readings = []
    with psycopg.connect(conninfo) as conn:
        for _ in range(5):
            before = datetime.now(timezone.utc)
            db_now = conn.execute("SELECT clock_timestamp()").fetchone()[0]
            after = datetime.now(timezone.utc)
            readings.append((db_now - (before + (after - before) / 2)).total_seconds())
    return sorted(readings)[2]


def fmt(d: dict | None) -> str:
    if d is None:
        return "| — | — | — | — | — |"
    return f"| {d['n']:,} | {d['p50']:.2f} s | {d['p95']:.2f} s | {d['p99']:.2f} s | {d['max']:.2f} s |"


def cmd_report(args: argparse.Namespace) -> int:
    runs = load_faults(args.ground_truth or [])
    periods = [(min(f.start for f in run) - PAD, max(f.end for f in run) + PAD) for run in runs]
    if args.start and args.end:
        periods.append((parse_timestamp(args.start), parse_timestamp(args.end)))
    if not periods:
        sys.exit("[FAIL] give --ground-truth files and/or --from and --to")
    incidents = [inc for run in runs for inc in incidents_of(run)]
    settings = DetectionSettings()

    try:
        offset = clock_offset(settings.postgres_conninfo)
        anomalies, alerts = [], []
        with psycopg.connect(settings.postgres_conninfo) as conn:
            for start, end in periods:
                params = {"start": start, "end": end}
                anomalies += [AnomalyTiming(*r) for r in conn.execute(ANOMALIES_SQL, params).fetchall()]
                alerts += [AlertTiming(*r) for r in conn.execute(ALERTS_SQL, params).fetchall()]
        anomalies, alerts = list(dict.fromkeys(anomalies)), list(dict.fromkeys(alerts))   # periods may overlap
    except psycopg.OperationalError as exc:
        print(f"[FAIL] PostgreSQL not reachable ({exc}). Start the stack: .\\scripts\\start.ps1 up")
        return 1
    try:
        ingest = ingest_latency(periods)
    except Exception as exc:
        print(f"[FAIL] Elasticsearch query failed ({exc}). Is the stack running?")
        return 1

    opened, telegram, later = alert_stages(alerts, offset)
    feed_records = []
    for path in args.feed or []:
        feed_records += [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    feed = feed_stages(feed_records)

    stages = {
        "ingest": ingest["distribution"],
        "detect": distribution(detection_stage(anomalies)),
        "alert": distribution(opened),
        "telegram": distribution(telegram),
        "anomaly.created": distribution(feed.get("anomaly.created", [])),
        "alert.created": distribution(feed.get("alert.created", [])),
    }
    chain = incident_chain(incidents, anomalies, alerts, offset_s=offset)
    chain_summary = {key: distribution([r[key] for r in chain if r[key] is not None])
                     for key in ("anomaly_s", "alert_s", "telegram_s")}

    payload = {
        "label": args.label, "created_at": datetime.now(timezone.utc).isoformat(),
        "periods": [[s.isoformat(), e.isoformat()] for s, e in periods],
        "ground_truth": [str(p) for p in args.ground_truth or []], "feed": [str(p) for p in args.feed or []],
        "db_clock_offset_s": round(offset, 3), "ingest_backlog_logs": ingest["backlog"],
        "alerts_notified_later": later, "stages": stages, "incidents": chain, "incident_summary": chain_summary,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{args.label}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [f"# Pipeline speed: {args.label}", "",
             f"Periods (UTC): " + "; ".join(f"{s:%Y-%m-%d %H:%M}–{e:%H:%M}" for s, e in periods) + ". "
             f"Database clock offset {offset:+.2f} s (subtracted where clocks are mixed).", "",
             "| Stage | n | median | p95 | p99 | max |", "|---|---|---|---|---|---|"]
    for key, name in STAGE_NAMES.items():
        lines.append(f"| {name} " + fmt(stages[key]))
    lines.append("")
    if ingest["backlog"]:
        lines.append(f"Logs read from a backlog (over 60 s, left out): {ingest['backlog']:,}.")
    if later:
        lines.append(f"Alerts notified only later (escalation or retry, left out of the Telegram stage): {later}.")
    if chain:
        lines += ["", "| Incident | Fault start (UTC) | → first anomaly | → first alert | → first Telegram |",
                  "|---|---|---|---|---|"]
        for r in chain:
            cells = [f"{r[k]:.1f} s" if r[k] is not None else "—" for k in ("anomaly_s", "alert_s", "telegram_s")]
            lines.append(f"| {r['scenario']} | {r['start'][11:19]} | " + " | ".join(cells) + " |")
        medians = [f"{chain_summary[k]['p50']:.1f} s" if chain_summary[k] else "—"
                   for k in ("anomaly_s", "alert_s", "telegram_s")]
        lines.append("| **median** | | " + " | ".join(medians) + " |")
    (OUT_DIR / f"{args.label}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved experiments/results/latency/{args.label}.json and .md")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the speed of every pipeline stage.")
    sub = parser.add_subparsers(dest="command", required=True)

    watch = sub.add_parser("watch", help="record the dashboard's live feed (/ws/live) for a while")
    watch.add_argument("--minutes", type=float, required=True)
    watch.add_argument("--label", required=True)
    watch.add_argument("--url", default=FEED_URL)
    watch.set_defaults(func=cmd_watch)

    report = sub.add_parser("report", help="stage latencies from stored data (+ recorded feeds)")
    report.add_argument("--label", required=True)
    report.add_argument("--ground-truth", type=Path, nargs="+", help="generator ground-truth files")
    report.add_argument("--from", dest="start", help="extra period start (ISO 8601 UTC), e.g. a fault-free run")
    report.add_argument("--to", dest="end", help="extra period end (ISO 8601 UTC)")
    report.add_argument("--feed", type=Path, nargs="+", help="feed files recorded with 'watch'")
    report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())