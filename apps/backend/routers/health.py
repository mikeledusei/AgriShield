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
    """Liveness: fast check that also reports model/db/gria status.

    Kept cheap — no smoke inference, just cached state — so dashboards polling
    every few seconds see 'model unavailable' immediately instead of forever.
    Use /health/ready for the full 503-gated probe (smoke test + Neon ping).
    """
    from services.health_service import build_health_report
    try:
        report = build_health_report()
        return HealthResponse(
            status='ok',
            services=report.services,
            model_loaded=report.services.get('ml_engine') not in (None, 'unavailable'),
            model_name=report.services.get('ml_engine', 'unavailable'),
            gria_available=str(report.services.get('gria_ai','')).startswith('configured'),
            database_connected=report.services.get('database') == 'connected (Neon)',
            problems=report.problems,
        )
    except Exception:
        # Liveness must never 500 — degraded report is still useful
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
        gria_available=str(report.services.get('gria_ai','')).startswith('configured'),
        database_connected=report.services.get('database') == 'connected',
        problems=report.problems,
    )
