"""Timestamps in the contract format: ISO 8601, UTC, millisecond precision, Z suffix."""
from datetime import datetime, timezone


def iso_ms(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")