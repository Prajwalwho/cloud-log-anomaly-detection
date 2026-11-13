"""Alerting rules without a database."""
from backend.alerting.rules import max_severity, opens_alert, title_for


def test_severity_escalates_never_drops():
    assert max_severity("HIGH", "CRITICAL") == "CRITICAL"
    assert max_severity("CRITICAL", "MEDIUM") == "CRITICAL"


def test_low_anomalies_never_open_alerts_by_default():
    assert not opens_alert("LOW", "MEDIUM")
    assert opens_alert("MEDIUM", "MEDIUM") and opens_alert("CRITICAL", "MEDIUM")


def test_titles_follow_the_strongest_reason():
    assert title_for("payment-service", ["error rate 39.3%"]) == "Error rate increase in payment-service"
    assert title_for("auth-service", ["no logs (normally ~805 per minute)"], "no_logs") == "auth-service stopped logging"
    assert title_for("order-service", ["p95 latency 343 ms (5.79x normal)"]) == "Latency increase in order-service"
    assert title_for("order-service", ["log volume 1% of normal (6 vs ~483)"]) == "Log volume drop in order-service"
    assert title_for("inventory-service", ["error rate 7.3%", "1 new message type(s)"]).startswith("Error rate")
    assert title_for("api-gateway", ["unusual log pattern (no single signal above its limit)"]) == \
        "Unusual log pattern in api-gateway"