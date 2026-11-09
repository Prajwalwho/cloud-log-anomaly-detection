"""
End-to-end integration test: generator -> Kafka -> ingestion -> Elasticsearch.

Requires the stack (.\\scripts\\start.ps1 up). Skipped automatically if Kafka or Elasticsearch
is not reachable. Uses temporary topics, consumer group and index prefix, and removes them afterwards.
"""
import os
import uuid
from collections import defaultdict

import pytest
from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, NotFoundError

from backend.ingestion.config import IngestionSettings
from backend.ingestion.consumer import IngestionConsumer
from backend.ingestion.es_sink import ElasticsearchSink
from backend.log_generator.generator import LogGenerator
from backend.log_generator.producer import KafkaLogPublisher

load_dotenv()
KAFKA = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")

pytestmark = pytest.mark.integration


@pytest.fixture
def environment():
    admin = AdminClient({"bootstrap.servers": KAFKA})
    es = Elasticsearch(ES_URL, request_timeout=10)
    try:
        admin.list_topics(timeout=5)
        es.info()
    except Exception:
        pytest.skip("Kafka or Elasticsearch not reachable; start the stack with .\\scripts\\start.ps1 up")

    suffix = uuid.uuid4().hex[:8]
    names = {
        "raw": f"e2e-raw-{suffix}",
        "deadletter": f"e2e-dl-{suffix}",
        "group": f"e2e-group-{suffix}",
        "prefix": f"e2elogs-{suffix}",
    }
    futures = admin.create_topics([NewTopic(names["raw"], num_partitions=3, replication_factor=1),
                                   NewTopic(names["deadletter"], num_partitions=1, replication_factor=1)])
    for future in futures.values():
        future.result(timeout=10)

    yield names, es

    for future in admin.delete_topics([names["raw"], names["deadletter"]]).values():
        future.result(timeout=10)
    indices = list(es.indices.get(index=f"{names['prefix']}-*", allow_no_indices=True).body)
    if indices:
        es.indices.delete(index=",".join(indices))
    try:
        es.indices.delete_index_template(name=f"{names['prefix']}-template")
    except NotFoundError:
        pass


def test_logs_flow_from_generator_to_elasticsearch(environment):
    names, es = environment

    # 1. Generator -> Kafka
    events = [event for _, event in LogGenerator(rate=20, seed=21).events(10)]
    publisher = KafkaLogPublisher(KAFKA, names["raw"])
    publisher.check_connection()
    for event in events:
        publisher.publish(event)
    assert publisher.flush() == 0
    assert publisher.delivered == len(events)

    # 2. Kafka -> ingestion -> Elasticsearch
    config = IngestionSettings(
        kafka_bootstrap_servers=KAFKA,
        kafka_topic_logs=names["raw"],
        kafka_topic_deadletter=names["deadletter"],
        ingestion_group_id=names["group"],
        elasticsearch_url=ES_URL,
        elasticsearch_index_prefix=names["prefix"],
    )
    sink = ElasticsearchSink(ES_URL, index_prefix=names["prefix"])
    sink.ensure_ready()
    stats = IngestionConsumer(sink, config).run(idle_exit_s=10, verbose=False)

    assert stats.received == len(events)
    assert stats.valid == len(events)
    assert stats.invalid == 0

    # 3. Every event is stored exactly once
    es.indices.refresh(index=f"{names['prefix']}-*")
    assert es.count(index=f"{names['prefix']}-*")["count"] == len(events)

    # 4. The request with the most services can be reconstructed by its trace_id
    services_per_trace = defaultdict(set)
    for event in events:
        if event["trace_id"]:
            services_per_trace[event["trace_id"]].add(event["service"])
    trace_id, expected_services = max(services_per_trace.items(), key=lambda item: len(item[1]))
    hits = es.search(index=f"{names['prefix']}-*", query={"term": {"trace_id": trace_id}}, size=50)
    assert {hit["_source"]["service"] for hit in hits["hits"]["hits"]} == expected_services

    # 5. Every stored document carries its ingestion time
    missing = es.count(index=f"{names['prefix']}-*",
                       query={"bool": {"must_not": {"exists": {"field": "ingested_at"}}}})["count"]
    assert missing == 0