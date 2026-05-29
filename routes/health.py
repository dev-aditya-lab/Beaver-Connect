"""
routes/health.py — GET /health

A simple liveness probe used by the website to confirm that the
Beaver Connect desktop app is running and reachable on localhost.

The website should call this endpoint periodically (e.g. every 10 s)
and display a "connected / disconnected" indicator to the user.

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

from fastapi import APIRouter
from pydantic import BaseModel

from config import APP_NAME, APP_VERSION

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Response schema
# ─────────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """JSON body returned by GET /health."""
    status: str
    app: str
    version: str


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description=(
        "Returns 200 OK when Beaver Connect is running. "
        "The website polls this to display a connection indicator."
    ),
)
async def health_check() -> HealthResponse:
    """Always returns {'status': 'ok'} if the server is reachable."""
    return HealthResponse(
        status="ok",
        app=APP_NAME,
        version=APP_VERSION,
    )
