"""
Typed data contracts for the AgriShield frontend (shared/types.py).
Mirrors the FastAPI schemas in apps/backend/schemas/ for predictions,
TreeSHAP explainability, future feature-slider forecasts, Gria AI, and uploads.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ShapContribution:
    feature: str
    label: str
    value: float
    shap_value: float
    impact_direction: str = "neutral"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShapContribution":
        return cls(
            feature=str(data.get("feature", "")),
            label=str(data.get("label", data.get("feature", ""))),
            value=float(data.get("value", 0.0)),
            shap_value=float(data.get("shap_value", 0.0)),
            impact_direction=str(data.get("impact_direction", "neutral")),
        )


@dataclass
class GlobalFeatureImportance:
    feature: str
    label: str
    importance: float
    importance_pct: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalFeatureImportance":
        return cls(
            feature=str(data.get("feature", "")),
            label=str(data.get("label", data.get("feature", ""))),
            importance=float(data.get("importance", 0.0)),
            importance_pct=float(data.get("importance_pct", 0.0)),
        )


@dataclass
class PredictionResult:
    county_name: str
    region: str
    focus: str
    risk_score: int
    risk_level: str
    main_driver: str
    recommendation: str
    model_used: str = "lightgbm_v1"
    month: Optional[str] = "2025-02"
    plain_summary: Optional[str] = None
    features: Optional[Dict[str, float]] = None
    shap_contributions: List[ShapContribution] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionResult":
        raw_shap = data.get("shap_contributions") or []
        return cls(
            county_name=str(data.get("county_name", "Unknown")),
            region=str(data.get("region", "Unknown")),
            focus=str(data.get("focus", "combined")),
            risk_score=int(round(float(data.get("risk_score", 0)))),
            risk_level=str(data.get("risk_level", "SAFE")),
            main_driver=str(data.get("main_driver", "N/A")),
            recommendation=str(data.get("recommendation", "")),
            model_used=str(data.get("model_used", "lightgbm_v1")),
            month=data.get("month", "2025-02"),
            plain_summary=data.get("plain_summary"),
            features=data.get("features"),
            shap_contributions=[
                ShapContribution.from_dict(s) if isinstance(s, dict) else s
                for s in raw_shap
            ],
        )


@dataclass
class ExplainResult:
    county_name: str
    month: str
    risk_score: int
    risk_level: str
    base_value: float
    main_driver: str
    plain_explanation: str
    local_shap: List[ShapContribution] = field(default_factory=list)
    global_importance: List[GlobalFeatureImportance] = field(default_factory=list)
    feature_ranges: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExplainResult":
        return cls(
            county_name=str(data.get("county_name", "Unknown")),
            month=str(data.get("month", "2025-02")),
            risk_score=int(round(float(data.get("risk_score", 0)))),
            risk_level=str(data.get("risk_level", "SAFE")),
            base_value=float(data.get("base_value", 0.0)),
            main_driver=str(data.get("main_driver", "N/A")),
            plain_explanation=str(data.get("plain_explanation", "")),
            local_shap=[
                ShapContribution.from_dict(s) for s in (data.get("local_shap") or [])
            ],
            global_importance=[
                GlobalFeatureImportance.from_dict(g)
                for g in (data.get("global_importance") or [])
            ],
            feature_ranges=dict(data.get("feature_ranges") or {}),
        )


@dataclass
class FutureForecastResult:
    county_name: str
    region: str
    target_month: int
    baseline: PredictionResult
    forecast: PredictionResult
    score_delta: int
    narrative: str
    gria_plain_analysis: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FutureForecastResult":
        return cls(
            county_name=str(data.get("county_name", "Unknown")),
            region=str(data.get("region", "Unknown")),
            target_month=int(data.get("target_month", 2)),
            baseline=PredictionResult.from_dict(data.get("baseline", {})),
            forecast=PredictionResult.from_dict(data.get("forecast", {})),
            score_delta=int(data.get("score_delta", 0)),
            narrative=str(data.get("narrative", "")),
            gria_plain_analysis=str(data.get("gria_plain_analysis", "")),
        )


@dataclass
class BatchResult:
    generated_at: str
    county_count: int
    counties: List[PredictionResult] = field(default_factory=list)
    month: Optional[str] = "2025-02"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchResult":
        counties = [
            PredictionResult.from_dict(c) for c in data.get("counties", [])
        ]
        return cls(
            generated_at=str(data.get("generated_at", "")),
            county_count=int(data.get("county_count", len(counties))),
            counties=counties,
            month=data.get("month", "2025-02"),
        )


@dataclass
class CompareResult:
    counties: List[PredictionResult]
    highest_risk: PredictionResult
    lowest_risk: PredictionResult

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompareResult":
        counties = [
            PredictionResult.from_dict(c) for c in data.get("counties", [])
        ]
        return cls(
            counties=counties,
            highest_risk=PredictionResult.from_dict(data.get("highest_risk", {})),
            lowest_risk=PredictionResult.from_dict(data.get("lowest_risk", {})),
        )


@dataclass
class RegionResult:
    region_name: str
    county_count: int
    average_risk: float
    risk_level: str
    counties: List[PredictionResult] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegionResult":
        counties = [
            PredictionResult.from_dict(c) for c in data.get("counties", [])
        ]
        return cls(
            region_name=str(data.get("region_name", "")),
            county_count=int(data.get("county_count", len(counties))),
            average_risk=float(data.get("average_risk", 0.0)),
            risk_level=str(data.get("risk_level", "SAFE")),
            counties=counties,
        )


@dataclass
class ScenarioResult:
    county_name: str
    original: PredictionResult
    scenario: PredictionResult
    score_delta: int
    narrative: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioResult":
        return cls(
            county_name=str(data.get("county_name", "")),
            original=PredictionResult.from_dict(data.get("original", {})),
            scenario=PredictionResult.from_dict(data.get("scenario", {})),
            score_delta=int(data.get("score_delta", 0)),
            narrative=str(data.get("narrative", "")),
        )


@dataclass
class HistoryPoint:
    date: str
    risk_score: int
    risk_level: str
    rainfall_mm: float = 0.0
    soil_moisture: float = 0.0
    ndvi_lag1: float = 0.0
    forage_dryness_index: float = 0.0
    temp_mean_c: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryPoint":
        return cls(
            date=str(data.get("date", "")),
            risk_score=int(round(float(data.get("risk_score", 0)))),
            risk_level=str(data.get("risk_level", "SAFE")),
            rainfall_mm=float(data.get("rainfall_mm", 0.0)),
            soil_moisture=float(data.get("soil_moisture", 0.0)),
            ndvi_lag1=float(data.get("ndvi_lag1", 0.0)),
            forage_dryness_index=float(data.get("forage_dryness_index", 0.0)),
            temp_mean_c=float(data.get("temp_mean_c", 0.0)),
        )


@dataclass
class HistoryResult:
    county_name: str
    months: int
    trend: List[HistoryPoint] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryResult":
        trend = [HistoryPoint.from_dict(t) for t in data.get("trend", [])]
        return cls(
            county_name=str(data.get("county_name", "")),
            months=int(data.get("months", 12)),
            trend=trend,
        )


@dataclass
class GriaResponse:
    reply: str
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    main_driver: Optional[str] = None
    plain_summary: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GriaResponse":
        return cls(
            reply=str(data.get("reply", "")),
            risk_score=(
                float(data["risk_score"])
                if data.get("risk_score") is not None
                else None
            ),
            risk_level=data.get("risk_level"),
            main_driver=data.get("main_driver"),
            plain_summary=data.get("plain_summary"),
        )


@dataclass
class UploadResult:
    file_name: str
    file_type: str
    extracted_data: Dict[str, Any]
    gria_summary: str
    risk_score: float
    risk_level: str
    baseline_risk_score: Optional[float] = None
    baseline_risk_level: Optional[str] = None
    score_delta_vs_baseline: Optional[float] = None
    model_used: str = "lightgbm_v1"
    main_driver: Optional[str] = None
    converted_features: Dict[str, float] = field(default_factory=dict)
    shap_contributions: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    comparison_narrative: Optional[str] = None
    row_count: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UploadResult":
        return cls(
            file_name=str(data.get("file_name", "")),
            file_type=str(data.get("file_type", "")),
            extracted_data=dict(data.get("extracted_data") or {}),
            gria_summary=str(data.get("gria_summary", "")),
            risk_score=float(data.get("risk_score", 0.0)),
            risk_level=str(data.get("risk_level", "SAFE")),
            baseline_risk_score=(
                float(data["baseline_risk_score"])
                if data.get("baseline_risk_score") is not None
                else None
            ),
            baseline_risk_level=data.get("baseline_risk_level"),
            score_delta_vs_baseline=(
                float(data["score_delta_vs_baseline"])
                if data.get("score_delta_vs_baseline") is not None
                else None
            ),
            model_used=str(data.get("model_used", "lightgbm_v1")),
            main_driver=data.get("main_driver"),
            converted_features=dict(data.get("converted_features") or {}),
            shap_contributions=list(data.get("shap_contributions") or []),
            suggestions=list(data.get("suggestions") or []),
            comparison_narrative=data.get("comparison_narrative"),
            row_count=int(data.get("row_count", 1)),
        )
