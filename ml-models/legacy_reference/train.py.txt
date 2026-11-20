"""Train candidate models (Logistic Regression, Random Forest, XGBoost, LightGBM)."""
from pathlib import Path
import json
import joblib

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = PROJECT_ROOT / "apps" / "backend" / "ml_artifacts"


def load_champion_model():
    """Load the persisted LightGBM champion model."""
    model_path = ARTIFACT_DIR / "lightgbm_agrishield_v1.joblib"
    if model_path.exists():
        return joblib.load(model_path)
    return None


def load_feature_columns():
    """Load the 16 feature column names."""
    cols_path = ARTIFACT_DIR / "feature_columns.json"
    if cols_path.exists():
        return json.loads(cols_path.read_text(encoding="utf-8"))
    return []
