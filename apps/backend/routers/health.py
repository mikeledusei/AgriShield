"""Health check endpoint."""
from fastapi import APIRouter

from core.config import settings
from core.database import is_configured
from core.supabase_client import is_supabase_configured
from schemas.pydantic_models import HealthResponse
from services.prediction_service import get_engine

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    engine = get_engine()
    model_loaded = engine.model is not None
    gria_ready = bool(
        settings.NVIDIA_API_KEY.strip()
        and settings.NVIDIA_API_KEY != "your-nvidia-api-key"
    )
    db_ready = is_configured()
    services = {
        "database": "connected" if db_ready else "not configured",
        "ml_engine": engine.model_name if model_loaded else "rule_based",
        "supabase": "connected" if is_supabase_configured() else "not configured",
        "redis": "connected" if settings.REDIS_URL else "offline (optional)",
        "gria_ai": "configured" if gria_ready else "fallback mode",
    }
    return HealthResponse(
        status="healthy",
        services=services,
        version="1.0.0",
        model_loaded=model_loaded,
        model_name=engine.model_name,
        gria_available=gria_ready,
        database_connected=db_ready,
    )
