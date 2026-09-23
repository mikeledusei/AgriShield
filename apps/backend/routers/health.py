import os
import json
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from fastapi import APIRouter

# Quick health check that doesn't require DB
router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    services: dict
    version: str = "1.0.0"

@router.get("/health")
async def health_check():
    services = {}
    services["supabase"] = "connected" if os.getenv("SUPABASE_URL") else "not configured"
    services["redis"] = "connected" if os.getenv("REDIS_URL") else "offline (optional)"
    services["gria_ai"] = "configured" if os.getenv("NVIDIA_API_KEY") else "not configured"
    return HealthResponse(
        status="healthy",
        services=services
    )

@router.get("/")
async def root():
    return {
        "name": "AgriShield API",
        "tagline": "Protecting Kenya's Food Security, Ensuring Future Sustainability.",
        "docs": "/docs",
        "health": "/api/v1/health",
        "version": "1.0.0"
    }