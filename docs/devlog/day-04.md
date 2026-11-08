# Day 4 — Elasticsearch

## Done
- Added Elasticsearch 8.17 (single node) to docker-compose.yml with a persistent volume and healthcheck.
- Added Elasticsearch settings to .env and .env.example.
- Extended scripts/smoke_test.py: cluster health check, and write/read/delete of a document in a temporary index.
- Removed the placeholder infrastructure/docker/elasticsearch folder (configured through environment variables).
- Verified: all four containers healthy; smoke test passes for Kafka, PostgreSQL and Elasticsearch.

## Decisions
- Single-node mode (discovery.type=single-node).
- Security (TLS and authentication) disabled for local development only; production deployment would enable it.
- Java heap fixed at 1 GB (Xms = Xmx), container memory limit 2 GB to leave room for file-system cache.
- Disk-watermark check disabled in development so Elasticsearch does not block writes on a nearly full laptop disk.

## Observations
- Cluster health is green because no permanent indices exist yet. Indices with replicas would turn it yellow
  on a single node (replicas cannot be placed), so log indices will be created with number_of_replicas = 0 (Day 10).
- First image pull took about 4 minutes (~700 MB).

## Problems faced
- None.