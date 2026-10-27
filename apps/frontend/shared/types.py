"""Typed API data contracts matching the AgriShield FastAPI backend schemas."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class HealthResponse(TypedDict, total=False):
    status: str
    services: Dict[str, str]
    version: str
    model_loaded: bool
    model_name: str
    gria_available: bool
    database_connected: bool


class PredictionOut(TypedDict, total=False):
    county_name: str
    region: Optional[str]
    focus: Optional[str]
    month: Optional[str]
    risk_score: int
    risk_level: str
    main_driver: str
    recommendation: str
    model_used: str


class BatchResponse(TypedDict):
    generated_at: str
    county_count: int
    counties: List[PredictionOut]


class CompareResponse(TypedDict):
    counties: List[PredictionOut]
    highest_risk: PredictionOut
    lowest_risk: PredictionOut


class RegionResponse(TypedDict):
    region_name: str
    county_count: int
    average_risk: float
    risk_level: str
    counties: List[PredictionOut]


class ScenarioResponse(TypedDict):
    county_name: str
    original: PredictionOut
    scenario: PredictionOut
    score_delta: int
    narrative: str


class TrendPoint(TypedDict):
    date: str
    risk_score: int
    risk_level: str


class HistoryResponse(TypedDict):
    county_name: str
    months: int
    trend: List[TrendPoint]


class ReportOut(TypedDict, total=False):
    id: int
    county_id: int
    report_type: str
    detailed: bool
    file_path: Optional[str]
    created_at: str


class ReportListResponse(TypedDict):
    reports: List[ReportOut]
    total: int


class GriaChatResponse(TypedDict, total=False):
    reply: str
    risk_score: Optional[float]
    risk_level: Optional[str]


class ExtractedModelInput(TypedDict):
    county_name: str
    rainfall_anomaly_30d: float
    ndvi_pasture_index: float
    temp_max_avg: float
    soil_moisture_deficit: float


class UploadResponse(TypedDict):
    file_name: str
    file_type: str
    extracted_data: ExtractedModelInput
    gria_summary: str
    risk_score: float
    risk_level: str
