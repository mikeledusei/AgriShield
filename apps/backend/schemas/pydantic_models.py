"""Pydantic models defining the API data contract (non-prediction schemas)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


# ---------- Core model input ----------
class ModelInput(BaseModel):
    county_name: str
    rainfall_anomaly_30d: float
    ndvi_pasture_index: float
    temp_max_avg: float
    soil_moisture_deficit: float


# ---------- Gria ----------
class GriaChatRequest(BaseModel):
    message: str
    county_name: Optional[str] = None


class GriaChatResponse(BaseModel):
    reply: str
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None


# ---------- Uploads ----------
class UploadResponse(BaseModel):
    file_name: str
    file_type: str
    extracted_data: ModelInput
    gria_summary: str
    risk_score: float
    risk_level: str


# ---------- Reports ----------
class ReportRequest(BaseModel):
    county_name: str
    report_type: str = "combined"
    detailed: bool = False


# ---------- Health ----------
class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    gria_available: bool
    database_connected: bool
