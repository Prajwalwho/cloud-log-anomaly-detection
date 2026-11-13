# Day 33 — Dashboard foundations and the Observatory design (Phase 9 starts)

## Done
- Vite dev server forwards /api (REST and WebSocket) to FastAPI: one origin, no CORS.
- src/types/api.ts (types from api-contracts.md 1.2), src/services/api.ts (typed client, readable errors;
  502/503/504 from the dev proxy reported as "backend not reachable").
- src/live/: one WebSocket for the whole app, automatic reconnect (1 s doubling to 30 s), connectionCount so pages
  reload after a reconnect (events are not replayed, api-contracts §4).
- src/lib/: time range (15 min to 7 days) chosen once in the top bar; formatting (UTC -> local time only in the
  dashboard, contracts §1).
- Layout: sidebar with backend-health and live-feed signals; Overview with the constellation, readout, severity
  spectrum and live signal list. Other pages are placeholders (Days 35–38).
- Removed empty placeholders (App.css, types/alert.ts, anomaly.ts, log.ts).
- lint and build (TypeScript type check) pass.

## Design: "Observatory"
- Concept: monitoring as watching the sky. Services are stars; size = log volume, colour = health (starlight ->
  gold -> amber -> red), halo = open alert, lines = calls from the gateway, a flare = a live anomaly.
- Palette: deep space blue-black, faint violet and teal nebula, static starfield; muted natural severity colours,
  no neon. Type: Fraunces (headings, numbers) and Instrument Sans (interface).
- Motion only for events (flare) and the live signal; respects reduced-motion settings.
- Every visual is paired with words (e.g. "1.7k logs, 20.5% errors"); selecting a star opens that service's anomalies.

## Live check
- 1 hour (after an error burst): payment-service red (CRITICAL alert, 20.5% errors), api-gateway amber (HIGH alert,
  4.4%), other services calm; 9 anomalies (3 critical, 4 high, 2 medium), 2 open alerts, 25.6k log lines.
- 24 hours: 55 anomalies (15 critical, 29 high, 10 medium, 1 low), 134.5k log lines in 1,755 windows.
- Backend down: "Backend unreachable" / "Reconnecting", automatic recovery when the API returns.

## Problems faced
- npm run dev in the project root (package.json is in frontend/).
- File mix-ups: SeverityBar code pasted into SeverityBadge.tsx; timeRangeProvider.tsx with a lowercase t
  (Windows ignores case, TypeScript does not); fixed with a two-step rename.
- The API was not running during the first look (ECONNREFUSED in the proxy log; dashboard showed "HTTP 502",
  now a clear message).
- CSS: `.readout div` also styled the divs inside the severity bar (stray lines, indent); fixed with `.readout > div`.
  The sidebar footer scrolled off screen; the sidebar is now sticky at full height.