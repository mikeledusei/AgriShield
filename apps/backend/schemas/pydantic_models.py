"""Pydantic models defining the API data contract."""
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


# ---------- Prediction ----------
class CountyPredictionRequest(BaseModel):
    county_name: str
    focus: str = "crops"


class PredictionResponse(BaseModel):
    county_name: str
    focus: str = "crops"
    risk_score: float
    risk_level: str
    main_driver: str
    recommendation: str


class BatchResponse(BaseModel):
    counties: List[PredictionResponse]
    generated_at: datetime


class RegionRequest(BaseModel):
    region_name: str


class RegionResponse(BaseModel):
    region_name: str
    county_count: int
    average_risk: float
    risk_level: str
    counties: List[PredictionResponse]


class CompareRequest(BaseModel):
    counties: List[str]


class CompareResponse(BaseModel):
    counties: List[PredictionResponse]


class ScenarioRequest(BaseModel):
    county_name: str
    rainfall_change: float = 0.0
    temp_change: float = 0.0


class ScenarioResponse(BaseModel):
    county_name: str
    original_risk: float
    original_level: str
    scenario_risk: float
    scenario_level: str


# ---------- Trends ----------
class TrendPoint(BaseModel):
    date: datetime
    risk_score: float
    risk_level: str


class TrendsResponse(BaseModel):
    county_name: str
    months: int
    trend: List[TrendPoint]


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