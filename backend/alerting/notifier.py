"""
Telegram notifications for the alerting service (Bot API sendMessage over HTTPS, standard library only).

The bot token is a secret: it is read from .env (TELEGRAM_BOT_TOKEN), used only in the request URL and never
printed. Without token and chat id, notifications are disabled and the service says what it would have sent.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

TELEGRAM_API = "https://api.telegram.org"
ICONS = {"CRITICAL": "\U0001F534", "HIGH": "\U0001F7E0", "MEDIUM": "\U0001F7E1", "LOW": "\u26AA"}
RESOLVED_ICON = "\u2705"
ESCALATED_ICON = "\u2B06\uFE0F"


def readable_time(iso: str | None) -> str:
    """'2026-11-13T17:48:05.706Z' -> '2026-11-13 17:48:05 UTC'."""
    return f"{iso[:10]} {iso[11:19]} UTC" if iso else "-"


def format_message(kind: str, alert: dict) -> str:
    icon = ICONS.get(alert["severity"], "")
    if kind == "new":
        head = f"{icon} {alert['severity']} alert: {alert['title']}"
    elif kind == "escalated":
        head = f"{ESCALATED_ICON} Escalated to {alert['severity']}: {alert['title']}"
    elif kind == "resolved":
        head = f"{RESOLVED_ICON} Resolved: {alert['title']}"
    else:
        raise ValueError(f"unknown notification kind: {kind}")
    lines = [head, f"Service: {alert['service']}"]
    if kind == "resolved":
        lines.append(f"Active {readable_time(alert['first_seen_at'])} to {readable_time(alert['last_seen_at'])}, "
                     f"{alert['occurrence_count']} anomalous minute(s)")
    else:
        if alert.get("message"):
            lines.append(f"Why: {alert['message']}")
        lines.append(f"First seen: {readable_time(alert['first_seen_at'])}")
        lines.append(f"Anomalous minutes so far: {alert['occurrence_count']}")
    lines.append(f"Alert id: {alert['id']}")
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, token: str | None, chat_id: str | None, timeout_s: float = 10.0) -> None:
        self._token = token
        self.chat_id = chat_id
        self.timeout_s = timeout_s
        self.sent = 0
        self.failed = 0

    @property
    def enabled(self) -> bool:
        return bool(self._token and self.chat_id)

    def send(self, text: str) -> bool:
        """True if Telegram accepted the message. Never raises; never prints the token."""
        if not self.enabled:
            print(f"  [notifications disabled] would send: {text.splitlines()[0].encode('ascii', 'ignore').decode()}")
            return False
        body = json.dumps({"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True}).encode()
        request = urllib.request.Request(f"{TELEGRAM_API}/bot{self._token}/sendMessage", data=body,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                ok = json.loads(response.read()).get("ok") is True
        except urllib.error.HTTPError as exc:
            print(f"  [WARN] Telegram rejected the message: HTTP {exc.code}")
            ok = False
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"  [WARN] Telegram not reachable ({type(exc).__name__})")
            ok = False
        if ok:
            self.sent += 1
        else:
            self.failed += 1
        return ok