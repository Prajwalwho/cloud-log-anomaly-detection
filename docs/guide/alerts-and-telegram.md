# Alerts and Telegram

Anomalies say *which minute* of *which service* was unusual. An operator does not want one message per minute: they want to know that *payment-service has a problem*, how bad it is, and when it is over. That is what the alerting service does. Its code is in `backend/alerting/`.

## From anomalies to alerts

The alerting service reads every anomaly from the Kafka topic `anomalies.detected` and decides, one anomaly at a time:

| Situation | What happens |
|---|---|
| The service already has an active alert whose last anomaly is at most 5 minutes away | The anomaly **joins** that alert: one more anomalous minute, its severity becomes the highest seen, its message the newest reasons |
| No such alert, and the anomaly is MEDIUM or higher | A **new alert** is opened |
| No such alert, and the anomaly is LOW | **No alert**: a LOW anomaly alone is not worth anyone's attention |
| The anomaly already has an alert | Nothing changes: Kafka may deliver a message twice, and this makes repeats harmless |

Alerts are always per service. A cascading failure across four services gives four alerts, one per affected service, which is what an operator needs to see where it hurts.

### Titles

The alert's title comes from the strongest reason of its first anomaly:

| Strongest reason | Title |
|---|---|
| `no logs (…)` | *auth-service stopped logging* |
| `error rate …` | *Error rate increase in payment-service* |
| `log volume …% of normal` | *Log volume drop in order-service* |
| `p95 latency …` | *Latency increase in order-service* |
| `… new message type(s)` | *New message type in inventory-service* |
| anything else | *Unusual log pattern in api-gateway* |

## The life of an alert

```text
          anomaly (MEDIUM or higher)
                    │
                    ▼
   ┌──────────►  OPEN  ──── operator: Acknowledge ───► ACKNOWLEDGED
   │                │                                       │
   │ more anomalies │ 5 minutes without new anomalies,      │
   │ (join, may     │ or operator: Resolve                  │
   │  escalate)     ▼                                       │
   └──────────── RESOLVED ◄─────────────────────────────────┘
```

- **OPEN**: something is wrong and nobody has said they are on it.
- **ACKNOWLEDGED**: an operator has seen it (their name is stored). It still collects anomalies and still resolves by itself.
- **RESOLVED**: no new anomalies for 5 minutes (checked every 30 seconds), or an operator marked it fixed. A new anomaly after that opens a new alert.

A resolved alert keeps its whole story: when it opened, each escalation, who acknowledged it, and how it was resolved. The Alerts page shows this as a timeline.

**In the live runs:** every alert resolved by itself, 5.1 to 6.4 minutes after its incident ended (median about 6). The last anomaly often comes from the minute just after the fault, then come 5 quiet minutes, then up to 30 seconds until the next check.

## Telegram notifications

An operator is told on their phone only about what matters, and at most three times per alert:

| When | Message |
|---|---|
| The alert reaches **HIGH** (when it opens, or later) | 🟠 or 🔴 *HIGH / CRITICAL alert: <title>* with the reasons, first seen, anomalous minutes so far, alert id |
| A notified alert becomes **CRITICAL** | ⬆️ *Escalated to CRITICAL: <title>* |
| A notified alert is **resolved automatically** | ✅ *Resolved: <title>*, when it was active and for how many anomalous minutes |

An example of the first message:

```text
🟠 HIGH alert: Error rate increase in payment-service
Service: payment-service
Why: error rate 14.7%
First seen: 2026-11-16 07:18:05 UTC
Anomalous minutes so far: 1
Alert id: 3f2c…
```

MEDIUM alerts appear on the dashboard only. A MEDIUM alert that later reaches HIGH sends its first message then. An alert resolved by an operator on the dashboard sends no message: the operator already knows.

### Sending without waiting

Messages are sent by a background thread, one after another, in the order they were created, so an alert's *escalated* message never arrives before its first message. Storing and showing alerts never waits for Telegram: when four services fail in the same minute, all four alerts appear on the dashboard within about a second, even if Telegram is slow.

If a message cannot be sent (no internet, Telegram unreachable), the alert is not marked as notified, and the next update of the alert tries again. Sending one message usually takes about a second; once in the tests Telegram itself took about 14 seconds to answer.

## Setting up Telegram

You need a Telegram bot (free) and your chat id. This is done once.

1. In Telegram, open **@BotFather** (it has a blue verified tick), send `/newbot`, choose a display name and a username ending in `bot`. BotFather replies with a **token**.
2. Open your new bot and send it any message, for example *hello*. A bot can only write to people who have written to it first.
3. Open `.env` in the project folder and fill in the token:

   ```text
   TELEGRAM_BOT_TOKEN=<your token>
   TELEGRAM_CHAT_ID=
   ```

4. Find your chat id. The script reads the bot's latest messages and prints the chat id; put it after `TELEGRAM_CHAT_ID=` and save `.env`:

   ```powershell
   python scripts/telegram_setup.py
   ```

5. Send yourself a test message:

   ```powershell
   python scripts/telegram_setup.py --send
   ```

6. Restart the alerting service. Its start-up line now says `Telegram: on (HIGH and above)`.

> [!CAUTION]
> The token controls your bot. Keep it only in `.env`, which Git ignores (check with `git check-ignore .env`). Never paste it into code, screenshots or chat. If it leaks, send `/revoke` to @BotFather and put the new token in `.env`.

### Turning Telegram off

- **For one run** (for example a load test): start the service with `--no-telegram`. Alerts are stored and shown as usual; the service prints what it would have sent.

  ```powershell
  python -m backend.alerting.service --no-telegram
  ```

- **Permanently:** leave `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` empty in `.env`.

> [!NOTE]
> In PowerShell, `$env:TELEGRAM_CHAT_ID=""` does not empty the variable: it removes it, and the value from `.env` is used again. Use `--no-telegram` instead.

## Settings

All in `.env`; the defaults are shown. Restart the alerting service after a change.

| Setting | Default | Meaning |
|---|---|---|
| `ALERT_GROUP_GAP_S` | `300` | An anomaly joins an alert whose last anomaly is at most this many seconds away |
| `ALERT_MIN_SEVERITY` | `MEDIUM` | The lowest severity that opens a new alert |
| `ALERT_RESOLVE_AFTER_S` | `300` | Seconds without new anomalies before an alert is resolved automatically |
| `ALERT_RESOLVE_CHECK_S` | `30` | How often the service looks for quiet alerts |
| `NOTIFY_MIN_SEVERITY` | `HIGH` | The lowest severity that sends a Telegram message |
| `TELEGRAM_BOT_TOKEN` | empty | The bot's token (secret) |
| `TELEGRAM_CHAT_ID` | empty | Where the messages go |

## Acknowledging and resolving

On the **Alerts** page, open an alert, type your name, and press **Acknowledge** or **Resolve**. The same works through the API:

```text
PATCH http://localhost:8000/api/v1/alerts/<id>
{"status": "ACKNOWLEDGED", "acknowledged_by": "your name"}
```

Every change is published on the live feed, so every open dashboard updates at once.

## Important to know

- **Start the alerting service before the traffic.** A new alerting service (a new consumer group) starts at the end of the topic and only sees anomalies from after its start. After that, it resumes where it stopped.
- **Run one alerting service** with Telegram on. Two copies would share the anomalies between them; only one of them may be set up to notify.
- **An alert is not an incident.** One fault usually gives one alert per affected service; in the live runs, 2.5 alerts per incident on average.

## Next

- [Operations](operations.md): running, checking and cleaning up the system.