"""AgriShield FastAPI application entry point."""
from contextlib import asynccontextmanager

from core.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.request_context import RequestContextMiddleware
from routers import (
    auth,
    documents,
    gria,
    health,
    history,
    live,
    manual_predictions,
    outcomes,
    snapshot_reports,
)
from seed_counties import seed as seed_counties
from services import logging_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging_service.info("Initializing AgriShield API (env=%s, model=%s)",
                         settings.APP_ENV, settings.MODEL_PATH.name)
    if settings.DATABASE_URL:
        try:
            seed_counties()
        except Exception:
            logging_service.exception(
                "County seeding failed; reports and history may be unavailable."
            )
    else:
        logging_service.info("DATABASE_URL is empty; using the local SQLite database.")

    from services.health_service import build_health_report

    report = build_health_report()
    if report.ready:
        logging_service.info("Dependency check passed: %s", report.services)
    else:
        # Do not crash the process: a degraded API can still serve /health/ready and
        # explain itself. The deploy platform decides based on that status code.
        logging_service.error("Dependency check failed: %s", "; ".join(report.problems))

    yield

    logging_service.info("AgriShield API shutdown complete.")


app = FastAPI(
    title="AgriShield API",
    description=(
        "Research prototype for a historical vegetation-stress proxy; "
        "not an operational early warning system."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Correlation id + access log first, so every later log line carries the request id.
app.add_middleware(RequestContextMiddleware)

cors_origins = settings.cors_origins_list
# Wildcards and credentials are mutually exclusive: a browser rejects the pair, and
# allowing any origin with credentials is a session-riding risk.
allow_credentials = cors_origins != ["*"]
if cors_origins == ["*"]:
    logging_service.warning(
        "CORS_ORIGINS='*': credentials are disabled. List explicit origins to send cookies."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-History-Key", "X-Report-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(live.router, prefix=settings.API_V1_PREFIX)
app.include_router(outcomes.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(manual_predictions.router, prefix=settings.API_V1_PREFIX)
app.include_router(gria.router, prefix=settings.API_V1_PREFIX)
app.include_router(documents.router, prefix=settings.API_V1_PREFIX)
app.include_router(snapshot_reports.router, prefix=settings.API_V1_PREFIX)
app.include_router(history.router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": "AgriShield API",
        "tagline": "Protecting Kenya's Food Security, Ensuring Future Sustainability.",
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
        "readiness": f"{settings.API_V1_PREFIX}/health/ready",
        "version": "1.0.0",
    }
