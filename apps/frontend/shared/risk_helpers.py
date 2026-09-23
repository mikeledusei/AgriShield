"""Risk calculation and prediction helpers."""
import streamlit as st
from typing import Optional

RISK_THRESHOLDS = {"CRITICAL": 75, "HIGH": 50, "MODERATE": 25, "SAFE": 0}

RISK_COLORS = {
    "CRITICAL": "#d32f2f",
    "HIGH": "#f57c00",
    "MODERATE": "#fbc02d",
    "SAFE": "#2e7d32",
}

FEATURE_LABELS = {
    "rainfall_anomaly_30d": "Rainfall Anomaly (30d)",
    "ndvi_pasture_index": "NDVI Pasture Index",
    "temp_max_avg": "Max Temperature",
    "soil_moisture_deficit": "Soil Moisture Deficit",
}


def compute_score(features: dict) -> int:
    """Compute a rule-based risk score from features (0-100)."""
    score = 0
    rainfall = features.get("rainfall_anomaly_30d", 0.0)
    ndvi = features.get("ndvi_pasture_index", 0.5)
    temp = features.get("temp_max_avg", 28.0)
    soil = features.get("soil_moisture_deficit", 40.0)

    if rainfall < -20:
        score += 30
    elif rainfall < -10:
        score += 20
    elif rainfall < 0:
        score += 10

    if ndvi < 0.3:
        score += 30
    elif ndvi < 0.4:
        score += 20
    elif ndvi < 0.5:
        score += 10

    if temp > 32:
        score += 20
    elif temp > 30:
        score += 10

    if soil > 50:
        score += 20
    elif soil > 40:
        score += 10

    return min(max(score, 0), 100)


def get_risk_level(score: int) -> str:
    """Map a numeric score to a risk level."""
    if score >= RISK_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if score >= RISK_THRESHOLDS["HIGH"]:
        return "HIGH"
    if score >= RISK_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    return "SAFE"


def format_feature_value(feature_name: str, value: float) -> str:
    """Format a feature value with its label."""
    label = FEATURE_LABELS.get(feature_name, feature_name)
    return f"{label}: {value:.4f}"


def get_risk_color(risk_level: str) -> str:
    """Get the hex color for a risk level."""
    return RISK_COLORS.get(risk_level.upper(), "#616161")
