"""Generate predictions using trained model."""
import os
import joblib
import pandas as pd


def predict(model, features: pd.DataFrame) -> pd.Series:
    """Generate risk predictions."""
    return model.predict(features)


def predict_proba(model, features: pd.DataFrame) -> pd.DataFrame:
    """Generate risk probabilities."""
    return model.predict_proba(features)


def predict_county(county_name: str, model=None):
    """Predict risk for a specific county."""
    if model is None:
        model_path = os.path.join(os.path.dirname(__file__), "..", "models", "xgboost_agrishield_v1.joblib")
        model = joblib.load(model_path)

    features = pd.DataFrame([{
        "rainfall_anomaly_30d": 0.0,
        "ndvi_pasture_index": 0.5,
        "temp_max_avg": 28.0,
        "soil_moisture_deficit": 40.0,
    }])

    risk_level = model.predict(features)[0]
    probabilities = model.predict_proba(features)[0]
    confidence = max(probabilities)

    return {
        "county_name": county_name,
        "risk_level": risk_level,
        "confidence": float(confidence),
    }
