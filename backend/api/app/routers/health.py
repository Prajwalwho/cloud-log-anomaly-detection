"""GET /health (api-contracts.md §3.1): PostgreSQL, Elasticsearch and Kafka; 503 "degraded" if any is down."""
from confluent_kafka.admin import AdminClient
from fastapi import APIRouter, Request, Response

from ..schemas import HealthOut

router = APIRouter(tags=["health"])


def _postgres_ok(request: Request) -> bool:
    try:
        with request.app.state.pool.connection(timeout=request.app.state.settings.dependency_timeout_s) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def _elasticsearch_ok(request: Request) -> bool:
    try:
        return bool(request.app.state.es.ping())
    except Exception:
        return False


def _kafka_ok(request: Request) -> bool:
    settings = request.app.state.settings
    try:
        admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers,
                             "socket.timeout.ms": int(settings.dependency_timeout_s * 1000)})
        topics = admin.list_topics(timeout=settings.dependency_timeout_s).topics
        return settings.kafka_topic_anomalies in topics
    except Exception:
        return False


@router.get("/health", response_model=HealthOut)
def health(request: Request, response: Response) -> HealthOut:
    components = {
        "postgres": "ok" if _postgres_ok(request) else "down",
        "elasticsearch": "ok" if _elasticsearch_ok(request) else "down",
        "kafka": "ok" if _kafka_ok(request) else "down",
    }
    degraded = any(state == "down" for state in components.values())
    if degraded:
        response.status_code = 503
    return HealthOut(status="degraded" if degraded else "ok", components=components)