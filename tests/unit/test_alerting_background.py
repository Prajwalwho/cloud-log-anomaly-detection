"""Telegram messages are sent in the background, in order, without holding up the alerting loop (Day 43)."""
import time

from backend.alerting.background import BackgroundSender


class SlowNotifier:
    enabled = True

    def __init__(self, delay_s: float = 0.2, fail: bool = False) -> None:
        self.delay_s, self.fail = delay_s, fail
        self.texts: list[str] = []

    def send(self, text: str) -> bool:
        time.sleep(self.delay_s)
        self.texts.append(text.splitlines()[0])
        return not self.fail


def alert(alert_id: str = "a1", service: str = "payment-service", severity: str = "HIGH") -> dict:
    return {"id": alert_id, "service": service, "severity": severity, "title": f"Error rate increase in {service}",
            "message": "error rate 14.7%", "first_seen_at": "2026-11-16T07:18:05.000Z",
            "last_seen_at": "2026-11-16T07:18:05.000Z", "occurrence_count": 1}


def test_submit_does_not_wait_for_telegram():
    sent = []
    sender = BackgroundSender(SlowNotifier(delay_s=0.3), lambda kind, a: sent.append((kind, a["id"])))
    began = time.monotonic()
    for i in range(3):
        sender.submit("new", alert(f"a{i}"))
    assert time.monotonic() - began < 0.1            # three sends of 0.3 s each did not block
    assert sender.close() == 0
    assert sent == [("new", "a0"), ("new", "a1"), ("new", "a2")]


def test_messages_of_one_alert_keep_their_order():
    notifier = SlowNotifier(delay_s=0.01)
    kinds = []
    sender = BackgroundSender(notifier, lambda kind, a: kinds.append(kind))
    sender.submit("new", alert(severity="HIGH"))
    sender.submit("escalated", alert(severity="CRITICAL"))
    sender.submit("resolved", alert(severity="CRITICAL"))
    sender.close()
    assert kinds == ["new", "escalated", "resolved"]
    assert notifier.texts[1].startswith("\u2B06\uFE0F Escalated to CRITICAL")


def test_alert_counts_as_pending_until_its_message_is_handled():
    sender = BackgroundSender(SlowNotifier(delay_s=0.2), lambda kind, a: None)
    sender.submit("new", alert("a1"))
    assert sender.is_pending("a1") and not sender.is_pending("a2")
    sender.close()
    assert not sender.is_pending("a1")


def test_failed_send_is_not_reported_and_clears_pending():
    sent = []
    sender = BackgroundSender(SlowNotifier(delay_s=0.01, fail=True), lambda kind, a: sent.append(kind))
    sender.submit("new", alert("a1"))
    sender.close()
    assert sent == [] and not sender.is_pending("a1")      # the next update of the alert will try again


def test_error_in_callback_does_not_stop_the_worker(capsys):
    calls = []

    def on_sent(kind, a):
        calls.append(a["id"])
        if a["id"] == "a1":
            raise RuntimeError("database down")

    sender = BackgroundSender(SlowNotifier(delay_s=0.01), on_sent)
    sender.submit("new", alert("a1"))
    sender.submit("new", alert("a2"))
    sender.close()
    assert calls == ["a1", "a2"]
    assert "notification for payment-service failed: RuntimeError" in capsys.readouterr().out


def test_full_queue_drops_instead_of_blocking():
    sender = BackgroundSender(SlowNotifier(delay_s=0.3), lambda kind, a: None, max_queue=1)
    for i in range(4):
        sender.submit("new", alert(f"a{i}"))
    assert sender.dropped >= 1
    sender.close()