"""
Health check endpoint.
Synchronous DB check (matches the sync SQLAlchemy engine),
with graceful handling of optional services (Redis).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Report the live status of every backing service."""
    services = {}

    # 1. NeonDB - synchronous check, NO await
    try:
        db.execute(text("SELECT 1"))
        services["database"] = "connected"
    except Exception as exc:
        services["database"] = f"error: {exc}"

    # 2. Redis - optional (API falls back to in-memory cache)
    try:
        import redis as redis_lib
        client = redis_lib.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=2
        )
        client.ping()
        services["redis"] = "connected"
    except Exception as exc:
        services["redis"] = f"offline (optional, using in-memory cache)"

    # 3. Supabase
    try:
        from core.supabase_client import get_supabase
        get_supabase()
        services["supabase"] = "connected"
    except Exception as exc:
        services["supabase"] = f"error: {exc}"

    # 4. Gria AI (NVIDIA NIM)
    services["gria_ai"] = (
        "configured" if settings.NVIDIA_API_KEY else "not configured"
    )

    # Overall status: healthy if the database is reachable.
    # Redis is optional and does not affect the status.
    healthy = services["database"] == "connected"

    return {
        "status": "healthy" if healthy else "unhealthy",
        "services": services,
    }