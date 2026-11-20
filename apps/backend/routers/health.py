"""Health: distinguish reachable dependencies from merely configured ones."""
from fastapi import APIRouter
from sqlalchemy import text

from core.config import settings
from database.connection import engine as db_engine
from core.supabase_client import is_supabase_configured
from schemas.pydantic_models import HealthResponse
from services.prediction_service import get_engine

router = APIRouter(tags=['Health'])


@router.get('/health', response_model=HealthResponse)
def health_check():
    model = get_engine()
    db_ready = False
    if db_engine is not None:
        try:
            with db_engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            db_ready = True
        except Exception:
            pass
    from agents.gria_agent import agent_executor
    gria_ready = agent_executor is not None
    model_ready = model.model is not None and bool(model.feature_cols)
    services = {
        'database': 'connected' if db_ready else 'unreachable',
        'ml_engine': model.model_name if model_ready else 'unavailable',
        'historical_data': 'available' if model.county_history else 'unavailable',
        'supabase': 'configured (not checked)' if is_supabase_configured() else 'not configured',
        'redis': 'configured (not checked)' if settings.REDIS_URL else 'not configured',
        'gria_ai': 'configured (not checked)' if gria_ready else 'summary mode',
    }
    return HealthResponse(status='healthy' if db_ready and model_ready else 'degraded', services=services,
                          model_loaded=model_ready, model_name=model.model_name if model_ready else 'unavailable',
                          gria_available=gria_ready, database_connected=db_ready)
