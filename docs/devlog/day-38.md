# Day 38 — Models page, Overview links, code splitting; Phase 9 complete

## Done
- src/pages/Models.tsx: the active model (name, version, algorithm, training date, threshold, training windows and
  runs, settings in words), a plain-language "How it decides", its evaluation (incidents detected, recall,
  precision and F1 on the fault run; false-alarm rate on the fault-free hour; minutes flagged and time to flag per
  injected fault), the operators' verdicts in the chosen range (real problems / false alarms / not reviewed, with
  a link to review), and all registered versions.
- src/lib/modelMetrics.ts: reads the stored evaluation (model_registry.metrics, written by train.py) into typed
  values, checking every field, plus names for scenarios and settings. src/hooks/useModels.ts.
- Overview: the numbers "Open alerts", "Anomalies" and "Log lines analysed" open their pages.
- Code splitting: App.tsx loads every page with React.lazy on first visit; Layout.tsx shows the shell with
  "Loading…" (Suspense) meanwhile. The charts library is now only loaded with the Overview.
- README: Dashboard section (pages, dev server, lint/build), pipeline table with the dashboard, port 5173,
  troubleshooting (API not reachable, Logs empty without ingestion, npm in the wrong folder, ignored folders),
  status and roadmap (Phase 9 done).

## Decisions
- The Models page shows the evaluation stored with the model at registration instead of recomputing anything: it
  is the same evidence that justified activating the model (Phase 6).
- "Flagged after" on the Models page comes from a replay (window end minus fault start); the page says that live
  detection adds the 5 s grace period, about half a minute in total (real-time run: 32–33 s).
- Operator verdicts are counted over all anomalies in the range, not per model, because only one model is active
  at a time; per-model feedback would need a model filter on GET /anomalies.
- Pages that share list styles import anomalies.css themselves, so they keep working when loaded on their own
  chunk.

## Phase 9 summary (Days 33–38)
- Observatory design: dark "deep space" theme, natural severity colours, service colours distinct from severity.
- One WebSocket for the app with reconnect and reload after reconnect; one time range for all pages; filters and
  selection in the URL on every page.
- Overview (constellation, readout, heatmap, error rate, anomaly timeline, live signals), Anomalies (filters,
  detail, sample logs, feedback), Alerts (status groups, timeline, story, acknowledge / resolve), Logs (search,
  request path, links from anomalies), Models (evaluation, verdicts, versions).
- Bugs found through the dashboard and fixed: idle windows shown as anomalous (API statistics, Day 34), a lint rule
  on the error-rate chart (Day 35), the logs folder ignored by Git (Day 37).
- Open points for Phase 10: per-model feedback, partial-minute volume drops at the start and end of traffic,
  root-cause hints when the gateway reports a downstream failure.

## Checked
- Preview with the real model metadata (models/metadata/live-pca-1.0.0.json, 1.1.0.json) at 1536 px.