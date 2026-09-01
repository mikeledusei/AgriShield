"""Prediction service."""
import joblib
import pandas as pd
from sqlalchemy.orm import Session
from core.config import settings
from database import crud
from services import cache_service, logging_service

_model = None
_model_load_attempted = False

def load_model():
    global _model, _model_load_attempted
    if not _model_load_attempted:
        _model_load_attempted = True
        if settings.MODEL_PATH.exists():
            try:
                _model = joblib.load(settings.MODEL_PATH)
                logging_service.info(f"Champion model loaded: {settings.MODEL_PATH.name}")
            except Exception as exc:
                logging_service.error(f"Failed to load model: {exc}")
                _model = None
        else:
            logging_service.warning("Champion model not found. Using rule-based risk engine.")
    return _model

def is_model_loaded() -> bool:
    return load_model() is not None

def get_risk_level(score: float) -> str:
    if score >= settings.RISK_THRESHOLDS["CRITICAL"]: return "CRITICAL"
    if score >= settings.RISK_THRESHOLDS["HIGH"]: return "HIGH"
    if score >= settings.RISK_THRESHOLDS["MODERATE"]: return "MODERATE"
    return "SAFE"

def _rule_based_score(features: dict) -> float:
    score = 0.0
    rainfall = features.get("rainfall_anomaly_30d", 0.0)
    if rainfall <= -30: score += 30
    elif rainfall <= -10: score += 18
    elif rainfall < 0: score += 8

    ndvi = features.get("ndvi_pasture_index", 0.5)
    if ndvi <= 0.25: score += 30
    elif ndvi <= 0.4: score += 18
    elif ndvi <= 0.55: score += 8

    temp = features.get("temp_max_avg", 28.0)
    if temp >= 34: score += 20
    elif temp >= 31: score += 12

    soil_deficit = features.get("soil_moisture_deficit", 40.0)
    if soil_deficit >= 70: score += 20
    elif soil_deficit >= 55: score += 12
    return round(min(score, 100.0), 2)

def compute_score(features: dict) -> float:
    model = load_model()
    if model is None: return _rule_based_score(features)
    df = pd.DataFrame([features])
    if hasattr(model, "feature_names_in_"):
        expected = list(model.feature_names_in_)
        for col in expected:
            if col not in df.columns: df[col] = 0.0
        df = df[expected]
    probability = model.predict_proba(df)[0]
    risk_probability = probability[1] if len(probability) > 1 else probability[0]
    return round(float(risk_probability) * 100, 2)

def determine_main_driver(features: dict) -> str:
    drivers = []
    if features.get("rainfall_anomaly_30d", 0.0) <= -20: drivers.append(("Rainfall deficit", abs(features["rainfall_anomaly_30d"])))
    if features.get("ndvi_pasture_index", 0.5) <= 0.4: drivers.append(("Low pasture greenness", (1 - features["ndvi_pasture_index"]) * 100))
    if features.get("temp_max_avg", 28.0) >= 31: drivers.append(("High temperature", features["temp_max_avg"]))
    if features.get("soil_moisture_deficit", 40.0) >= 55: drivers.append(("Soil moisture deficit", features["soil_moisture_deficit"]))
    if not drivers: return "No dominant risk factor detected"
    drivers.sort(key=lambda item: item[1], reverse=True)
    return drivers[0][0]

def get_recommendation(risk_level: str) -> str:
    advice = {
        "SAFE": "Conditions are favorable. Continue normal farming activities.",
        "MODERATE": "Monitor weather closely and prepare backup plans.",
        "HIGH": "Take preventive action now to protect crops and livestock.",
        "CRITICAL": "Immediate intervention required. Mobilize emergency support.",
    }
    return advice[risk_level]

def get_features_for_county(db: Session, county) -> dict:
    features = dict(settings.DEFAULT_FEATURES)
    if county is None: return features
    latest = crud.get_latest_features(db, county.id)
    if latest is None: return features
    features["rainfall_anomaly_30d"] = latest.rainfall_anomaly_30d or features["rainfall_anomaly_30d"]
    features["ndvi_pasture_index"] = latest.ndvi_pasture_index or features["ndvi_pasture_index"]
    features["temp_max_avg"] = latest.temp_max_avg or features["temp_max_avg"]
    features["soil_moisture_deficit"] = latest.soil_moisture_deficit or features["soil_moisture_deficit"]
    return features

def predict_county(db: Session, county_name: str, focus: str = "crops") -> dict:
    cache_key = f"predict:{county_name}:{focus}"
    cached = cache_service.get(cache_key)
    if cached: return cached

    county = crud.get_county_by_name(db, county_name)
    features = get_features_for_county(db, county)
    score = compute_score(features)
    level = get_risk_level(score)
    driver = determine_main_driver(features)
    recommendation = get_recommendation(level)

    if county is not None:
        crud.save_prediction(db, county.id, focus, score, level, driver, recommendation)

    result = {
        "county_name": county_name, "focus": focus, "risk_score": score,
        "risk_level": level, "main_driver": driver, "recommendation": recommendation,
    }
    cache_service.set(cache_key, result)
    return result

def quick_risk(county_name: str) -> tuple:
    features = dict(settings.DEFAULT_FEATURES)
    score = compute_score(features)
    return score, get_risk_level(score)

def predict_scenario(db: Session, county_name: str, rainfall_change: float, temp_change: float) -> dict:
    county = crud.get_county_by_name(db, county_name)
    base_features = get_features_for_county(db, county)
    original_score = compute_score(base_features)
    scenario_features = dict(base_features)
    scenario_features["rainfall_anomaly_30d"] += rainfall_change
    scenario_features["temp_max_avg"] += temp_change
    scenario_score = compute_score(scenario_features)
    return {
        "county_name": county_name,
        "original_risk": original_score, "original_level": get_risk_level(original_score),
        "scenario_risk": scenario_score, "scenario_level": get_risk_level(scenario_score),
    }