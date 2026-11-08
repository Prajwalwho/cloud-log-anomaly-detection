# Day 1 — Data contracts

## Done
- Added .gitattributes to normalize line endings (LF in repo, CRLF for .ps1).
- Wrote docs/design/contracts.md: log event schema, validation rules, Kafka topics, and message formats for logs.raw, logs.deadletter and anomalies.detected, plus the ground-truth record format.

## Decisions
- All timestamps in UTC; anomaly scores normalized to 0–1.
- Kafka message key = service, so each service's logs stay ordered (needed for windowing).
- Ground-truth labels kept out of the log stream, in a separate file, to prevent label leakage.
- Invalid messages go to a dead-letter topic rather than being dropped.

## Problems faced
- LF/CRLF warnings from Git on Windows; fixed with .gitattributes.