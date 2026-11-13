# Day 32 — Auto-resolve and Telegram notifications (Phase 8 complete)

## Done
- backend/alerting/notifier.py: Telegram Bot API (standard library only); messages for new, escalated and resolved
  alerts; the bot token is read from .env and never printed.
- rules.py: notification_kind (when to notify).
- store.py: previous severity in the outcome, mark_notified, resolve_quiet (auto-resolve after 5 minutes quiet).
- service.py: notifications, periodic auto-resolve, resolved alerts published to alerts.events.
- config.py: TELEGRAM_BOT_TOKEN (secret), TELEGRAM_CHAT_ID, notify_min_severity HIGH, resolve settings.
- scripts/telegram_setup.py: shows which bot the token belongs to and the chat id; --send sends a test message.
- scripts/watch_live.py: reports a server-side close instead of a traceback.
- tests: test_alerting_notify.py (5), test_alerting_lifecycle_integration.py (2); 51 API/alerting tests pass.
- contracts.md 1.2 (alerts.events, alert lifecycle, API consumption without a balanced group),
  api-contracts.md 1.2.

## Notification rules
| Event | Message |
|---|---|
| Alert opens as HIGH/CRITICAL, or a MEDIUM alert reaches HIGH | one message |
| Notified alert escalates to CRITICAL | "Escalated" |
| Further anomalies at the same severity | none |
| Notified alert resolves | "Resolved" |
- A failed send leaves notification_sent false, so the next update retries.

## Live run (run-20261113-191147, error_burst from 19:12:47 UTC)
- Telegram, in order: HIGH payment-service (error rate 7.7%), HIGH api-gateway (MEDIUM -> HIGH), Escalated to
  CRITICAL payment-service (38.9%), Resolved api-gateway (19:13–19:15 UTC, 3 anomalous minutes), Resolved
  payment-service (19:13–19:16 UTC, 4 anomalous minutes).
- 7 anomalies -> 2 alerts -> 5 messages covering start, escalation and end; 5 further alert updates sent no
  message (about 11 messages without grouping and these rules).
- First message 19 s after fault start (13 s of fault in the 19:12 window gave 7.7% errors).
- Auto-resolve ~5.5 min after the last anomaly (5 min quiet + 30-s check interval).
- Alerting summary: created 2, updated 5, resolved 2, unknown 1 (the integration test's marked message, no anomaly
  in the database), Telegram sent 5, failed 0. Detection: 18,075 events, 0 late, 7 anomalies published.

## Observations
- A MEDIUM payment anomaly at 19:15 ("1 new message type") after the burst ended kept the alert open one minute
  longer: an after-effect of the fault.
- Stopping the API closed the WebSocket with code 1012; watch_live.py crashed on it (fixed). The dashboard must
  reconnect and reload (api-contracts §4).

## Problems faced
- telegram_setup.py first found no messages; a diagnostic version (getMe + update count) found the chat on the
  next attempt after a fresh message.
- The chat id was typed but not saved in .env; checked with Select-String.
- A terminal command was accidentally typed into telegram_setup.py (unsaved); undone before committing.
- Decision: the bot token appeared in screenshots; the owner chose to keep it (low-risk development bot).