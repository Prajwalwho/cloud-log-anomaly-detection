# Day 6 — Log generator: normal traffic

## Done
- backend/log_generator/config.py: settings loaded from .env (rate, seed, Kafka settings for Day 8).
- backend/log_generator/generator.py: simulates 5 microservices with request flows
  (browse_products, login, order_status, checkout) through the API gateway.
- Output: real-time or fast mode, console (JSON or --pretty) or JSONL file, summary statistics.
- pyproject.toml: pytest and ruff configuration.
- tests/unit/test_generator.py: 9 tests (contract fields, reproducibility, ordering, unique IDs,
  multi-service traces, request rate, normal error rate, failure propagation). All passing.

## Design decisions
- Traffic modelled as request flows, not independent random lines: logs share trace_id,
  latencies add up along the call chain, and downstream failures appear as 502 at the gateway.
- Poisson request arrivals with a ±30% sinusoidal rate variation (10-minute period), so normal
  traffic has peaks and dips the detector must not flag.
- Log-normal latencies; calls slower than 3x the median are logged as WARN.
- 0.2% baseline failure rate per call: normal data is realistically noisy, not perfectly clean.
- Periodic background logs (health checks, pool stats, batch jobs) per service.
- Fixed seed produces identical output, for reproducible experiments.
- Events are emitted in timestamp order using a priority queue (heap).

## Results — 10 minutes of normal traffic (rate 20 req/s, seed 42)

| Level | Events | Share |
|---|---|---|
| DEBUG | 3,216 | 8.78% |
| INFO | 33,022 | 90.13% |
| WARN | 320 | 0.87% |
| ERROR | 82 | 0.22% |
| **Total** | **36,640** | |

| Service | Events |
|---|---|
| api-gateway | 11,971 |
| auth-service | 8,054 |
| order-service | 4,805 |
| payment-service | 2,433 |
| inventory-service | 9,377 |

- Service volumes match the configured flow mix (e.g. order-service ≈ 40% of 12,000 requests).
- Generation speed in fast mode: ~28,000 events/second (36,640 events in 1.3 s).

## Problems faced
- Test for failure propagation failed: it counted all api-gateway events, but the gateway also writes
  background logs (health checks, pool stats) that are not requests. Fixed the test to count only
  request logs (events with a trace_id).