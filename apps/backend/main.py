"""AgriShield FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from core.config import settings
from routers import health, predictions, gria, uploads, reports, auth, storage
from services import logging_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Modern, elegant, and perfectly spelled startup banner
    startup_banner = """
\033[92m
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║                  🌾  A G R I S H I E L D  🌾                     ║
║                                                                  ║
║Protecting Kenya's Food Security & Ensuring Future Sustainability ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
\033[0m
    """
    print(startup_banner)
    
    logging_service.info("🚀 Initializing AgriShield API...")
    logging_service.info(f" Environment: {settings.APP_ENV}")
    logging_service.info("🗄️  Database: NeonDB (PostgreSQL)")
    logging_service.info("🔐 Storage: Supabase")
    logging_service.info("⚡ Cache: Redis")
    logging_service.info(" Server is ready to accept connections!")
    
    yield
    
    print("\n\033[93m👋 Shutting down AgriShield API. Goodbye and keep growing! 🌾\033[0m\n")
    logging_service.info("🛑 AgriShield API shutdown complete.")


app = FastAPI(
    title="AgriShield API",
    description="Backend for crop yield and livestock forage risk prediction.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
cors_origins = settings.cors_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with API versioning
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
# app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(predictions.router, prefix=settings.API_V1_PREFIX)
app.include_router(storage.router, prefix=settings.API_V1_PREFIX)
app.include_router(gria.router, prefix=settings.API_V1_PREFIX)
app.include_router(uploads.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports.router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    return {
        "name": "AgriShield API",
        "tagline": "Protecting Kenya's Food Security, Ensuring Future Sustainability.",
        "docs": "/docs",
        "health": "/api/v1/health",
        "version": "1.0.0"
    }