"""
Response and request models (api-contracts.md 1.1). Timestamps serialise to the contract format (ms precision, Z).
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, Field, PlainSerializer

from .timeutil import iso_ms

UtcDatetime = Annotated[datetime, PlainSerializer(iso_ms, return_type=str, when_used="json")]
T = TypeVar("T")
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
AlertStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]


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


class AlertOut(BaseModel):
    """Alert item (api-contracts.md §3.8)."""
    id: str
    service: str
    severity: Severity
    title: str
    message: str | None
    status: AlertStatus
    occurrence_count: int
    first_seen_at: UtcDatetime
    last_seen_at: UtcDatetime
    acknowledged_at: UtcDatetime | None
    acknowledged_by: str | None
    resolved_at: UtcDatetime | None
    notification_sent: bool


class AlertDetailOut(AlertOut):
    """Alert detail (api-contracts.md §3.9): item plus its anomalies, newest first."""
    anomalies: list[AnomalyOut]


class AlertPatchIn(BaseModel):
    """PATCH /alerts/{id} (api-contracts.md §3.10)."""
    status: AlertStatus
    acknowledged_by: str | None = Field(None, max_length=100)


class ServiceStats(BaseModel):
    service: str
    anomalies: int
    error_rate: float


class SummaryOut(BaseModel):
    """GET /stats/summary (api-contracts.md §3.11)."""
    total_logs: int
    total_windows: int
    total_anomalies: int
    open_alerts: int
    error_rate: float
    by_severity: dict[str, int]
    by_service: list[ServiceStats]


class Point(BaseModel):
    t: UtcDatetime
    v: float | None


class Series(BaseModel):
    service: str
    points: list[Point]


class TimeseriesOut(BaseModel):
    """GET /stats/timeseries (api-contracts.md §3.12)."""
    metric: str
    interval: str
    series: list[Series]