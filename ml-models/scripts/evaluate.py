"""Evaluate trained models on the 2024-2025 holdout test set."""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = PROJECT_ROOT / "apps" / "backend" / "ml_artifacts"
PROCESSED_DIR = PROJECT_ROOT / "data_pipeline" / "data" / "processed"


def evaluate_champion() -> dict:
    """Evaluate the LightGBM champion model on X_test / y_test (2024-2025)."""
    model_path = ARTIFACT_DIR / "lightgbm_agrishield_v1.joblib"
    cols_path = ARTIFACT_DIR / "feature_columns.json"
    x_test_path = PROCESSED_DIR / "X_test.csv"
    y_test_path = PROCESSED_DIR / "y_test.csv"
    if not (model_path.exists() and cols_path.exists() and x_test_path.exists() and y_test_path.exists()):
        return {}
    cols = json.loads(cols_path.read_text(encoding="utf-8"))
    model = joblib.load(model_path)
    x_test = pd.read_csv(x_test_path)[cols]
    y_test = pd.read_csv(y_test_path)["target_risk"].astype(int)
    y_pred = model.predict(x_test)
    y_prob = model.predict_proba(x_test)[:, 1]
    return {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_prob)), 4),
    }
