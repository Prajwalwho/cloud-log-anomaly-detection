"""Unit tests for fault scenarios and fault injection."""
import statistics
from datetime import datetime, timezone

import pytest

from backend.log_generator.generator import LogGenerator, ground_truth_records
from backend.log_generator.scenarios import SCENARIOS, Fault, build_schedule, schedule_faults

FIXED_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
FAULT_START, FAULT_END = 30.0, 90.0


def run(faults, duration: float = 120, seed: int = 3) -> list[tuple[float, dict]]:
    generator = LogGenerator(rate=20, seed=seed, start=FIXED_START, faults=faults)
    return list(generator.events(duration))


def inside(offset: float) -> bool:
    return FAULT_START <= offset < FAULT_END


def request_events(events, service):
    return [(o, e) for o, e in events if e["service"] == service and e["trace_id"] and e["level"] != "DEBUG"]


def error_rate(pairs) -> float:
    return sum(1 for _, e in pairs if e["level"] == "ERROR") / len(pairs)


# ---------------- validation ----------------
def test_invalid_fault_kind_rejected():
    with pytest.raises(ValueError):
        Fault("explosion", "payment-service", 0, 10)


def test_fault_end_must_be_after_start():
    with pytest.raises(ValueError):
        Fault("silent", "payment-service", 10, 10)


def test_gateway_cannot_be_faulted():
    with pytest.raises(ValueError):
        LogGenerator(rate=1, faults=[Fault("silent", "api-gateway", 0, 10)])


def test_no_faults_gives_identical_output_to_plain_generator():
    plain = list(LogGenerator(rate=20, seed=5, start=FIXED_START).events(60))
    empty = list(LogGenerator(rate=20, seed=5, start=FIXED_START, faults=()).events(60))
    assert plain == empty


# ---------------- fault behaviour ----------------
def test_error_burst_raises_error_rate_only_inside_window():
    events = run([Fault("error_burst", "payment-service", FAULT_START, FAULT_END, error_rate=0.4)])
    payment = request_events(events, "payment-service")
    in_window = [p for p in payment if inside(p[0])]
    outside = [p for p in payment if not inside(p[0]) and p[0] > FAULT_END + 1]
    assert error_rate(in_window) > 0.25
    assert error_rate(outside) < 0.05


def test_latency_spike_increases_latency():
    events = run([Fault("latency_spike", "order-service", FAULT_START, FAULT_END, latency_factor=6.0)])
    order = request_events(events, "order-service")
    lat_in = statistics.median(e["latency_ms"] for o, e in order if inside(o))
    lat_out = statistics.median(e["latency_ms"] for o, e in order if o < FAULT_START)
    assert lat_in > 4 * lat_out


def test_new_error_message_appears_only_during_fault():
    message = "Unhandled exception in worker {worker_id}: OutOfMemoryError"
    events = run([Fault("new_error", "inventory-service", FAULT_START, FAULT_END,
                        error_rate=0.15, message=message)])
    novel = [o for o, e in events if "OutOfMemoryError" in e["message"]]
    assert novel, "new error never appeared"
    assert all(FAULT_START <= o < FAULT_END + 1 for o in novel)


def test_silent_service_writes_nothing_and_gateway_returns_503():
    events = run([Fault("silent", "auth-service", FAULT_START, FAULT_END)])
    auth_inside = [o for o, e in events if e["service"] == "auth-service" and FAULT_START + 1 <= o < FAULT_END]
    assert auth_inside == []
    gateway_503 = [o for o, e in events if e["service"] == "api-gateway" and e["status_code"] == 503]
    assert gateway_503
    assert all(FAULT_START <= o < FAULT_END + 1 for o in gateway_503)


# ---------------- schedule and ground truth ----------------
def test_schedule_places_scenarios_with_gaps():
    schedule, total = build_schedule(["error_burst", "cascading_failure"], warmup_s=300, gap_s=300)
    assert [offset for _, offset in schedule] == [300, 720]          # 300 + 120 + 300
    assert total == 720 + 180 + 300
    assert len(schedule_faults(schedule)) == 1 + 3


def test_all_scenarios_are_valid_and_schedulable():
    schedule, total = build_schedule(list(SCENARIOS))
    faults = schedule_faults(schedule)
    LogGenerator(rate=1, faults=faults)   # must not raise
    assert all(f.end_s <= total for f in faults)


def test_ground_truth_records_follow_contract():
    schedule, _ = build_schedule(["cascading_failure"], warmup_s=60, gap_s=60)
    records = ground_truth_records(schedule, FIXED_START, "run-test")
    assert len(records) == 3
    for record in records:
        assert set(record) == {"run_id", "scenario", "service", "start", "end", "description"}
        assert record["scenario"] == "cascading_failure"
        assert record["start"] < record["end"]
        assert record["start"].endswith("Z")