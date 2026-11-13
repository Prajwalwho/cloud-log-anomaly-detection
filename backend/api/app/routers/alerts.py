"""
GET /alerts, GET /alerts/{id}, PATCH /alerts/{id} (api-contracts.md §3.8–3.10).

Alerts are created by the alerting service (Phase 8). Status transitions: OPEN -> ACKNOWLEDGED -> RESOLVED,
and OPEN -> RESOLVED; anything else is 400. The alert row is locked during a change, so two concurrent updates
cannot produce an inconsistent alert.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from ..params import csv_values, pagination, time_range
from ..schemas import AlertDetailOut, AlertOut, AlertPatchIn, Page
from .anomalies import SELECT as ANOMALY_SELECT
from .anomalies import to_item as anomaly_item

router = APIRouter(tags=["alerts"])

STATUSES = {"OPEN", "ACKNOWLEDGED", "RESOLVED"}
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
ALLOWED = {("OPEN", "ACKNOWLEDGED"), ("ACKNOWLEDGED", "RESOLVED"), ("OPEN", "RESOLVED")}

SELECT = """
SELECT al.id, s.name AS service, al.severity, al.title, al.message, al.status, al.occurrence_count,
       al.first_seen_at, al.last_seen_at, al.acknowledged_at, al.acknowledged_by, al.resolved_at,
       al.notification_sent
FROM alerts al
JOIN services s ON s.id = al.service_id
"""


def alert_item(row: dict) -> dict:
    return {**row, "id": str(row["id"])}


@router.get("/alerts", response_model=Page[AlertOut])
def list_alerts(
    request: Request,
    status: str | None = None,
    severity: str | None = None,
    service: str | None = None,
    window: tuple = Depends(time_range),
    paging: tuple = Depends(pagination),
) -> dict:
    (start, end), (page, size) = window, paging
    statuses = csv_values(status, STATUSES, "status")
    severities = csv_values(severity, SEVERITIES, "severity")

    where = ["al.last_seen_at >= %(start)s", "al.last_seen_at < %(end)s"]
    params: dict = {"start": start, "end": end, "limit": size, "offset": (page - 1) * size}
    if statuses:
        where.append("al.status = ANY(%(statuses)s)")
        params["statuses"] = statuses
    if severities:
        where.append("al.severity = ANY(%(severities)s)")
        params["severities"] = severities
    if service:
        where.append("s.name = %(service)s")
        params["service"] = service
    clause = " WHERE " + " AND ".join(where)

    with request.app.state.pool.connection() as conn:
        total = conn.execute("SELECT count(*) AS n FROM alerts al JOIN services s ON s.id = al.service_id" + clause,
                             params).fetchone()["n"]
        rows = conn.execute(SELECT + clause + " ORDER BY al.last_seen_at DESC, al.id LIMIT %(limit)s OFFSET %(offset)s",
                            params).fetchall()
    return {"items": [alert_item(r) for r in rows], "total": total, "page": page, "size": size}


def _fetch_alert(conn, alert_id: UUID) -> dict:
    row = conn.execute(SELECT + " WHERE al.id = %(id)s", {"id": alert_id}).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert_item(row)


@router.get("/alerts/{alert_id}", response_model=AlertDetailOut)
def get_alert(request: Request, alert_id: UUID) -> dict:
    with request.app.state.pool.connection() as conn:
        alert = _fetch_alert(conn, alert_id)
        rows = conn.execute(ANOMALY_SELECT + " WHERE a.alert_id = %(id)s ORDER BY a.detected_at DESC",
                            {"id": alert_id}).fetchall()
    return {**alert, "anomalies": [anomaly_item(r) for r in rows]}


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def update_alert(request: Request, alert_id: UUID, body: AlertPatchIn) -> dict:
    with request.app.state.pool.connection() as conn:
        current = conn.execute("SELECT status FROM alerts WHERE id = %(id)s FOR UPDATE", {"id": alert_id}).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        if (current["status"], body.status) not in ALLOWED:
            raise HTTPException(status_code=400,
                                detail=f"Cannot change status from {current['status']} to {body.status}")
        if body.status == "ACKNOWLEDGED":
            conn.execute("UPDATE alerts SET status = 'ACKNOWLEDGED', acknowledged_at = now(), "
                         "acknowledged_by = %(by)s WHERE id = %(id)s", {"by": body.acknowledged_by, "id": alert_id})
        else:
            conn.execute("UPDATE alerts SET status = 'RESOLVED', resolved_at = now() WHERE id = %(id)s",
                         {"id": alert_id})
        return _fetch_alert(conn, alert_id)