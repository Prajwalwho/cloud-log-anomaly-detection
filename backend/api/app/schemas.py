"""
Response and request models (api-contracts.md 1.1). Timestamps serialise to the contract format (ms precision, Z).
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, PlainSerializer

from .timeutil import iso_ms

UtcDatetime = Annotated[datetime, PlainSerializer(iso_ms, return_type=str, when_used="json")]
T = TypeVar("T")
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class Page(BaseModel, Generic[T]):
    """Paginated response envelope (api-contracts.md §1)."""
    items: list[T]
    total: int
    page: int
    size: int


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    components: dict[str, Literal["ok", "down"]]


class ServiceOut(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: UtcDatetime


class ModelOut(BaseModel):
    id: int
    name: str
    version: str
    algorithm: str
    threshold: float | None
    training_data: str | None
    training_samples: int | None
    is_active: bool
    trained_at: UtcDatetime
    parameters: dict
    metrics: dict


class ModelRef(BaseModel):
    id: int
    name: str
    version: str


class AnomalyOut(BaseModel):
    """Anomaly item (api-contracts.md §3.5)."""
    id: str
    service: str
    detected_at: UtcDatetime
    window_start: UtcDatetime
    window_end: UtcDatetime
    anomaly_score: float
    severity: Severity
    model: ModelRef
    summary: dict
    alert_id: str | None
    feedback: Literal["CONFIRMED", "FALSE_POSITIVE"] | None


class AnomalyDetailOut(AnomalyOut):
    """Anomaly detail (api-contracts.md §3.6): item plus its sample log events from Elasticsearch."""
    sample_event_ids: list[str]
    sample_logs: list[dict]
    sample_logs_error: str | None = None


class FeedbackIn(BaseModel):
    """PATCH /anomalies/{id}/feedback (api-contracts.md §3.7); null clears the feedback."""
    feedback: Literal["CONFIRMED", "FALSE_POSITIVE"] | None