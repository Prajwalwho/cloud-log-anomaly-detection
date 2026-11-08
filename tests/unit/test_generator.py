"""Unit tests for the log generator."""
from collections import defaultdict
from datetime import datetime, timezone

import backend.log_generator.generator as gen_module
from backend.log_generator.generator import LEVELS, SCHEMA_VERSION, LogGenerator

REQUIRED_FIELDS = {"schema_version", "event_id", "timestamp", "service", "host", "level", "message"}
ALLOWED_FIELDS = REQUIRED_FIELDS | {"trace_id", "endpoint", "status_code", "latency_ms", "metadata"}
FIXED_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def collect(seed: int = 42, duration: float = 60, rate: float = 20) -> list[dict]:
    generator = LogGenerator(rate=rate, seed=seed, start=FIXED_START)
    return [event for _, event in generator.events(duration)]


def test_events_follow_contract():
    events = collect()
    assert events, "generator produced no events"
    for event in events:
        assert REQUIRED_FIELDS <= event.keys()
        assert event.keys() <= ALLOWED_FIELDS
        assert event["schema_version"] == SCHEMA_VERSION
        assert event["level"] in LEVELS
        assert event["timestamp"].endswith("Z")
        assert 0 < len(event["message"]) <= 10_000
        if event["status_code"] is not None:
            assert 100 <= event["status_code"] <= 599
        if event["latency_ms"] is not None:
            assert event["latency_ms"] >= 0


def test_same_seed_gives_same_output():
    assert collect(seed=7) == collect(seed=7)


def test_different_seeds_give_different_output():
    assert collect(seed=1) != collect(seed=2)


def test_timestamps_are_in_order():
    timestamps = [event["timestamp"] for event in collect()]
    assert timestamps == sorted(timestamps)


def test_event_ids_are_unique():
    ids = [event["event_id"] for event in collect()]
    assert len(ids) == len(set(ids))


def test_requests_span_multiple_services():
    services_per_trace = defaultdict(set)
    for event in collect():
        if event["trace_id"]:
            services_per_trace[event["trace_id"]].add(event["service"])
    assert any(len(services) >= 3 for services in services_per_trace.values())


def test_request_rate_is_roughly_respected():
    rate, duration = 20, 120
    gateway_requests = [
        e for e in collect(rate=rate, duration=duration)
        if e["service"] == "api-gateway" and e["trace_id"]
    ]
    expected = rate * duration
    assert 0.75 * expected < len(gateway_requests) < 1.25 * expected


def test_normal_error_rate_is_low():
    events = collect(duration=120)
    errors = sum(1 for e in events if e["level"] == "ERROR")
    assert errors / len(events) < 0.02


def test_downstream_failure_appears_at_gateway(monkeypatch):
    monkeypatch.setattr(gen_module, "BASE_ERROR_RATE", 1.0)   # every first call fails
    # Only request logs (with a trace_id); background logs like health checks are not requests
    gateway_requests = [
        e for e in collect(duration=10)
        if e["service"] == "api-gateway" and e["trace_id"]
    ]
    assert gateway_requests
    assert all(e["level"] == "ERROR" and e["status_code"] == 502 for e in gateway_requests)