"""Run single-row or batch inference using the LightGBM champion artifact."""
from pathlib import Path
import json
import joblib
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = PROJECT_ROOT / "apps" / "backend" / "ml_artifacts"


def predict_proba_from_features(features: dict) -> float:
    """Predict drought risk probability [0.0, 1.0] from a 16-feature dictionary."""
    model_path = ARTIFACT_DIR / "lightgbm_agrishield_v1.joblib"
    cols_path = ARTIFACT_DIR / "feature_columns.json"
    cols = json.loads(cols_path.read_text(encoding="utf-8"))
    model = joblib.load(model_path)
    x = pd.DataFrame([[float(features[c]) for c in cols]], columns=cols)
    return float(model.predict_proba(x)[0][1])
