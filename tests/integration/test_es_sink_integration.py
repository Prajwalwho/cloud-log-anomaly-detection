"""
Integration tests for the Elasticsearch sink: template, idempotent writes, searching.

Requires the stack (.\\scripts\\start.ps1 up). Skipped automatically if Elasticsearch is not reachable.
Uses a unique index prefix per test and deletes everything it creates.
"""
import json
import os
import uuid

import pytest
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, NotFoundError

from backend.ingestion.es_sink import ElasticsearchSink
from backend.ingestion.validator import validate_message
from backend.log_generator.generator import LogGenerator

load_dotenv()
URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")

pytestmark = pytest.mark.integration


@pytest.fixture
def es() -> Elasticsearch:
    client = Elasticsearch(URL, request_timeout=10)
    try:
        client.info()
    except Exception:
        pytest.skip("Elasticsearch not reachable; start the stack with .\\scripts\\start.ps1 up")
    return client


@pytest.fixture
def prefix(es: Elasticsearch):
    name = f"testlogs-{uuid.uuid4().hex[:8]}"   # does not match the real logs-* template
    yield name
    indices = list(es.indices.get(index=f"{name}-*", allow_no_indices=True).body)
    if indices:
        es.indices.delete(index=",".join(indices))   # explicit names: wildcard deletes are blocked by default
    try:
        es.indices.delete_index_template(name=f"{name}-template")
    except NotFoundError:
        pass


def sample_events(seconds: float = 10):
    return [validate_message(json.dumps(event)) for _, event in LogGenerator(rate=20, seed=9).events(seconds)]


def test_writes_are_idempotent_and_searchable(es: Elasticsearch, prefix: str):
    sink = ElasticsearchSink(URL, index_prefix=prefix)
    sink.ensure_ready()
    batch = sample_events()

    assert sink.write_batch(batch) == []
    assert sink.write_batch(batch) == []          # same events again, as after a consumer restart
    es.indices.refresh(index=f"{prefix}-*")

    assert es.count(index=f"{prefix}-*")["count"] == len(batch)      # no duplicates
    payment = es.count(index=f"{prefix}-*", query={"term": {"service": "payment-service"}})["count"]
    assert payment == sum(1 for event in batch if event.service == "payment-service")


def test_indices_are_created_from_the_template(es: Elasticsearch, prefix: str):
    sink = ElasticsearchSink(URL, index_prefix=prefix)
    sink.ensure_ready()
    sink.write_batch(sample_events()[:5])

    indices = es.indices.get(index=f"{prefix}-*").body
    assert indices
    for info in indices.values():
        assert info["settings"]["index"]["number_of_replicas"] == "0"
        assert info["mappings"]["dynamic"] == "strict"
        assert info["mappings"]["properties"]["service"]["type"] == "keyword"