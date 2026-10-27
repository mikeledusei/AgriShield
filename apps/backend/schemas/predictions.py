"""Typed contracts for all prediction, future forecast, and SHAP explainability endpoints."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ShapFeatureContribution(BaseModel):
    feature: str
    label: str
    value: float
    shap_value: float
    impact_direction: str  # "increases_risk" | "reduces_risk" | "neutral"


class GlobalFeatureImportance(BaseModel):
    feature: str
    label: str
    importance: float
    importance_pct: float


class CountyPredictionRequest(BaseModel):
    county_name: str
    focus: Optional[str] = None
    month: Optional[str] = None  # e.g. "2025-02" or None for default active period


class FutureForecastRequest(BaseModel):
    county_name: str
    focus: Optional[str] = "combined"
    target_month: int = Field(default=2, ge=1, le=12)
    auto_derive_indices: bool = True
    # Core Champion Model feature overrides (any omitted field uses county baseline)
    rainfall_mm: Optional[float] = None
    rain_3m_sum: Optional[float] = None
    rainfall_anomaly: Optional[float] = None
    temp_mean_c: Optional[float] = None
    soil_moisture: Optional[float] = None
    ndvi_lag1: Optional[float] = None
    ndvi_lag3: Optional[float] = None
    ndvi_roll3_mean: Optional[float] = None
    ndvi_roll3_std: Optional[float] = None
    ndvi_anomaly: Optional[float] = None
    forage_dryness_index: Optional[float] = None
    farming_ratio: Optional[float] = None
    livestock_share: Optional[float] = None
    irrigation_ratio: Optional[float] = None


class CompareRequest(BaseModel):
    counties: List[str] = Field(..., min_length=2, max_length=10)
    month: Optional[str] = None


class RegionRequest(BaseModel):
    region_name: str
    month: Optional[str] = None


class ScenarioRequest(BaseModel):
    county_name: str
    rainfall_change_pct: float = 0.0   # e.g. -20 = 20% less rain
    temp_change_c: float = 0.0         # e.g. +3 = 3°C hotter
    ndvi_shock: float = 0.0            # e.g. -0.1 = vegetation shock
    month: Optional[str] = None


class PredictionOut(BaseModel):
    county_name: str
    region: Optional[str] = None
    focus: Optional[str] = None
    month: Optional[str] = None
    risk_score: int
    risk_level: str
    main_driver: str
    recommendation: str
    model_used: str
    plain_summary: Optional[str] = None
    features: Optional[Dict[str, float]] = None
    shap_contributions: Optional[List[ShapFeatureContribution]] = None


class FutureForecastResponse(BaseModel):
    county_name: str
    region: Optional[str] = None
    target_month: int
    baseline: PredictionOut
    forecast: PredictionOut
    score_delta: int
    narrative: str
    gria_plain_analysis: str


class ExplainResponse(BaseModel):
    county_name: str
    month: str
    risk_score: int
    risk_level: str
    base_value: float
    main_driver: str
    plain_explanation: str
    local_shap: List[ShapFeatureContribution]
    global_importance: List[GlobalFeatureImportance]
    feature_ranges: Dict[str, Dict[str, float]]


class BatchResponse(BaseModel):
    generated_at: str
    month: Optional[str] = None
    county_count: int
    counties: List[PredictionOut]


class CompareResponse(BaseModel):
    counties: List[PredictionOut]          # ranked highest -> lowest risk
    highest_risk: PredictionOut
    lowest_risk: PredictionOut


class RegionResponse(BaseModel):
    region_name: str
    county_count: int
    average_risk: float
    risk_level: str
    counties: List[PredictionOut]


class ScenarioResponse(BaseModel):
    county_name: str
    original: PredictionOut
    scenario: PredictionOut
    score_delta: int
    narrative: str
