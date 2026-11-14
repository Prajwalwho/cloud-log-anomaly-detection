"""
GET /stats/summary and GET /stats/timeseries (api-contracts.md §3.11, §3.12), from detection_windows.

Windows hold one row per service and minute, so these queries stay fast regardless of log volume.
Assumption: one model scored each period (we always run one at a time); two models scoring the same period
would be counted twice.

Idle windows are excluded (Day 34): when no service had traffic, the detection service still stores a window per
service, with log_count 0, is_anomaly false and a high model score (an empty window is far from normal). Those
minutes say nothing about anomalies but made every idle minute look anomalous in the heatmap. A window that is empty
AND flagged (a silent service while others had traffic) is a real anomaly and is kept.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..params import time_range
from ..schemas import SummaryOut, TimeseriesOut

router = APIRouter(tags=["statistics"])

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ACTIVE = "NOT (w.log_count = 0 AND NOT w.is_anomaly)"      # excludes idle (no-traffic) windows
# Aggregation per bucket (api-contracts.md §3.12)
METRICS = {
    "log_count": "SUM(w.log_count)::float",
    "error_rate": "SUM(w.error_count)::float / NULLIF(SUM(w.log_count), 0)",
    "avg_latency_ms": "AVG(w.avg_latency_ms)",
    "anomaly_score": "MAX(w.anomaly_score)",
    "anomaly_count": "SUM(w.is_anomaly::int)::float",
}
INTERVALS = {"1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "1h": timedelta(hours=1)}
MAX_POINTS = 2000


@router.get("/stats/summary", response_model=SummaryOut)
def summary(request: Request, window: tuple = Depends(time_range)) -> dict:
    start, end = window
    params = {"start": start, "end": end}
    with request.app.state.pool.connection() as conn:
        totals = conn.execute(
            "SELECT COALESCE(SUM(w.log_count), 0) AS logs, COALESCE(SUM(w.error_count), 0) AS errors, "
            "COUNT(*) AS windows FROM detection_windows w "
            f"WHERE w.window_start >= %(start)s AND w.window_start < %(end)s AND {ACTIVE}", params).fetchone()
        severities = conn.execute(
            "SELECT severity, COUNT(*) AS n FROM anomalies "
            "WHERE window_start >= %(start)s AND window_start < %(end)s GROUP BY severity", params).fetchall()
        open_alerts = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE status = 'OPEN'").fetchone()["n"]
        per_service = conn.execute(
            f"""
            SELECT s.name AS service,
                   COALESCE(SUM(w.log_count), 0) AS logs,
                   COALESCE(SUM(w.error_count), 0) AS errors,
                   (SELECT COUNT(*) FROM anomalies a
                     WHERE a.service_id = s.id AND a.window_start >= %(start)s AND a.window_start < %(end)s)
                     AS anomalies
            FROM services s
            JOIN detection_windows w
              ON w.service_id = s.id AND w.window_start >= %(start)s AND w.window_start < %(end)s AND {ACTIVE}
            GROUP BY s.id, s.name
            ORDER BY anomalies DESC, s.name
            """, params).fetchall()

    by_severity = {s: 0 for s in SEVERITIES}
    by_severity.update({row["severity"]: row["n"] for row in severities})
    return {
        "total_logs": totals["logs"],
        "total_windows": totals["windows"],
        "total_anomalies": sum(by_severity.values()),
        "open_alerts": open_alerts,
        "error_rate": totals["errors"] / totals["logs"] if totals["logs"] else 0.0,
        "by_severity": by_severity,
        "by_service": [{"service": r["service"], "anomalies": r["anomalies"],
                        "error_rate": r["errors"] / r["logs"] if r["logs"] else 0.0} for r in per_service],
    }


@router.get("/stats/timeseries", response_model=TimeseriesOut)
def timeseries(
    request: Request,
    metric: str = Query(..., description=f"One of {', '.join(METRICS)}"),
    interval: str = Query("5m", description=f"One of {', '.join(INTERVALS)}"),
    service: str | None = None,
    window: tuple = Depends(time_range),
) -> dict:
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail=f"Unknown metric: {metric} (allowed: {', '.join(METRICS)})")
    if interval not in INTERVALS:
        raise HTTPException(status_code=400, detail=f"Unknown interval: {interval} (allowed: {', '.join(INTERVALS)})")
    start, end = window
    step = INTERVALS[interval]
    if (end - start) / step > MAX_POINTS:
        raise HTTPException(status_code=400,
                            detail=f"More than {MAX_POINTS} points per series; use a larger interval or shorter range")

    service_filter = "AND s.name = %(service)s" if service else ""
    sql = f"""
        SELECT s.name AS service,
               date_bin(%(step)s, w.window_start, TIMESTAMPTZ '2000-01-01 00:00:00+00') AS t,
               {METRICS[metric]} AS v
        FROM detection_windows w
        JOIN services s ON s.id = w.service_id
        WHERE w.window_start >= %(start)s AND w.window_start < %(end)s AND {ACTIVE} {service_filter}
        GROUP BY s.name, t
        ORDER BY s.name, t
    """
    with request.app.state.pool.connection() as conn:
        rows = conn.execute(sql, {"step": step, "start": start, "end": end, "service": service}).fetchall()

    series: dict[str, list[dict]] = {}
    for row in rows:
        series.setdefault(row["service"], []).append({"t": row["t"], "v": row["v"]})
    return {"metric": metric, "interval": interval,
            "series": [{"service": name, "points": points} for name, points in series.items()]}