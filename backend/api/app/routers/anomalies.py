"""
GET /anomalies, GET /anomalies/{id}, PATCH /anomalies/{id}/feedback (api-contracts.md §3.5–3.7).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from ..es_queries import fetch_logs_by_ids, logs_index_pattern
from ..params import csv_values, pagination, time_range
from ..schemas import AnomalyDetailOut, AnomalyOut, FeedbackIn, Page

router = APIRouter(tags=["anomalies"])

SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
FEEDBACK_FILTERS = {"CONFIRMED", "FALSE_POSITIVE", "NONE"}

FROM_JOINS = """
FROM anomalies a
JOIN services s ON s.id = a.service_id
JOIN model_registry m ON m.id = a.model_id
"""
SELECT = """
SELECT a.id, s.name AS service, a.detected_at, a.window_start, a.window_end, a.anomaly_score, a.severity,
       m.id AS model_id, m.name AS model_name, m.version AS model_version,
       a.summary, a.alert_id, a.feedback, a.sample_event_ids
""" + FROM_JOINS


def to_item(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "service": row["service"],
        "detected_at": row["detected_at"],
        "window_start": row["window_start"],
        "window_end": row["window_end"],
        "anomaly_score": row["anomaly_score"],
        "severity": row["severity"],
        "model": {"id": row["model_id"], "name": row["model_name"], "version": row["model_version"]},
        "summary": row["summary"],
        "alert_id": str(row["alert_id"]) if row["alert_id"] else None,
        "feedback": row["feedback"],
    }


@router.get("/anomalies", response_model=Page[AnomalyOut])
def list_anomalies(
    request: Request,
    service: str | None = None,
    severity: str | None = None,
    feedback: str | None = None,
    window: tuple = Depends(time_range),
    paging: tuple = Depends(pagination),
) -> dict:
    (start, end), (page, size) = window, paging
    severities = csv_values(severity, SEVERITIES, "severity")
    feedbacks = csv_values(feedback, FEEDBACK_FILTERS, "feedback")

    where = ["a.detected_at >= %(start)s", "a.detected_at < %(end)s"]
    params: dict = {"start": start, "end": end, "limit": size, "offset": (page - 1) * size}
    if service:
        where.append("s.name = %(service)s")
        params["service"] = service
    if severities:
        where.append("a.severity = ANY(%(severities)s)")
        params["severities"] = severities
    if feedbacks:
        parts = []
        if "NONE" in feedbacks:
            parts.append("a.feedback IS NULL")
        given = [f for f in feedbacks if f != "NONE"]
        if given:
            parts.append("a.feedback = ANY(%(feedbacks)s)")
            params["feedbacks"] = given
        where.append("(" + " OR ".join(parts) + ")")
    clause = " WHERE " + " AND ".join(where)

    with request.app.state.pool.connection() as conn:
        total = conn.execute("SELECT count(*) AS n" + FROM_JOINS + clause, params).fetchone()["n"]
        rows = conn.execute(SELECT + clause + " ORDER BY a.detected_at DESC, a.id LIMIT %(limit)s OFFSET %(offset)s",
                            params).fetchall()
    return {"items": [to_item(r) for r in rows], "total": total, "page": page, "size": size}


def _fetch_row(request: Request, anomaly_id: UUID) -> dict:
    with request.app.state.pool.connection() as conn:
        row = conn.execute(SELECT + " WHERE a.id = %(id)s", {"id": anomaly_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return row


@router.get("/anomalies/{anomaly_id}", response_model=AnomalyDetailOut)
def get_anomaly(request: Request, anomaly_id: UUID) -> dict:
    row = _fetch_row(request, anomaly_id)
    settings = request.app.state.settings
    ids = list(row["sample_event_ids"] or [])
    logs, error = fetch_logs_by_ids(request.app.state.es, logs_index_pattern(settings.elasticsearch_index_prefix), ids)
    return {**to_item(row), "sample_event_ids": ids, "sample_logs": logs, "sample_logs_error": error}


@router.patch("/anomalies/{anomaly_id}/feedback", response_model=AnomalyOut)
def set_feedback(request: Request, anomaly_id: UUID, body: FeedbackIn) -> dict:
    # Two separate parameters: using one parameter both as the stored VARCHAR value and in an IS NULL test made
    # PostgreSQL deduce two types for it ("text versus character varying", Day 28).
    with request.app.state.pool.connection() as conn:
        updated = conn.execute(
            """
            UPDATE anomalies
            SET feedback = %(feedback)s,
                feedback_at = CASE WHEN %(is_set)s THEN now() ELSE NULL END
            WHERE id = %(id)s
            RETURNING id
            """,
            {"feedback": body.feedback, "is_set": body.feedback is not None, "id": anomaly_id},
        ).fetchone()
    if updated is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return to_item(_fetch_row(request, anomaly_id))