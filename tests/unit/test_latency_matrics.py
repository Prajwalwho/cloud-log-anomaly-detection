"""Pipeline speed metrics (Day 41): percentiles, stage durations, per-incident chain, live-feed records."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.detection.evaluation.latency import (
    AlertTiming, AnomalyTiming, alert_stages, detection_stage, distribution, feed_stages, incident_chain, percentile,
)
from backend.detection.evaluation.live_run import Incident

T0 = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def test_percentile_interpolates():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([5.0], 0.95) == 5.0
    with pytest.raises(ValueError):
        percentile([], 0.5)


def test_distribution():
    d = distribution([4.0, 1.0, 3.0, 2.0, 5.0])
    assert (d["n"], d["min"], d["p50"], d["max"], d["mean"]) == (5, 1.0, 3.0, 5.0, 3.0)
    assert d["p95"] == pytest.approx(4.8)
    assert distribution([]) is None


def test_detection_stage_measures_from_minute_end():
    anomalies = [AnomalyTiming("payment-service", at(60), at(65.4)), AnomalyTiming("api-gateway", at(60), at(65.6))]
    assert detection_stage(anomalies) == pytest.approx([5.4, 5.6])


def test_alert_stages_correct_clock_offset_and_skip_late_notifications():
    alerts = [
        # database clock 2 s ahead: opened 0.3 s after the anomaly, Telegram 0.8 s later
        AlertTiming("payment-service", at(65), at(67.3), at(68.1)),
        # notified only 90 s after opening (escalation in old data): not a Telegram send time
        AlertTiming("api-gateway", at(65), at(67.4), at(157.4)),
        AlertTiming("order-service", at(65), at(67.5), None),           # MEDIUM: never notified
    ]
    opened, telegram, later = alert_stages(alerts, offset_s=2.0)
    assert opened == pytest.approx([0.3, 0.4, 0.5])
    assert telegram == pytest.approx([0.8])
    assert later == 1


def test_incident_chain_takes_first_of_each_step():
    incident = Incident("error_burst", at(9), at(129), ("payment-service",))
    anomalies = [AnomalyTiming("api-gateway", at(60), at(65.7)), AnomalyTiming("payment-service", at(60), at(65.5)),
                 AnomalyTiming("payment-service", at(600), at(605.0))]          # far after the incident: ignored
    alerts = [AlertTiming("payment-service", at(65.5), at(66.0), at(66.9)),
              AlertTiming("api-gateway", at(65.7), at(66.2), at(67.0))]
    [row] = incident_chain([incident], anomalies, alerts)
    assert (row["anomaly_s"], row["alert_s"], row["telegram_s"]) == (56.5, 57.0, 57.9)


def test_incident_chain_without_detection():
    incident = Incident("latency_spike", at(9), at(129), ("order-service",))
    [row] = incident_chain([incident], [], [])
    assert row["anomaly_s"] is None and row["alert_s"] is None and row["telegram_s"] is None


def test_feed_stages_groups_by_type():
    records = [{"type": "anomaly.created", "delay_s": 0.04}, {"type": "alert.created", "delay_s": 0.31},
               {"type": "anomaly.created", "delay_s": 0.06}, {"type": "anomaly.created", "delay_s": None}]
    assert feed_stages(records) == {"anomaly.created": [0.04, 0.06], "alert.created": [0.31]}