# Day 3 — Kafka and PostgreSQL in Docker

## Done
- docker-compose.yml with Kafka 3.9 (KRaft, single broker) and PostgreSQL 16, with healthchecks.
- kafka-init one-shot service creates logs.raw (3 partitions, 24h), logs.deadletter and anomalies.detected (1 partition, 7 days).
- Postgres runs init.sql automatically; 5 tables and 5 seeded services verified.
- .env.example with database and Kafka settings.
- scripts/smoke_test.py: checks topics, Kafka produce/consume round trip, and database tables from the host.

## Decisions
- KRaft mode instead of Zookeeper (simpler; Zookeeper is deprecated in recent Kafka).
- Two listeners: localhost:9092 for host processes, kafka:29092 for containers.
- Topic auto-creation disabled; topics created explicitly per contracts.md.
- Kafka data not persisted in development; PostgreSQL data persisted in a named volume.
- Docker PostgreSQL exposed on host port 15432.
- Topic names use only periods (never underscores) to avoid Kafka metric-name collisions.

## Problems faced
- Kafka exited on startup: "advertised.listeners cannot use the nonroutable meta-address 0.0.0.0".
  In combined broker+controller mode, the CONTROLLER listener was bound to 0.0.0.0 and Kafka tried to advertise it.
  Fixed by binding it to the container hostname (CONTROLLER://kafka:9093).
- PostgreSQL host-port conflicts:
  - 5432: a Windows PostgreSQL 18 service answered instead of the container ("password authentication failed").
  - 5433: already in use by another PostgreSQL server.
  - 55432: inside a Windows reserved port range (Hyper-V/WSL); bind was forbidden.
    Reserved ranges can be listed with `netsh interface ipv4 show excludedportrange protocol=tcp`.
  - Fixed by using 15432.
- When one container fails, `docker compose up` stops and dependent jobs (kafka-init) never run.
- Smoke test must wait a few seconds after `up` for kafka-init to create topics.
- Learned: POSTGRES_PASSWORD is applied only when the data volume is first created; reset with `down -v`.