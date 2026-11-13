"""
GET /logs and GET /logs/{event_id} (api-contracts.md §3.3, §3.4), from Elasticsearch.

Query design follows the index template (elasticsearch-design.md, checked Day 28):
- service, level, trace_id are keyword fields -> exact filters (term / terms)
- message is a text field -> full-text match, all words required
- timestamp is a date field -> time range and newest-first sort (event_id as tie-breaker)
Elasticsearch's from/size paging stops at 10,000 results, so page × size is limited to 10,000.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from ..es_queries import fetch_logs_by_ids, logs_index_pattern, to_log_event
from ..params import csv_values, pagination, time_range
from ..schemas import Page
from ..timeutil import iso_ms

router = APIRouter(tags=["logs"])

LEVELS = {"DEBUG", "INFO", "WARN", "ERROR", "FATAL"}
MAX_RESULT_WINDOW = 10_000


@router.get("/logs", response_model=Page[dict])
def search_logs(
    request: Request,
    q: str | None = None,
    service: str | None = None,
    level: str | None = None,
    trace_id: str | None = None,
    window: tuple = Depends(time_range),
    paging: tuple = Depends(pagination),
) -> dict:
    (start, end), (page, size) = window, paging
    if page * size > MAX_RESULT_WINDOW:
        raise HTTPException(status_code=400,
                            detail=f"page × size may not exceed {MAX_RESULT_WINDOW}; narrow the filters or time range")
    levels = csv_values(level, LEVELS, "level")

    filters: list[dict] = [{"range": {"timestamp": {"gte": iso_ms(start), "lt": iso_ms(end)}}}]
    if service:
        filters.append({"term": {"service": service}})
    if levels:
        filters.append({"terms": {"level": levels}})
    if trace_id:
        filters.append({"term": {"trace_id": trace_id}})
    must = [{"match": {"message": {"query": q, "operator": "and"}}}] if q else []

    settings = request.app.state.settings
    response = request.app.state.es.search(
        index=logs_index_pattern(settings.elasticsearch_index_prefix),
        query={"bool": {"filter": filters, "must": must}},
        sort=[{"timestamp": {"order": "desc"}}, {"event_id": {"order": "asc"}}],
        from_=(page - 1) * size, size=size, track_total_hits=True,
        ignore_unavailable=True, allow_no_indices=True,
    )
    hits = response["hits"]
    return {"items": [to_log_event(h["_source"]) for h in hits["hits"]],
            "total": hits["total"]["value"], "page": page, "size": size}


@router.get("/logs/{event_id}", response_model=dict)
def get_log(request: Request, event_id: UUID) -> dict:
    settings = request.app.state.settings
    logs, error = fetch_logs_by_ids(request.app.state.es,
                                    logs_index_pattern(settings.elasticsearch_index_prefix), [str(event_id)])
    if error:
        raise HTTPException(status_code=503, detail="Elasticsearch unavailable")
    if not logs:
        raise HTTPException(status_code=404, detail="Log event not found")
    return logs[0]