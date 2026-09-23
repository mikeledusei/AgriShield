"""Synthesize target labels for model training."""
import pandas as pd

RISK_THRESHOLDS = {"CRITICAL": 75, "HIGH": 50, "MODERATE": 25, "SAFE": 0}


def synthesize_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Create binary/categorical risk targets from features."""
    df = df.copy()
    score = pd.Series(0.0, index=df.index)

    if "rainfall_anomaly_30d" in df.columns:
        score += (df["rainfall_anomaly_30d"] < -10).astype(int) * 25

    if "ndvi_pasture_index" in df.columns:
        score += (df["ndvi_pasture_index"] < 0.3).astype(int) * 30

    if "temp_max_avg" in df.columns:
        score += (df["temp_max_avg"] > 32).astype(int) * 20

    if "soil_moisture_deficit" in df.columns:
        score += (df["soil_moisture_deficit"] > 50).astype(int) * 25

    df["risk_score"] = score.clip(0, 100)
    df["risk_label"] = df["risk_score"].apply(
        lambda s: "CRITICAL" if s >= 75 else "HIGH" if s >= 50 else "MODERATE" if s >= 25 else "SAFE"
    )
    return df
