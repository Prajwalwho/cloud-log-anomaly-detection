"""
Integration test for the model registry (needs PostgreSQL from the stack; skipped if unreachable).
Restores the previously active model afterwards.
"""
import uuid

import psycopg
import pytest

from backend.detection.config import DetectionSettings
from backend.detection.registry import active_model, register_model, set_active

pytestmark = pytest.mark.integration
CONNINFO = DetectionSettings().postgres_conninfo


@pytest.fixture
def registry():
    try:
        with psycopg.connect(CONNINFO, connect_timeout=5):
            pass
    except Exception:
        pytest.skip("PostgreSQL not reachable; start the stack with .\\scripts\\start.ps1 up")
    previous = active_model(CONNINFO)
    name = f"test-model-{uuid.uuid4().hex[:8]}"
    yield name
    with psycopg.connect(CONNINFO) as conn:
        conn.execute("DELETE FROM model_registry WHERE name = %s", (name,))
    set_active(CONNINFO, previous["id"] if previous else None)


def register(name: str, version: str) -> int:
    return register_model(CONNINFO, name=name, version=version, algorithm="pca", file_path="x",
                          parameters={}, threshold=1.0, training_data="test", training_samples=1,
                          metrics={}, activate=True)


def test_newest_registration_becomes_the_only_active_model(registry):
    first = register(registry, "1")
    second = register(registry, "2")
    assert active_model(CONNINFO)["id"] == second
    with psycopg.connect(CONNINFO) as conn:
        assert conn.execute("SELECT is_active FROM model_registry WHERE id = %s", (first,)).fetchone()[0] is False


def test_duplicate_version_is_rejected(registry):
    register(registry, "1")
    with pytest.raises(ValueError):
        register(registry, "1")