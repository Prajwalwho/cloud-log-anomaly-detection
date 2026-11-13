"""GET /services (api-contracts.md §3.2)."""
from fastapi import APIRouter, Request

from ..schemas import ServiceOut

router = APIRouter(tags=["services"])


@router.get("/services", response_model=list[ServiceOut])
def list_services(request: Request) -> list[dict]:
    with request.app.state.pool.connection() as conn:
        return conn.execute("SELECT id, name, description, created_at FROM services ORDER BY name").fetchall()