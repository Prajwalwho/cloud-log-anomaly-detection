"""
Validation of incoming log events against the log event contract
(docs/design/contracts.md, Sections 2 and 2.4).

Rules enforced:
  1. valid JSON
  2. required fields present, all fields of the correct type (strict: "500" is not an int)
  3. level is one of DEBUG, INFO, WARN, ERROR, FATAL
  4. timestamp parseable, timezone-aware, not more than 5 minutes in the future
  5. status_code 100-599, latency_ms >= 0
  6. no top-level fields outside the contract (extra data belongs in metadata)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, field_validator

SCHEMA_VERSION = "1.0"
MAX_FUTURE_SKEW = timedelta(minutes=5)
MAX_ERROR_LENGTH = 1000

Level = Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]


class LogEvent(BaseModel):
    """One validated log event (contracts.md, Section 2.1)."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"]
    event_id: UUID
    timestamp: AwareDatetime
    service: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    host: str = Field(min_length=1, max_length=100)
    level: Level
    message: str = Field(min_length=1, max_length=10_000)
    trace_id: str | None = Field(default=None, max_length=64)
    endpoint: str | None = Field(default=None, max_length=200)
    status_code: int | None = Field(default=None, ge=100, le=599)
    latency_ms: float | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _utc_and_not_in_future(cls, value: datetime) -> datetime:
        value = value.astimezone(timezone.utc)
        if value > datetime.now(timezone.utc) + MAX_FUTURE_SKEW:
            raise ValueError("timestamp is more than 5 minutes in the future")
        return value


def validate_message(raw: bytes | str | None) -> LogEvent:
    """Parse and validate one raw Kafka message. Raises on any contract violation."""
    if raw is None:
        raise ValueError("empty message (no value)")
    return LogEvent.model_validate_json(raw)


def describe_error(exc: Exception) -> str:
    """Short, human-readable reason for a rejection, e.g. "level: Input should be 'DEBUG', ..."."""
    if isinstance(exc, ValidationError):
        parts = []
        for error in exc.errors(include_url=False):
            field = ".".join(str(p) for p in error["loc"]) or "json"
            parts.append(f"{field}: {error['msg']}")
        text = "; ".join(parts)
    else:
        text = f"{type(exc).__name__}: {exc}"
    return text[:MAX_ERROR_LENGTH]


def utc_now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def build_deadletter_record(
    raw: bytes | None, source_topic: str, partition: int, offset: int, error: str
) -> dict:
    """Dead-letter message in the format of contracts.md, Section 5.2."""
    return {
        "schema_version": SCHEMA_VERSION,
        "failed_at": utc_now_iso(),
        "source_topic": source_topic,
        "source_partition": partition,
        "source_offset": offset,
        "error": error,
        # The original message, exactly as received, so nothing is lost
        "raw_message": raw.decode("utf-8", errors="replace") if raw else "",
    }