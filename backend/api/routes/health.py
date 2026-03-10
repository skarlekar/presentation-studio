"""
Health check route — GET /api/health

Returns a simple liveness probe response with service name, version, and UTC timestamp.
"""
from datetime import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Liveness probe", tags=["health"])
async def health_check() -> dict:
    """Return service health status.

    Returns:
        JSON with status, version, service name, and current UTC timestamp.
    """
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "deckstudio-backend",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
