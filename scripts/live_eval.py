"""
Live evaluation (Phase 10, RQ3). Turns real-time runs into numbers: detection per fault and per incident,
detection and alert delay, window-level precision / recall, false alarms, alerts per incident.
Protocol and definitions: docs/testing/live-evaluation-plan.md. Metric code: backend/detection/evaluation/live_run.py.

Usage (from the project root, venv active, stack running; results go to experiments/results/live/):

    # after a fault run (the generator prints the ground-truth file)
    python scripts/live_eval.py run data/ground_truth/eval-r1.jsonl --label r1

    # after a fault-free run: the minutes it lasted, run right after it ends (or give --from / --to in UTC)
    python scripts/live_eval.py normal --minutes 60 --label n1

    # mean, standard deviation, min and max over all saved runs -> summary.json and summary.md
    python scripts/live_eval.py summary
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.detection.config import DetectionSettings  # noqa: E402
from backend.detection.evaluation.live_run import (  # noqa: E402
    AlertRecord, FaultRecord, WindowRecord, evaluate_normal, evaluate_run, summarise_runs,
)
from backend.detection.pipeline import parse_timestamp  # noqa: E402
from backend.detection.registry import active_model  # noqa: E402

OUT_DIR = ROOT / "experiments" / "results" / "live"
# Evaluate from 4 min before the first fault to 4 min after the last one: inside the generator's 5-minute warm-up
# and final gap, so the first (partial) minute of traffic and the hand-over to the next run are never included.
PAD = timedelta(minutes=4)

WINDOWS_SQL = """
SELECT s.name, w.window_start, w.window_end, w.log_count, w.is_anomaly,
       a.severity, a.detected_at, a.summary->'reasons'
FROM detection_windows w
JOIN services s ON s.id = w.service_id
LEFT JOIN anomalies a ON a.window_id = w.id
WHERE w.model_id = %(model)s AND w.window_start >= %(start)s AND w.window_end <= %(end)s
ORDER BY w.window_start, s.name
"""
ALERTS_SQL = """
SELECT s.name, al.severity, al.first_seen_at, al.last_seen_at, al.resolved_at, al.notification_sent,
       al.occurrence_count
