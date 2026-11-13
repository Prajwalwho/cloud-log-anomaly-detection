"""
Query parameters shared by all list endpoints (api-contracts.md §1):
time range (from/to, default last hour), pagination (page, size ≤ 200), comma-separated value lists.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Query

DEFAULT_RANGE = timedelta(hours=1)
MAX_SIZE = 200


def _utc(value: datetime) -> datetime:
    """Timestamps without a time zone are taken as UTC (contract: everything is UTC)."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def time_range(
    from_: datetime | None = Query(None, alias="from", description="Start (ISO 8601, UTC). Default: to - 1 hour"),
    to: datetime | None = Query(None, description="End (ISO 8601, UTC). Default: now"),
) -> tuple[datetime, datetime]:
    end = _utc(to) if to else datetime.now(timezone.utc)
    start = _utc(from_) if from_ else end - DEFAULT_RANGE
    if start >= end:
        raise HTTPException(status_code=400, detail="'from' must be before 'to'")
    return start, end


def pagination(
    page: int = Query(1, ge=1, description="Page number, starting at 1"),
    size: int = Query(50, ge=1, le=MAX_SIZE, description=f"Items per page (max {MAX_SIZE})"),
) -> tuple[int, int]:
    return page, size


def csv_values(raw: str | None, allowed: set[str], name: str) -> list[str] | None:
    """'HIGH,critical' -> ['HIGH', 'CRITICAL']; unknown values -> 400."""
    if not raw:
        return None
    values = [v.strip().upper() for v in raw.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise HTTPException(status_code=400,
                            detail=f"Unknown {name}: {', '.join(unknown)} (allowed: {', '.join(sorted(allowed))})")
    return values or None