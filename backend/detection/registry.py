"""
Model registry in PostgreSQL (database-design.md, table model_registry).

At most one model is active (enforced by a unique partial index). Registering with activate=True
deactivates the current active model and activates the new one in the same transaction.
"""
from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb


def register_model(
    conninfo: str,
    *,
    name: str,
    version: str,
    algorithm: str,
    file_path: str,
    parameters: dict,
    threshold: float | None,
    training_data: str,
    training_samples: int,
    metrics: dict,
    activate: bool = True,
) -> int:
    with psycopg.connect(conninfo) as conn, conn.transaction():
        exists = conn.execute(
            "SELECT 1 FROM model_registry WHERE name = %s AND version = %s", (name, version)
        ).fetchone()
        if exists:
            raise ValueError(f"Model {name} {version} is already registered")
        if activate:
            conn.execute("UPDATE model_registry SET is_active = FALSE WHERE is_active")
        row = conn.execute(
            """
            INSERT INTO model_registry
                (name, version, algorithm, file_path, parameters, threshold,
                 training_data, training_samples, metrics, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (name, version, algorithm, file_path, Jsonb(parameters), threshold,
             training_data, training_samples, Jsonb(metrics), activate),
        ).fetchone()
    return int(row[0])


def active_model(conninfo: str) -> dict | None:
    with psycopg.connect(conninfo) as conn:
        cursor = conn.execute(
            "SELECT id, name, version, algorithm, file_path, threshold, parameters, metrics, trained_at "
            "FROM model_registry WHERE is_active"
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(zip([column.name for column in cursor.description], row))


def set_active(conninfo: str, model_id: int | None) -> None:
    """Make model_id the active model (None = no active model)."""
    with psycopg.connect(conninfo) as conn, conn.transaction():
        conn.execute("UPDATE model_registry SET is_active = FALSE WHERE is_active")
        if model_id is not None:
            conn.execute("UPDATE model_registry SET is_active = TRUE WHERE id = %s", (model_id,))