FROM alerts al
JOIN services s ON s.id = al.service_id
WHERE al.first_seen_at >= %(start)s AND al.first_seen_at < %(end)s
ORDER BY al.first_seen_at
"""


def load(conninfo: str, model_id: int, start: datetime, end: datetime) -> tuple[list[WindowRecord], list[AlertRecord]]:
    params = {"model": model_id, "start": start, "end": end}
    with psycopg.connect(conninfo) as conn:
        windows = [WindowRecord(r[0], r[1], r[2], r[3], r[4], r[5], r[6], tuple(r[7] or ()))
                   for r in conn.execute(WINDOWS_SQL, params).fetchall()]
        alerts = [AlertRecord(*r) for r in conn.execute(ALERTS_SQL, params).fetchall()]
    return windows, alerts


def model_or_exit(settings: DetectionSettings) -> dict:
    model = active_model(settings.postgres_conninfo)
    if model is None:
        sys.exit("[FAIL] no active model")
    return model


def save(label: str, payload: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{label}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def secs(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f} s"


def cmd_run(args: argparse.Namespace) -> int:
    raw = [json.loads(line) for line in args.ground_truth.open(encoding="utf-8") if line.strip()]
    if not raw:
        sys.exit(f"[FAIL] {args.ground_truth} has no fault records")
    faults = [FaultRecord(r["scenario"], r["service"], parse_timestamp(r["start"]), parse_timestamp(r["end"]))
              for r in raw]
    start = min(f.start for f in faults) - PAD
    end = max(f.end for f in faults) + PAD
    settings = DetectionSettings()
    model = model_or_exit(settings)
    windows, alerts = load(settings.postgres_conninfo, model["id"], start, end)
    if not windows:
        sys.exit(f"[FAIL] no stored windows for {model['name']} {model['version']} between {start:%H:%M} and "
                 f"{end:%H:%M} UTC. Was the detection service running during the run?")
    if datetime.now(timezone.utc) < max(f.end for f in faults) + timedelta(minutes=7):
        print("[WARN] the run ended less than 7 minutes ago: late windows and auto-resolves may still be missing.")

    result = evaluate_run(faults, windows, alerts, margin_s=args.margin, alert_tail_s=args.alert_tail)
    label = args.label or raw[0].get("run_id", args.ground_truth.stem)
    path = save(label, {"kind": "fault_run", "label": label, "ground_truth": str(args.ground_truth),
                        "run_id": raw[0].get("run_id"), "model": f"{model['name']} {model['version']}",
                        "evaluated_at": datetime.now(timezone.utc).isoformat(),
                        "margin_s": args.margin, "alert_tail_s": args.alert_tail, **result})

    s, w = result["summary"], result["window_level"]
    print(f"Run {label} · model {model['name']} {model['version']} · {w['windows']} windows\n")
    print(f"{'incident':<18} {'detected':<9} {'delay':>7} {'first':<18} {'anomalies':>9} {'worst':<9} "
          f"{'alerts':>6} {'alert delay':>11} {'notified':>8}")
    for i in result["per_incident"]:
        print(f"{i['scenario']:<18} {'yes' if i['detected'] else 'NO':<9} {secs(i['delay_s']):>7} "
              f"{(i['first_service'] or '—'):<18} {i['anomalies']:>9} {(i['worst_severity'] or '—'):<9} "
              f"{i['alerts']:>6} {secs(i['alert_delay_s']):>11} {i['alerts_notified']:>8}")
    print(f"\nIncidents detected {s['incidents_detected']}/{s['incidents']} · mean delay {secs(s['mean_delay_s'])} · "
          f"mean alert delay {secs(s['mean_alert_delay_s'])}")
    print(f"Window level: precision {pct(w['precision'])} · recall {pct(w['recall'])} · F1 "
          f"{w['f1']:.3f} · full-window recall {pct(w['full_window_recall'])} · incident precision "
          f"{pct(w['incident_precision'])}")
    print(f"Quiet windows {w['quiet_windows']}, false alarms {w['quiet_false_alarms']} "
          f"({pct(w['quiet_false_alarm_rate'])}) · alerts outside incidents {s['alerts_outside_incidents']}")
    print(f"\nSaved {path.relative_to(ROOT)}")
    return 0


def cmd_normal(args: argparse.Namespace) -> int:
    if args.start and args.end:
        start, end = parse_timestamp(args.start), parse_timestamp(args.end)
    else:
        end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        start = end - timedelta(minutes=args.minutes)
    settings = DetectionSettings()
    model = model_or_exit(settings)
    windows, alerts = load(settings.postgres_conninfo, model["id"], start, end)
    if not windows:
        sys.exit(f"[FAIL] no stored windows between {start:%H:%M} and {end:%H:%M} UTC")
    result = evaluate_normal(windows, alerts)
    path = save(args.label, {"kind": "normal_run", "label": args.label, "from": start.isoformat(),
                             "to": end.isoformat(), "model": f"{model['name']} {model['version']}",
                             "evaluated_at": datetime.now(timezone.utc).isoformat(), **result})
    print(f"Fault-free run {args.label} ({start:%H:%M}–{end:%H:%M} UTC) · {result['windows']} windows · "
          f"false alarms {result['false_alarms']} ({pct(result['false_alarm_rate'])}) "
          f"{result['false_alarm_severities']} · alerts {result['alerts']}")
    for a in result["false_alarm_list"]:
        print(f"  {a['start'][11:16]} {a['service']:<18} {a['severity']:<8} {'; '.join(a['reasons'])}")
    print(f"Saved {path.relative_to(ROOT)}")
    return 0


def fmt(stat: dict | None, kind: str) -> str:
    if not stat:
        return "—"
    if kind == "pct":
        return f"{100 * stat['mean']:.1f}% ± {100 * stat['std']:.1f}"
    if kind == "s":
        return f"{stat['mean']:.0f} s ± {stat['std']:.0f}"
    return f"{stat['mean']:.2f} ± {stat['std']:.2f}"


def cmd_summary(args: argparse.Namespace) -> int:
    files = sorted(p for p in OUT_DIR.glob("*.json") if p.name != "summary.json")
    payloads = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    runs = [p for p in payloads if p.get("kind") == "fault_run"]
    normals = [p for p in payloads if p.get("kind") == "normal_run"]
    if not runs:
        sys.exit(f"[FAIL] no fault runs saved in {OUT_DIR.relative_to(ROOT)}")
    summary = summarise_runs(runs, normals)
    summary["runs"] = [p["label"] for p in runs]
    summary["normal_runs"] = [p["label"] for p in normals]
    summary["models"] = sorted({p["model"] for p in payloads})
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    o = summary["overall"]
    lines = [
        "# Live evaluation summary",
        "",
        f"Fault runs: {', '.join(summary['runs'])} · fault-free runs: {', '.join(summary['normal_runs']) or 'none'} · "
        f"model: {', '.join(summary['models'])}. Values are mean ± standard deviation over runs.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Incidents detected | {fmt(o['incident_detection_rate'], 'pct')} |",
        f"| Detection delay (first anomaly after fault start) | {fmt(o['mean_delay_s'], 's')} |",
        f"| Alert delay (first alert after fault start) | {fmt(o['mean_alert_delay_s'], 's')} |",
        f"| Precision (faulty service's minutes) | {fmt(o['precision'], 'pct')} |",
        f"| Recall | {fmt(o['recall'], 'pct')} |",
        f"| F1 | {fmt(o['f1'], 'num')} |",
        f"| Recall, minutes fully inside a fault | {fmt(o['full_window_recall'], 'pct')} |",
        f"| Precision counting reactions near incidents | {fmt(o['incident_precision'], 'pct')} |",
        f"| False-alarm rate, quiet minutes | {fmt(o['quiet_false_alarm_rate'], 'pct')} |",
        f"| Anomalies per incident | {fmt(o['anomalies_per_incident'], 'num')} |",
        f"| Alerts per incident | {fmt(o['alerts_per_incident'], 'num')} |",
        f"| Alerts outside incidents per run | {fmt(o['alerts_outside_incidents'], 'num')} |",
    ]
    if summary["normal"]:
        n = summary["normal"]
        lines.append(f"| Fault-free runs: false alarms | {n['false_alarms']} of {n['windows']} windows "
                     f"({pct(n['false_alarm_rate'])}), {n['alerts']} alerts |")
    lines += ["", "| Scenario | Detected | Delay | Alert delay | Anomalies | Alerts | Worst severity |",
              "|---|---|---|---|---|---|---|"]
    for name, sc in summary["per_scenario"].items():
        worst = ", ".join(f"{k.lower()} {v}" for k, v in sc["worst_severities"].items())
        lines.append(f"| {name} | {sc['detected']}/{sc['runs']} | {fmt(sc['delay_s'], 's')} | "
                     f"{fmt(sc['alert_delay_s'], 's')} | {fmt(sc['anomalies'], 'num')} | {fmt(sc['alerts'], 'num')} | {worst} |")
    (OUT_DIR / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved {(OUT_DIR / 'summary.json').relative_to(ROOT)} and {(OUT_DIR / 'summary.md').relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Live evaluation of real-time runs (RQ3).")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="evaluate a fault run against its ground truth")
    run.add_argument("ground_truth", type=Path)
    run.add_argument("--label", help="name of the result file (default: the run id)")
    run.add_argument("--margin", type=float, default=120.0, help="seconds around an incident that count as near it")
    run.add_argument("--alert-tail", type=float, default=240.0,
                     help="seconds after an incident in which a new alert still belongs to it")
    run.set_defaults(func=cmd_run)
    normal = sub.add_parser("normal", help="evaluate a fault-free run")
    normal.add_argument("--label", required=True)
    normal.add_argument("--minutes", type=float, default=60.0, help="length of the run, ending now")
    normal.add_argument("--from", dest="start", help="start (ISO 8601 UTC) instead of --minutes")
    normal.add_argument("--to", dest="end", help="end (ISO 8601 UTC)")
    normal.set_defaults(func=cmd_normal)
    summary = sub.add_parser("summary", help="summarise all saved runs")
    summary.set_defaults(func=cmd_summary)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())