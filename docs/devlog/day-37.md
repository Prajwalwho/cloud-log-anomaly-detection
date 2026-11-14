# Day 37 — Logs page: search, request path, links from anomalies

## Done
- src/pages/Logs.tsx: search the stored log lines (GET /logs, Elasticsearch), newest first, 100 per page. Filters:
  full-text search on the message (all words required, submitted with Enter or the Search button), service, levels
  (several at once), request (trace ID). Everything is in the URL (`?q=&service=&level=&trace=&from=&to=&page=`).
- An explicit time window in the URL (`from` + `to`) replaces the chosen time range and is shown as a removable chip.
  The Anomalies page's "All logs of this minute" link uses it (`/logs?service=…&from=…&to=…`).
- src/components/logs/LogRow.tsx: one line per log event with millisecond time, level (errors and fatals marked with
  a coloured edge), service, message and endpoint / status (4xx amber, 5xx orange) / latency. A click expands every
  field, the metadata, and three actions: Follow this request, <service> around this moment (±1 min), Copy event ID.
- src/components/logs/TracePath.tsx: the request path — all lines of one trace ID, oldest first, with the time since
  the request started, the services it passed through, total time and whether it failed. Loaded over the last
  7 days, so a request is complete even when it lies outside the chosen range.
- src/hooks/useLogs.ts (search and trace), src/components/logs/LogFilters.tsx, src/lib/logFormat.ts
  (millisecond times, offsets), logs.css.

## Decisions
- No automatic reload on this page. Logs arrive thousands per minute, so reloading every 30 s or after every live
  event would move the list while someone reads or expands a line. The toolbar shows "as of <time>" and a Refresh
  button instead (disabled for a fixed time window, which does not change).
- Paging stops at 10,000 results, the Elasticsearch from/size limit the API enforces (api-contracts.md §3.3); the
  page says so and suggests narrowing the search.
- Following a request clears the text, level and service filters, so the list shows every line of the request.
- The search box keeps its text locally until submitted; the filter component is remounted when the URL's query
  changes (back / forward), so the box always shows the search in effect.

## Fix: the new folder was ignored by Git
- `git status` did not list src/components/logs/. The Vite template's frontend/.gitignore has the line `logs`, which
  ignores every folder named logs at any depth, so the page would have been committed without its components.
- Changed to `/logs` (only a logs folder at the top of frontend/). Checked with `git check-ignore -v`.

## Checked
- Preview with mocked API data at 1536 px: search, level chips, expanding a line, following a request (path with
  offsets, total time, success), the trace chip.