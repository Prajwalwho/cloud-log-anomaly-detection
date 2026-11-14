# Day 34 — Overview charts: heatmap, error rate, anomaly timeline

## Done
- src/lib/buckets.ts: time buckets matching the API's date_bin (gaps shown as gaps), local-time labels.
- src/hooks/useReloadKey.ts: one reload trigger (every 30 s, 1.5 s after live events, after a reconnect);
  useOverview.ts uses it; new useOverviewSeries.ts loads anomaly score, error rate and anomaly count at the
  bucket size of the chosen range (1 min / 5 min / 1 h).
- src/components/charts/: ActivityHeatmap (services x time, coloured by highest anomaly score: dark blue normal,
  gold at the threshold, amber to red more anomalous, hover for values), ErrorRateChart (line per service, round
  5%/10% axis ticks), AnomalyBars (anomalous minutes stacked by service), SeriesLegend, theme (service colours kept
  distinct from severity colours), charts.css.
- Overview: sky and readout, then heatmap, error rate and anomaly timeline, then live signals.
- API fix (backend/api/app/routers/stats.py): idle windows excluded from statistics; test added
  (test_idle_windows_are_ignored); 9 statistics/alert tests pass. lint and build pass.

## Bug found through the dashboard: idle minutes looked anomalous
- After the generator stopped, every service glowed amber in the heatmap (1 hour: 01:41–01:46; 24 hours: almost
  every hour), including healthy auth, order and inventory.
- Cause: with no traffic at all, the detection service still stores a window per service (log_count 0,
  is_anomaly false, Day 24 "no traffic" rule) with the model's raw score, which is high for an empty window. The
  heatmap shows the highest score per cell.
- Fix in the API statistics: windows that are empty and not flagged are ignored; empty and flagged windows (a silent
  service while others have traffic) still count. "Windows analysed" no longer counts idle minutes.
- After the fix: 1 hour shows warm cells only for api-gateway and payment-service during the burst; 24 hours shows
  which services were affected in which hours (all five during the Day 26 all-scenario run, only payment and gateway
  during the error-burst runs).

## Observations
- Recharts roughly doubled the bundle (222 kB compressed; Vite warns above 500 kB uncompressed). Code splitting per
  page is planned for Day 38.
- The heatmap colours by anomaly score (how unusual), not by severity (how harmful); severity is shown in the
  spectrum bar and on each anomaly.