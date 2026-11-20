"""AgriShield FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routers import health, manual_predictions, gria, auth, snapshot_reports, legacy, documents, live, history, outcomes
from seed_counties import seed as seed_counties
from services import logging_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_banner = (
        "\n"
        "════════════════════════════════════════════════════════════\n"
        "                  🌾  A G R I S H I E L D  🌾\n"
        "Protecting Kenya's Food Security & Ensuring Future Sustainability\n"
        "════════════════════════════════════════════════════════════\n"
    )
    print(startup_banner)

    logging_service.info("🚀 Initializing AgriShield API...")
    logging_service.info(f" Environment: {settings.APP_ENV}")
    logging_service.info("Report database configured" if settings.DATABASE_URL else "Report database not configured")
    if settings.DATABASE_URL:
        try:
            seed_counties()
        except Exception:
            logging_service.error("Database initialization failed; report storage is unavailable.")
    logging_service.info(" Server is ready to accept connections!")

    yield

    print("\n👋 Shutting down AgriShield API. Goodbye and keep growing! 🌾\n")
    logging_service.info("🛑 AgriShield API shutdown complete.")


app = FastAPI(
    title="AgriShield API",
    description="Research prototype for a historical vegetation-stress proxy; not an operational early warning system.",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = settings.cors_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
# Unsafe legacy routes are explicitly retired instead of silently returning invented data.
app.include_router(legacy.router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    return {
        "name": "AgriShield API",
        "tagline": "Protecting Kenya's Food Security, Ensuring Future Sustainability.",
        "docs": "/docs",
        "health": "/api/v1/health",
        "version": "1.0.0",
    }