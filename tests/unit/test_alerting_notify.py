"""When to notify and what the messages say (no Telegram needed)."""
import pytest

from backend.alerting.notifier import TelegramNotifier, format_message
from backend.alerting.rules import notification_kind

ALERT = {"id": "a1", "service": "payment-service", "severity": "CRITICAL",
         "title": "Error rate increase in payment-service", "message": "error rate 39.9%",
         "first_seen_at": "2026-11-13T17:48:05.706Z", "last_seen_at": "2026-11-13T17:50:05.602Z",
         "occurrence_count": 3}


def test_first_message_when_an_alert_reaches_high():
    assert notification_kind("created", "HIGH", None, notified=False) == "new"
    assert notification_kind("created", "MEDIUM", None, notified=False) is None
    assert notification_kind("updated", "HIGH", "MEDIUM", notified=False) == "new"     # escalated into HIGH


def test_no_repeats_but_escalation_to_critical_is_announced():
    assert notification_kind("updated", "HIGH", "HIGH", notified=True) is None
    assert notification_kind("updated", "CRITICAL", "CRITICAL", notified=True) is None
    assert notification_kind("updated", "CRITICAL", "HIGH", notified=True) == "escalated"


def test_other_outcomes_never_notify():
    for result in ("duplicate", "unknown", "below_threshold"):
        assert notification_kind(result, "CRITICAL", None, notified=False) is None


def test_messages():
    new = format_message("new", ALERT)
    assert "CRITICAL alert: Error rate increase in payment-service" in new
    assert "Why: error rate 39.9%" in new and "2026-11-13 17:48:05 UTC" in new
    resolved = format_message("resolved", ALERT)
    assert "Resolved: Error rate increase in payment-service" in resolved and "3 anomalous minute(s)" in resolved
    assert "Escalated to CRITICAL" in format_message("escalated", ALERT)
    with pytest.raises(ValueError):
        format_message("other", ALERT)


def test_disabled_notifier_never_sends():
    notifier = TelegramNotifier(token=None, chat_id=None)
    assert not notifier.enabled
    assert notifier.send("x") is False