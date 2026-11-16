# Day 47 — Docs: Architecture and the reference pages; README

## Written
- `docs/guide/architecture.md`: the parts and the data flow (diagram, table of what each part reads and writes),
  where data lives (Kafka topics with partitions, keys and retention; the five PostgreSQL tables; the daily
  Elasticsearch indices), one fault end to end with the measured times, the design decisions and their reasons,
  what happens when each part stops, limits, links to the design documents.
- `docs/guide/api-reference.md`: rules for every endpoint (times, range, paging, value lists, errors, CORS), every
  endpoint with its parameters and an example answer, allowed alert status changes, the live feed's messages, ping
  and disconnect rule.
- `docs/guide/configuration.md`: how `.env` is read, every setting of every service with its default, the
  command-line options of the services, the generator (with the five scenarios) and training, and the scripts.
- `docs/guide/glossary.md`: every term in one line, with links to the full explanations.
- `docs/guide/faq.md`: questions about detection, using the system and small problems (the README's
  troubleshooting rows that were not yet in the guide).
- Docs sidebar: Architecture under **Learn**, a new **Reference** section. "Next" links now lead through the guide
  (Getting started, How detection works, Using the dashboard, Operations).
- `README.md` rewritten as the front page: what it does, the Phase 10 results, the guide, a short quick start,
  stack, research results, structure, tests, roadmap (Phase 10 done, Phase 11 in progress). Details that are now in
  the guide (dashboard, API, alerts, troubleshooting) were moved there.

## Corrected while checking
- `using-the-dashboard.md`: the readout's *Open alerts* counts only alerts with the status OPEN, at any time
  (`stats/summary`); the galaxy uses active alerts (open or acknowledged) of the last seven days; the galaxy shows
  the alert's title under the service, not a ring; the alert detail shows *Sent to Telegram*, *Not needed* or
  *Not sent*, not a time.
- `concepts.md`: `alerts.events` keeps messages 7 days (created by `common/kafka_topics.py`), not Kafka's default.

## Checked against the code
- Endpoints, parameters, limits and errors (`api/app/routers/`, `params.py`, `main.py`); response fields
  (`schemas.py`); anomaly summary fields (`detection/store.py`); alert times are detection times and the message is
  the latest reasons (`alerting/store.py`); model `parameters` and `metrics` (`train.py`, model metadata); settings
  and defaults (each service's `config.py`, `.env.example`, `docker-compose.yml`); command-line options (argparse in
  each program); scenarios (`log_generator/scenarios.py`); severity limits (`scoring/severity.py`); galaxy colours
  (`Constellation.tsx`, `useOverview.ts`).
- Every link and heading anchor in the guide and the README checked with a script.

## Next
- Day 48: study guide (how to learn and present the project) and the final check.