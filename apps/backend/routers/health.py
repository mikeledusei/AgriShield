"""Health and readiness.

``/health`` is a cheap liveness probe: it answers 200 as long as the process is
serving. ``/health/ready`` performs the real dependency checks and answers 503 when
the app cannot score a request, so a deploy platform's health check fails instead
of reporting green on a broken release.
"""
from fastapi import APIRouter, Response, status
from schemas.pydantic_models import HealthResponse
from services.health_service import build_health_report

router = APIRouter(tags=['Health'])


@router.get('/health', response_model=HealthResponse)
def health_check():
    """Liveness: the process is up. Does not touch the model or the database."""
    return HealthResponse(status='ok', services={'process': 'running'},
                          model_loaded=False, model_name='unchecked',
                          gria_available=False, database_connected=False)


@router.get('/health/ready', response_model=HealthResponse, responses={503: {'model': HealthResponse}})
def readiness(response: Response):
    report = build_health_report()
    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status='ready' if report.ready else 'degraded',
        services=report.services,
        model_loaded=report.services.get('ml_engine') not in (None, 'unavailable'),
        model_name=report.services.get('ml_engine', 'unavailable'),
        gria_available=report.services.get('gria_ai') == 'configured',
        database_connected=report.services.get('database') == 'connected',
        problems=report.problems,
    )
