"""
Measure pipeline latency: the time from a log being created (timestamp) to being
stored in Elasticsearch by the ingestion service (ingested_at).

Measure a LIVE window: the ingestion consumer must have been running while the
generator was sending. Logs ingested from a backlog (consumer started late) or
re-indexed later have large latencies by design.

Logs become searchable up to 5 s after ingested_at (index refresh_interval).

Usage:
    python scripts/pipeline_latency.py --minutes 3
"""
import argparse
import os
import sys

from dotenv import load_dotenv
from elasticsearch import ConnectionError as ESConnectionError
from elasticsearch import Elasticsearch

load_dotenv()
URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
PREFIX = os.getenv("ELASTICSEARCH_INDEX_PREFIX", "logs")
BACKLOG_THRESHOLD_MS = 60_000

# Computed by Elasticsearch for every matching document, at query time
RUNTIME_MAPPINGS = {
    "lag_ms": {
        "type": "long",
        "script": {
            "source": "emit(doc['ingested_at'].value.toInstant().toEpochMilli()"
                      " - doc['timestamp'].value.toInstant().toEpochMilli())"
        },
    }
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure ingestion pipeline latency.")
    parser.add_argument("--minutes", type=float, default=3, help="time window (default: %(default)s)")
    args = parser.parse_args()

    es = Elasticsearch(URL, request_timeout=60)
    try:
        response = es.search(
            index=f"{PREFIX}-*",
            size=0,
            query={"range": {"timestamp": {"gte": f"now-{int(args.minutes)}m"}}},
            runtime_mappings=RUNTIME_MAPPINGS,
            aggs={
                "stats": {"stats": {"field": "lag_ms"}},
                "percentiles": {"percentiles": {"field": "lag_ms", "percents": [50, 95, 99]}},
                "by_service": {
                    "terms": {"field": "service", "size": 20},
                    "aggs": {"p95": {"percentiles": {"field": "lag_ms", "percents": [95]}}},
                },
            },
        )
    except ESConnectionError as exc:
        print(f"[FAIL] Elasticsearch not reachable at {URL}: {exc}")
        return 1

    aggregations = response.body.get("aggregations")
    stats = aggregations["stats"] if aggregations else {"count": 0}
    if not stats["count"]:
        print(f"No logs in the last {args.minutes:g} min. Run the consumer and the generator live first.")
        return 0

    p = aggregations["percentiles"]["values"]
    print(f"Pipeline latency (timestamp -> stored in Elasticsearch), last {args.minutes:g} min, "
          f"{stats['count']} logs")
    print(f"  min / avg / max : {stats['min']:>8.0f} / {stats['avg']:>8.0f} / {stats['max']:>8.0f} ms")
    print(f"  p50 / p95 / p99 : {p['50.0']:>8.0f} / {p['95.0']:>8.0f} / {p['99.0']:>8.0f} ms")
    print("  p95 per service :")
    for bucket in aggregations["by_service"]["buckets"]:
        print(f"    {bucket['key']:<20} {bucket['p95']['values']['95.0']:>8.0f} ms  ({bucket['doc_count']} logs)")
    print("  Searchable up to 5 s later (refresh_interval).")

    if stats["max"] > BACKLOG_THRESHOLD_MS:
        print(f"\n[WARN] Some logs took over {BACKLOG_THRESHOLD_MS // 1000} s: they were probably ingested from "
              f"a backlog or re-indexed. Measure a window where the consumer ran live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())