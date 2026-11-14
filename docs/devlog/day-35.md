# Day 35 — Anomalies page: filters, list, detail with log lines and feedback

## Done
- src/pages/Anomalies.tsx: every anomaly in the chosen time range, newest first, 50 per page. Filters, page and the
  selected anomaly are kept in the URL (`?service=&severity=&feedback=&page=&id=`), so a view can be bookmarked and
  the Overview constellation's link (`/anomalies?service=…`) opens a filtered list.
- src/components/anomalies/AnomalyFilters.tsx: service, severity chips (several at once, each with its count in the
  range) and review state (all / not reviewed / confirmed / false positive).
- src/components/anomalies/ScoreGauge.tsx: score meter per row and a full gauge in the detail panel. The normalised
  score is 0.5 at the threshold, so the threshold mark sits in the middle; the detail also shows the raw score as a
  multiple of the threshold (raw_score / threshold).
- src/components/anomalies/AnomalyDetail.tsx: why the minute was flagged (reasons, no-logs rule), its numbers (log
  lines, error and warning rate, average and p95 latency, new message types), the operator's verdict ("Real problem" /
  "False alarm", pressing again clears it; PATCH /anomalies/{id}/feedback), the alert it belongs to, the model, and
  the sampled log lines from Elasticsearch (errors first), with a message when Elasticsearch is unavailable or the
  lines have expired.
- src/hooks/useAnomalies.ts: list + severity counts (one request per severity, size 1, ignoring the severity
  filter) and the detail; both reload with useReloadKey and keep the previous result while loading.
- src/hooks/useServiceNames.ts: service list for the filter, in topology order.
- src/lib/format.ts: formatClock, formatShortDateTime, formatWindow, formatLatency, LEVEL_COLOURS.
- New anomalies arriving over the WebSocket glow for 8 s in the list after the reload.
- Layout: list and a sticky detail panel side by side; below 1150 px the detail moves above the list.

## Fix: lint error in the Day 34 error-rate chart
- `npm run lint` failed with react-hooks/immutability in ErrorRateChart.tsx: the highest error rate (`dataMax`) was
  updated inside the `.map()` that builds the chart rows ("Cannot reassign variable after render completes").
- Fix: build the rows first, then compute the maximum with `reduce`. Same result, no variable changed inside the
  callback. lint and build pass.

## Decisions
- Verdict labels say "Real problem" / "False alarm" rather than CONFIRMED / FALSE_POSITIVE, because the dashboard is
  read by operators; the stored values follow the contract.
- The list shows the minute (window start); the full window and detection time are in the row tooltip and the
  detail. With 12-hour clocks the full window made the table wider than its panel.
- Severity counts use `total` from size-1 requests instead of /stats/summary, because the summary is not filtered by
  service or review state.

## Links prepared for later pages
- "Open the alert" → `/alerts?id=…` (Day 36).
- "All logs of this minute" → `/logs?service=…&from=…&to=…` (Day 37).

## Checked
- Preview with mocked API data at 1440 px and 390 px: filters, selection, feedback toggle, pagination, empty states.
- lint and build pass.