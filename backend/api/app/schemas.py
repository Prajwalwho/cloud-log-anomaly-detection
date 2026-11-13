"""
Response models (api-contracts.md 1.1). Timestamps serialise to the contract format (ms precision, Z).
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, PlainSerializer

from .timeutil import iso_ms

UtcDatetime = Annotated[datetime, PlainSerializer(iso_ms, return_type=str, when_used="json")]
T = TypeVar("T")


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