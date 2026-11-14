"""Live evaluation metrics (backend/detection/evaluation/live_run.py) on a small hand-made run."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.detection.evaluation.live_run import (
    AlertRecord, FaultRecord, WindowRecord, evaluate_normal, evaluate_run, incidents_of, summarise_runs,
)

T0 = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def window(service: str, minute: int, flagged: bool = False, logs: int = 300, severity: str | None = None,
           delay_s: float = 33) -> WindowRecord:
    start = at(minute)
    return WindowRecord(service, start, start + timedelta(minutes=1), logs, flagged,
                        severity if flagged else None,
                        start + timedelta(minutes=1, seconds=delay_s - 60 + 5) if flagged else None)


# One fault: payment-service errors from 10:05:30 to 10:07:30 (scenario "error_burst").
FAULTS = [FaultRecord("error_burst", "payment-service", at(5.5), at(7.5))]


def run_windows() -> list[WindowRecord]:
    ws = []
    for m in range(0, 15):
        ws.append(window("payment-service", m, flagged=m in (5, 6, 7), severity="HIGH"))
        # the gateway reacts during the incident; one false alarm far away at minute 13
        ws.append(window("api-gateway", m, flagged=m in (6, 13), severity="MEDIUM"))
    ws.append(window("auth-service", 14, logs=0))          # idle window: ignored
    return ws


ALERTS = [
    AlertRecord("payment-service", "HIGH", at(6.1), at(8.1), at(13.2), True, 3),
    AlertRecord("api-gateway", "MEDIUM", at(13.1), at(13.1), at(18.1), False, 1),   # outside the incident
]


def test_incidents_group_fault_records_by_scenario():
    faults = FAULTS + [FaultRecord("cascade", "order-service", at(20), at(23)),
                       FaultRecord("cascade", "payment-service", at(21), at(23))]
    incidents = incidents_of(faults)
    assert [i.scenario for i in incidents] == ["error_burst", "cascade"]
    assert incidents[1].start == at(20) and incidents[1].services == ("order-service", "payment-service")


def test_window_level_metrics():
    result = evaluate_run(FAULTS, run_windows(), ALERTS)
    wl = result["window_level"]
    assert wl["windows"] == 30                       # idle auth window left out
    assert wl["faulty_windows"] == 3                 # payment minutes 5, 6, 7 overlap the fault
    assert wl["recall"] == pytest.approx(1.0)
    assert wl["precision"] == pytest.approx(3 / 5)   # gateway at 6 and 13 are not the faulty service
    assert wl["full_window_recall"] == pytest.approx(1.0)   # only minute 6 lies fully inside
    assert wl["incident_precision"] == pytest.approx(4 / 5)  # the gateway reaction at 6 is expected
    assert wl["quiet_false_alarms"] == 1
    assert wl["quiet_false_alarm_list"][0]["service"] == "api-gateway"


def test_incident_and_alert_metrics():
    result = evaluate_run(FAULTS, run_windows(), ALERTS)
    inc = result["per_incident"][0]
    assert inc["detected"] and inc["first_service"] == "payment-service"
    assert inc["anomalies"] == 4                     # payment 5, 6, 7 and gateway 6
    assert inc["worst_severity"] == "HIGH"
    assert inc["alerts"] == 1 and inc["alerts_notified"] == 1
    assert inc["alert_delay_s"] == pytest.approx(36.0)
    assert inc["resolved_after_end_s"] == pytest.approx(342.0)
    assert result["summary"]["alerts_outside_incidents"] == 1
    fault = result["per_fault"][0]
    assert fault["flagged"] == 3 and fault["windows"] == 3
    assert fault["delay_s"] is not None and fault["delay_s"] < 60


def test_normal_run_counts_every_flag_as_false_alarm():
    ws = [window("auth-service", m, flagged=(m == 3), severity="LOW") for m in range(10)]
    result = evaluate_normal(ws, [])
    assert result["windows"] == 10 and result["false_alarms"] == 1
    assert result["false_alarm_rate"] == pytest.approx(0.1)
    assert result["false_alarm_severities"] == {"LOW": 1}


def test_summary_over_runs():
    one = evaluate_run(FAULTS, run_windows(), ALERTS)
    summary = summarise_runs([one, one], [evaluate_normal([window("auth-service", 0)], [])])
    assert summary["overall"]["runs"] == 2
    assert summary["overall"]["recall"]["mean"] == pytest.approx(1.0)
    assert summary["overall"]["recall"]["std"] == pytest.approx(0.0)
    assert summary["per_scenario"]["error_burst"]["detected"] == 2
    assert summary["normal"]["false_alarm_rate"] == pytest.approx(0.0)