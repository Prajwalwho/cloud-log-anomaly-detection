"""
Backend API (Phase 7, api-contracts.md 1.1).

Run (from the project root, venv active, stack running):
    uvicorn backend.api.app.main:app --reload --reload-dir backend/api --port 8000
Interactive docs: http://localhost:8000/docs
Live feed: ws://localhost:8000/api/v1/ws/live (python scripts/watch_live.py)

Design:
- Endpoints are plain (sync) functions: psycopg and the Elasticsearch client are used synchronously, and
  FastAPI runs sync endpoints in a thread pool.
- PostgreSQL connections come from a pool that is opened WITHOUT waiting, so the API starts even when the
  database is down; /health then reports "degraded". The Kafka listener for /ws/live also retries in the
  background.
- Dependency failures become 503 {"detail": ...} (contract error format), never a stack trace.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

import psycopg
from elasticsearch import ConnectionError as EsConnectionError
from elasticsearch import ConnectionTimeout as EsConnectionTimeout
from elasticsearch import Elasticsearch
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from .config import ApiSettings
from .realtime import FeedListener, LiveHub, alert_event, anomaly_event
from .routers import alerts, anomalies, health, live, logs, models, services, stats

API_PREFIX = "/api/v1"


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    settings = settings or ApiSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.pool = ConnectionPool(
            settings.postgres_conninfo, min_size=1, max_size=settings.postgres_pool_max,
            kwargs={"row_factory": dict_row}, timeout=settings.dependency_timeout_s,
            open=False, name="api",
        )
        app.state.pool.open(wait=False)          # do not block start-up if PostgreSQL is down
        app.state.es = Elasticsearch(settings.elasticsearch_url, request_timeout=settings.dependency_timeout_s)

        # Live feed: hub in this event loop, Kafka listener in a background thread, ping task.
        app.state.hub = LiveHub(asyncio.get_running_loop(), settings.live_queue_size)
        app.state.listener = None
        if settings.live_kafka_enabled:
            app.state.listener = FeedListener(
                app.state.hub, settings.kafka_bootstrap_servers,
                {settings.kafka_topic_anomalies: anomaly_event, settings.kafka_topic_alerts: alert_event},
                settings.api_group_id,
            )
            app.state.listener.start()

        async def ping() -> None:
            while True:
                await asyncio.sleep(settings.live_ping_s)
                app.state.hub.publish({"type": "ping", "data": {}})

        ping_task = asyncio.create_task(ping())
        try:
            yield
        finally:
            ping_task.cancel()
            with suppress(asyncio.CancelledError):
                await ping_task
            if app.state.listener is not None:
                app.state.listener.stop()
                app.state.listener.join(timeout=5)
            app.state.pool.close()
            app.state.es.close()

    app = FastAPI(
        title="Cloud Log Anomaly Detection API",
        version="1.1",
        description="Logs, anomalies, alerts, statistics, models and a live feed (api-contracts.md 1.1).",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "PATCH"], allow_headers=["*"],
    )

    @app.exception_handler(PoolTimeout)
    @app.exception_handler(psycopg.OperationalError)
    async def postgres_unavailable(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "PostgreSQL unavailable"})

    @app.exception_handler(EsConnectionError)
    @app.exception_handler(EsConnectionTimeout)
    async def elasticsearch_unavailable(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Elasticsearch unavailable"})

    for router in (health.router, services.router, models.router, anomalies.router, logs.router,
                   alerts.router, stats.router, live.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()