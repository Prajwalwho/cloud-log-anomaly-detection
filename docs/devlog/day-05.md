# Day 5 — Setup and start scripts, README

## Done
- scripts/setup.ps1: checks prerequisites, creates the Python 3.12 venv, installs Python and frontend
  dependencies, creates .env, pulls Docker images. Safe to run repeatedly.
- scripts/start.ps1 with actions: up, down, status, logs, test, reset.
  `up` waits for container health checks and kafka-init, then runs the smoke test automatically.
- README.md: overview, data flow, stack, quick start, commands, ports, structure, roadmap, troubleshooting.
- Verified: setup kept existing venv and .env; full down/up cycle healthy; smoke test 3/3 OK; reset cancels unless "yes" is typed.
- Phase 2 (infrastructure) complete.

## Decisions
- One command per action instead of long docker compose commands.
- `start.ps1 up` replaces fixed sleeps with real health polling (no more timing failures in the smoke test).
- `reset` requires typing "yes" because it deletes all data volumes.
- Scripts check $LASTEXITCODE after every external command, so failures stop the script with a clear message.

## Problems faced
- `start.ps1 logs` follows logs continuously and looks frozen when the service is idle; stop it with Ctrl+C.
- Commands meant to be run one at a time were pasted together; the logs command blocked the rest until Ctrl+C.