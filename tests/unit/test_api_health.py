"""The API starts and reports 'degraded' (503) when its dependencies are unreachable. No Docker needed."""
from fastapi.testclient import TestClient

from backend.api.app.config import ApiSettings
from backend.api.app.main import create_app

UNREACHABLE = ApiSettings(postgres_port=1, elasticsearch_url="http://localhost:1",
                          kafka_bootstrap_servers="localhost:1", dependency_timeout_s=1.0)


def test_health_is_degraded_when_everything_is_down():
    with TestClient(create_app(UNREACHABLE)) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded",
                               "components": {"postgres": "down", "elasticsearch": "down", "kafka": "down"}}


def test_database_endpoints_return_503_in_contract_format():
    with TestClient(create_app(UNREACHABLE)) as client:
        for path in ("/api/v1/services", "/api/v1/anomalies"):
            response = client.get(path)
            assert response.status_code == 503, path
            assert response.json() == {"detail": "PostgreSQL unavailable"}


def test_log_endpoints_return_503_when_elasticsearch_is_down():
    with TestClient(create_app(UNREACHABLE)) as client:
        response = client.get("/api/v1/logs")
        assert response.status_code == 503
        assert response.json() == {"detail": "Elasticsearch unavailable"}
        assert client.get("/api/v1/logs/3f2b8c1e-9a4d-4e2b-8f61-2c7d9e0a1b34").status_code == 503


def test_invalid_parameters_are_rejected_before_touching_the_database():
    with TestClient(create_app(UNREACHABLE)) as client:
        assert client.get("/api/v1/anomalies", params={"size": 500}).status_code == 422
        assert client.get("/api/v1/anomalies/not-a-uuid").status_code == 422