"""Engineer features from raw and fetched data."""
import pandas as pd
from config import DEFAULT_FEATURES, COUNTIES


FEATURE_COLUMNS = [
    "rainfall_anomaly_30d",
    "ndvi_pasture_index",
    "temp_max_avg",
    "soil_moisture_deficit",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive model features from raw data."""
    df = df.copy()
    if "rainfall" in df.columns:
        df["rainfall_anomaly_30d"] = df["rainfall"] - df["rainfall"].rolling(30).mean()
    if "temperature" in df.columns:
        df["temp_max_avg"] = df["temperature"].rolling(7).max()
    if "ndvi" in df.columns:
        df["ndvi_pasture_index"] = df["ndvi"]
    if "soil_moisture" in df.columns:
        df["soil_moisture_deficit"] = 100 - df["soil_moisture"]
    return df


def build_feature_matrix(county_name: str) -> pd.DataFrame:
    """Build a feature matrix for a specific county."""
    features = DEFAULT_FEATURES.copy()
    return pd.DataFrame([features])
