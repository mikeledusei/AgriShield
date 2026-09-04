"""Typed contracts for all prediction endpoints."""
from typing import List, Optional
from pydantic import BaseModel, Field


class CountyPredictionRequest(BaseModel):
    county_name: str
    focus: Optional[str] = None


class CompareRequest(BaseModel):
    counties: List[str] = Field(..., min_length=2, max_length=10)


class RegionRequest(BaseModel):
    region_name: str


class ScenarioRequest(BaseModel):
    county_name: str
    rainfall_change_pct: float = 0.0   # e.g. -20 = 20% less rain
    temp_change_c: float = 0.0         # e.g. +3 = 3°C hotter
    ndvi_shock: float = 0.0            # e.g. -0.1 = vegetation shock


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


class BatchResponse(BaseModel):
    generated_at: str
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