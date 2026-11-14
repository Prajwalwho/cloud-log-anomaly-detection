# Day 36 — Alerts page: status groups, timeline, acknowledge and resolve

## Done
- src/pages/Alerts.tsx: alerts whose last anomaly falls in the chosen time range, newest first, 50 per page.
  Status tabs Active (open + acknowledged, the default), Resolved and All, each with its count; service and severity
  filters. Filters, page and selection are in the URL (`?status=&service=&severity=&page=&id=`), so the "Open the
  alert" link on the Anomalies page (`/alerts?id=…`) opens the alert directly.
- Each row: status (an open alert's dot breathes), service, severity, title, and a line with the number of anomalous
  minutes, first–last time and the latest reasons; a paper-plane icon when Telegram was notified.
- src/components/alerts/AlertDetail.tsx: title and reasons; a timeline; how long it has been open (or lasted),
  anomalous minutes, last anomaly; Acknowledge (with the operator's name, remembered in this browser) and Resolve
  (PATCH /alerts/{id}); "What happened": opened, each escalation, acknowledged by whom, resolved after how many quiet
  minutes; Telegram status; the anomalies of the alert, each linking to the Anomalies page.
- src/components/alerts/AlertTimeline.tsx: the alert on one line, one dot per anomaly (colour = severity, size grows
  with severity), a mark when acknowledged, a ring when resolved; an active alert continues dashed to now.
- src/lib/alertEvents.ts: builds the alert's story. Escalations are not stored as separate rows; they follow from the
  severities of the alert's anomalies in time order (the alert's severity is the highest so far, contracts.md §5.4).
- src/hooks/useAlerts.ts (list, status counts, detail), src/hooks/useNow.ts (a clock that keeps render pure),
  src/components/alerts/AlertFilters.tsx, StatusPill.tsx, alerts.css.
- src/lib/format.ts: formatDuration, STATUS_COLOURS, STATUS_NAMES.
- Alerts that open or change while the page is open (alert.created / alert.updated on the WebSocket) glow briefly
  after the reload. A change made from the dashboard is also pushed to every other open dashboard by the API.

## Decisions
- The resolve line states a fact rather than a guess: "Resolved after N min without new anomalies"
  (resolved_at − last_seen_at). Who resolved an alert (the auto-resolver or an operator) is not stored.
- Telegram status: "Sent", "Not needed" for low and medium (NOTIFY_MIN_SEVERITY is HIGH), and for high/critical
  alerts that were not sent, a hint to check the Telegram settings.
- The Alerts page reuses the list / detail styles from anomalies.css and adds alerts.css for what is specific.
- The time range filters on last_seen_at, as the API does (api-contracts.md §3.8).

## Checked
- Preview with mocked API data at 1536 px: status tabs and counts, selecting, acknowledge with a name (the button
  disappears and the story gains "Acknowledged by …"), the All tab with a resolved alert.