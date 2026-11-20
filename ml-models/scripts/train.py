"""Reproducible retrospective comparison. Never promotes or replaces the deployed model."""
import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from data_pipeline.scripts.experiment import DEFAULT_PANEL, FEATURES, build_experiment, load_panel

ARTIFACT_DIR = PROJECT_ROOT / 'apps/backend/ml_artifacts'


def load_champion_model():
    return joblib.load(ARTIFACT_DIR / 'lightgbm_agrishield_v1.joblib')


def load_feature_columns():
    return json.loads((ARTIFACT_DIR / 'feature_columns.json').read_text())


def metrics(y, p):
    predicted = (p >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    return {'samples': len(y), 'positives': int(sum(y)), 'true_positive': int(tp), 'false_positive': int(fp),
            'true_negative': int(tn), 'false_negative': int(fn),
            'accuracy': float(accuracy_score(y, predicted)), 'precision': float(precision_score(y, predicted, zero_division=0)),
            'recall': float(recall_score(y, predicted, zero_division=0)), 'f1': float(f1_score(y, predicted, zero_division=0)),
            'roc_auc': float(roc_auc_score(y, p)) if len(set(y)) == 2 else None,
            'average_precision': float(average_precision_score(y, p)) if len(set(y)) == 2 else None,
            'brier': float(brier_score_loss(y, p))}


def run_experiment(panel_path: Path, out: Path):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory is not empty; choose a new path to preserve previous runs.')
    df = build_experiment(load_panel(panel_path), train_end=2021)
    train = df[df.year <= 2021]
    validation = df[df.year.between(2022, 2023)]
    evaluation = df[df.year.between(2024, 2025)]
    if validation.empty or evaluation.empty or train.target_risk.nunique() < 2:
        raise ValueError('The configured periods must contain data and training needs both classes.')
    weight = (train.target_risk == 0).sum() / max((train.target_risk == 1).sum(), 1)
    models = {
        'logistic_regression': make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)),
        'random_forest': RandomForestClassifier(n_estimators=300, max_depth=10, min_samples_leaf=5, class_weight='balanced', random_state=42, n_jobs=1),
        'xgboost': XGBClassifier(n_estimators=200, max_depth=5, learning_rate=.05, scale_pos_weight=weight, eval_metric='logloss', random_state=42, n_jobs=1),
        'lightgbm': LGBMClassifier(n_estimators=200, max_depth=6, learning_rate=.05, scale_pos_weight=weight, random_state=42, verbosity=-1, n_jobs=1),
    }
    out.mkdir(parents=True, exist_ok=True)
    results, predictions = {}, []
    for name, model in models.items():
        model.fit(train[FEATURES], train.target_risk)
        joblib.dump(model, out / f'{name}.joblib')
        results[name] = {}
        for split, rows in [('validation_2022_2023', validation), ('previously_used_2024_2025', evaluation)]:
            prob = model.predict_proba(rows[FEATURES])[:, 1]
            results[name][split] = metrics(rows.target_risk, prob)
            predictions.extend({'model': name, 'split': split, 'county': c, 'year': int(y), 'month': int(m), 'target': int(t), 'score': float(p)}
                               for c, y, m, t, p in zip(rows.county, rows.year, rows.month, rows.target_risk, prob, strict=False))
    selected = max(models, key=lambda n: (results[n]['validation_2022_2023']['f1'], results[n]['validation_2022_2023']['roc_auc'] or 0))
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(models[selected], out / 'research_candidate.joblib')
    prediction_df = pd.DataFrame(predictions)
    prediction_df.to_csv(out / 'predictions.csv', index=False)
    for grouping, filename in [('county', 'metrics_by_county.csv'), ('month', 'metrics_by_month.csv')]:
        summaries = []
        for (name, split, key), group in prediction_df.groupby(['model', 'split', grouping]):
            summaries.append({'model': name, 'split': split, grouping: key, **metrics(group['target'], group['score'])})
        pd.DataFrame(summaries).to_csv(out / filename, index=False)
    report = {'description': 'Retrospective low-NDVI proxy experiment, not a crop or forage outcome forecast.',
              'train': '2015-2021', 'validation': '2022-2023',
              'evaluation': '2024-2025 (previously used for model selection; NOT an independent holdout)',
              'selection': 'Highest validation F1, then ROC-AUC at fixed 0.5 threshold; no tuning or promotion.',
              'limitations': ['Same-month weather makes this a retrospective/nowcast analysis.',
                              '2019 demographics and train-wide baselines are retrospective for early training rows.',
                              'Labels are a low-NDVI proxy, not observed agricultural losses.',
                              'All periods have been explored previously; obtain new independent outcome data.'],
              'panel_sha256': hashlib.sha256(Path(panel_path).read_bytes()).hexdigest(),
              'features': FEATURES, 'seed': 42, 'selected_on_validation': selected, 'results': results,
              'versions': {pkg: importlib.metadata.version(pkg) for pkg in ['scikit-learn', 'lightgbm', 'xgboost', 'pandas', 'numpy']}}
    (out / 'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel', type=Path, default=DEFAULT_PANEL)
    parser.add_argument('--output', type=Path, default=PROJECT_ROOT / 'ml-models/experiments/latest')
    args = parser.parse_args()
    result = run_experiment(args.panel, args.output)
    print(f"Selected {result['selected_on_validation']} on 2022–2023 validation; results saved to {args.output}")
    print('2024–2025 has been used before and is not an independent test. The deployed model was not changed.')
