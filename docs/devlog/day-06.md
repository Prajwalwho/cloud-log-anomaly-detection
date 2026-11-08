# Day 6 — Log generator: normal traffic

## Done
- backend/log_generator/config.py: settings loaded from .env (rate, seed, Kafka settings for Day 8).
- backend/log_generator/generator.py: simulates 5 microservices with request flows
  (browse_products, login, order_status, checkout) through the API gateway.
- Output: real-time or fast mode, console (JSON or --pretty) or JSONL file, summary statistics.
- pyproject.toml: pytest and ruff configuration.
- tests/unit/test_generator.py: 9 tests (contract fields, reproducibility, ordering, unique IDs,
  multi-service traces, request rate, normal error rate, failure propagation).

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

## Results
- (paste the summary from the 10-minute fast run)

## Problems faced
- Test for failure propagation failed: it counted all api-gateway events, but the gateway also writes
  background logs (health checks, pool stats) that are not requests. Fixed the test to count only
  request logs (events with a trace_id).