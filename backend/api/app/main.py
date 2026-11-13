"""
Backend API (Phase 7, api-contracts.md 1.1).

Run (from the project root, venv active, stack running):
    uvicorn backend.api.app.main:app --reload --port 8000
Interactive docs: http://localhost:8000/docs

Design:
- Endpoints are plain (sync) functions: psycopg and the Elasticsearch client are used synchronously, and
  FastAPI runs sync endpoints in a thread pool.
- PostgreSQL connections come from a pool that is opened WITHOUT waiting, so the API starts even when the
  database is down; /health then reports "degraded".
- Dependency failures become 503 {"detail": ...} (contract error format), never a stack trace.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

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
from .routers import anomalies, health, logs, models, services

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
        try:
            yield
        finally:
            app.state.pool.close()
            app.state.es.close()

    app = FastAPI(
        title="Cloud Log Anomaly Detection API",
        version="1.1",
        description="Logs, anomalies, alerts, statistics and models (api-contracts.md 1.1).",
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

    for router in (health.router, services.router, models.router, anomalies.router, logs.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()