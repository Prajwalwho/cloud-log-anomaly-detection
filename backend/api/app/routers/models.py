"""GET /models and GET /models/active (api-contracts.md §3.13, §3.14)."""
from fastapi import APIRouter, HTTPException, Request

from ..schemas import ModelOut

router = APIRouter(tags=["models"])

COLUMNS = ("id, name, version, algorithm, threshold, training_data, training_samples, is_active, "
           "trained_at, parameters, metrics")


@router.get("/models", response_model=list[ModelOut])
def list_models(request: Request) -> list[dict]:
    with request.app.state.pool.connection() as conn:
        return conn.execute(f"SELECT {COLUMNS} FROM model_registry ORDER BY trained_at DESC, id DESC").fetchall()


@router.get("/models/active", response_model=ModelOut)
def active_model(request: Request) -> dict:
    with request.app.state.pool.connection() as conn:
        row = conn.execute(f"SELECT {COLUMNS} FROM model_registry WHERE is_active").fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No active model")
    return row