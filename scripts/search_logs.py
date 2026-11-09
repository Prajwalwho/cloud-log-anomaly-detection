"""
Search logs stored in Elasticsearch.

Usage:
    python scripts/search_logs.py                                   # last 60 min: totals + 10 newest logs
    python scripts/search_logs.py --level ERROR
    python scripts/search_logs.py --service payment-service --level ERROR,WARN --minutes 30
    python scripts/search_logs.py --q "timeout"
    python scripts/search_logs.py --trace 3f2b8c1e9a4d4e2b          # one request across all services
    python scripts/search_logs.py --minutes 1440 --size 0           # count only, last 24 h
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Search logs in Elasticsearch.")
    parser.add_argument("--service", help="exact service name, e.g. payment-service")
    parser.add_argument("--level", help="comma-separated levels, e.g. ERROR,WARN")
    parser.add_argument("--q", help="words that must appear in the message")
    parser.add_argument("--trace", help="show every log of one request (trace_id), oldest first")
    parser.add_argument("--minutes", type=float, default=60, help="time window (default: %(default)s)")
    parser.add_argument("--size", type=int, default=10, help="number of logs to show (default: %(default)s)")
    args = parser.parse_args()

    if args.trace:
        filters = [{"term": {"trace_id": args.trace}}]          # a trace ignores the time window
    else:
        filters = [{"range": {"timestamp": {"gte": f"now-{int(args.minutes)}m"}}}]
    if args.service:
        filters.append({"term": {"service": args.service}})
    if args.level:
        filters.append({"terms": {"level": [lvl.strip().upper() for lvl in args.level.split(",")]}})
    must = [{"match": {"message": {"query": args.q, "operator": "and"}}}] if args.q else []

    es = Elasticsearch(URL, request_timeout=30)
    try:
        response = es.search(
            index=f"{PREFIX}-*",
            query={"bool": {"filter": filters, "must": must}},
            sort=[{"timestamp": "asc" if args.trace else "desc"}],
            size=100 if args.trace else args.size,
            track_total_hits=True,
            aggs={
                "by_service": {"terms": {"field": "service", "size": 20}},
                "by_level": {"terms": {"field": "level", "size": 10}},
            },
        )
    except ESConnectionError as exc:
        print(f"[FAIL] Elasticsearch not reachable at {URL}: {exc}")
        return 1

    total = response["hits"]["total"]["value"]
    window = f"trace {args.trace}" if args.trace else f"last {args.minutes:g} min"
    print(f"Matching logs ({window}): {total}")
    if total == 0:
        # No matching data (or no log indices yet): Elasticsearch then returns no aggregations.
        print("No logs found. Is the ingestion consumer running, and does the time window cover your data?")
        return 0

    aggregations = response.body.get("aggregations", {})
    for name, title in (("by_service", "By service"), ("by_level", "By level")):
        buckets = aggregations.get(name, {}).get("buckets", [])
        if buckets:
            print(f"{title}: " + ", ".join(f"{b['key']}={b['doc_count']}" for b in buckets))

    hits = response["hits"]["hits"]
    if hits:
        print()
    for hit in hits:
        log = hit["_source"]
        latency = f"  [{log['latency_ms']:.0f} ms]" if log.get("latency_ms") is not None else ""
        print(f"{log['timestamp']}  {log['level']:<5}  {log['service']:<18}  {log['message']}{latency}")
    return 0


if __name__ == "__main__":
    sys.exit(main())