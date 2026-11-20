"""Evaluate the existing deployed model on its previously used 2024–2025 data.

This is not an independent test and measures the synthesized NDVI proxy only.
"""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                             confusion_matrix, precision_score, recall_score, f1_score, roc_auc_score)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = PROJECT_ROOT / 'apps/backend/ml_artifacts'
PROCESSED_DIR = PROJECT_ROOT / 'data_pipeline/data/processed'


def evaluate_champion() -> dict:
    cols = json.loads((ARTIFACT_DIR / 'feature_columns.json').read_text(encoding='utf-8'))
    model = joblib.load(ARTIFACT_DIR / 'lightgbm_agrishield_v1.joblib')
    x = pd.read_csv(PROCESSED_DIR / 'X_test.csv')[cols]
    y = pd.read_csv(PROCESSED_DIR / 'y_test.csv')['target_risk'].astype(int)
    if len(x) != len(y):
        raise ValueError('Feature and target rows do not match.')
    predicted = model.predict(x)
    prob = model.predict_proba(x)[:, 1]
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    return {'scope': '2024–2025 previously used for champion selection; not an independent test; NDVI proxy only',
            'samples': len(y), 'positives': int(y.sum()), 'true_positive': int(tp), 'false_positive': int(fp),
            'true_negative': int(tn), 'false_negative': int(fn),
            'accuracy': round(float(accuracy_score(y, predicted)), 4),
            'precision': round(float(precision_score(y, predicted, zero_division=0)), 4),
            'recall': round(float(recall_score(y, predicted, zero_division=0)), 4),
            'f1': round(float(f1_score(y, predicted, zero_division=0)), 4),
            'roc_auc': round(float(roc_auc_score(y, prob)), 4),
            'average_precision': round(float(average_precision_score(y, prob)), 4),
            'brier': round(float(brier_score_loss(y, prob)), 4)}


if __name__ == '__main__':
    print(json.dumps(evaluate_champion(), indent=2))
