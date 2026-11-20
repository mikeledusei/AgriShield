"""Retrospective annual maize-yield research; not a live crop-risk forecast."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

ROOT = Path(__file__).resolve().parents[2]
OUTCOMES = ROOT / 'data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv'
CLIMATE = ROOT / 'data_pipeline/outputs/panel_2026_11_20/cleaned_panel.csv'
FEATURES = ['rainfall_year_mm', 'temperature_mean_c', 'soil_moisture_mean', 'prior_yield_mean']


def build_panel(outcomes=OUTCOMES, climate=CLIMATE):
    yields = pd.read_csv(outcomes)
    climate_data = pd.read_csv(climate)
    if yields.duplicated(['county', 'year']).any() or climate_data.duplicated(['county', 'year', 'month']).any():
        raise ValueError('Duplicate source rows.')
    valid = yields[yields.quality_flag == 'ok'].copy()
    weather = climate_data.groupby(['county', 'year']).agg(
        months=('month', 'nunique'), rainfall_year_mm=('rainfall_mm', 'sum'),
        temperature_mean_c=('temp_mean_c', 'mean'), soil_moisture_mean=('soil_moisture', 'mean'),
        soil_imputed_months=('soil_moisture_mean_imputed', 'sum')).reset_index()
    weather = weather[weather.months == 12]
    panel = valid.merge(weather, on=['county', 'year'], how='inner', validate='one_to_one')
    panel = panel[panel.year.isin([2015, 2016, 2017, 2018, 2020])].copy()
    # A county baseline for each year is built solely from earlier, quality-flagged years.
    # Never use the 2018 validation outcomes to fit or form the 2020 test baseline.
    prior = []
    for row in panel.itertuples():
        history = valid[(valid.county == row.county) & (valid.year < min(row.year, 2018))]
        prior.append(history['yield_tonnes_per_ha'].mean() if len(history) >= 2 else np.nan)
    panel['prior_yield_mean'] = prior
    if panel[FEATURES + ['yield_tonnes_per_ha']].isna().any().any():
        raise ValueError('Missing required weather, outcome or historical baseline.')
    if not np.isfinite(panel[FEATURES + ['yield_tonnes_per_ha']].to_numpy()).all():
        raise ValueError('Non-finite values in outcome panel.')
    return panel.sort_values(['year', 'county']).reset_index(drop=True)


def metrics(y, predicted):
    return {'samples': len(y), 'mae_tonnes_per_ha': float(mean_absolute_error(y, predicted)),
            'rmse_tonnes_per_ha': float(np.sqrt(mean_squared_error(y, predicted))),
            'r2': float(r2_score(y, predicted))}


def run(out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory is not empty; choose a new one.')
    panel = build_panel()
    train = panel[panel.year.between(2015, 2017)]
    validation = panel[panel.year == 2018]
    test = panel[panel.year == 2020]
    if train.empty or validation.empty or test.empty:
        raise ValueError('A required training, validation or holdout split has no data.')
    models = {
        'ridge': make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        'random_forest': RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42, n_jobs=1),
        'xgboost': XGBRegressor(n_estimators=150, max_depth=3, learning_rate=.05, random_state=42, n_jobs=1),
        'lightgbm': LGBMRegressor(n_estimators=150, max_depth=3, learning_rate=.05, random_state=42, verbosity=-1, n_jobs=1),
    }
    out.mkdir(parents=True, exist_ok=True)
    panel.to_csv(out / 'model_panel.csv', index=False)
    results, predictions = {}, []
    for name, model in models.items():
        model.fit(train[FEATURES], train.yield_tonnes_per_ha)
        joblib.dump(model, out / f'{name}.joblib')
        results[name] = {}
        for label, rows in [('validation_2018', validation), ('holdout_2020', test)]:
            pred = model.predict(rows[FEATURES])
            results[name][label] = metrics(rows.yield_tonnes_per_ha, pred)
            predictions.extend({'model': name, 'split': label, 'county': c, 'year': int(y), 'reported_yield': float(t), 'predicted_yield': float(p)}
                               for c, y, t, p in zip(rows.county, rows.year, rows.yield_tonnes_per_ha, pred))
    selected = min(models, key=lambda name: results[name]['validation_2018']['mae_tonnes_per_ha'])
    baselines = {label: metrics(rows.yield_tonnes_per_ha, rows.prior_yield_mean)
                 for label, rows in [('validation_2018', validation), ('holdout_2020', test)]}
    pd.DataFrame(predictions).to_csv(out / 'predictions.csv', index=False)
    report = {'target': 'Reported annual maize yield, tonnes per harvested hectare',
              'split': {'train': '2015-2017', 'validation': '2018', 'held_out_evaluation': '2020'},
              'selection': 'Lowest 2018 validation MAE, without hyperparameter tuning',
              'selected_model': selected, 'features': FEATURES, 'results': results,
              'historical_county_mean_baseline': baselines,
              'source_sha256': hashlib.sha256(OUTCOMES.read_bytes()).hexdigest(),
              'climate_sha256': hashlib.sha256(CLIMATE.read_bytes()).hexdigest(),
              'limitations': ['Third-party workbook source, primary source not independently verified.',
                              'Annual historical data only; 2019 missing and zero-area or inconsistent records excluded.',
                              'Full-year weather is retrospective, not available at the start of the year.',
                              'Packaged climate data provenance is unverified and soil moisture is partially imputed.',
                              'Small held-out sample from a single year; not independently verified field outcomes.',
                              'This experiment estimates yield, not crop-loss risk; no live deployment or threshold is approved.']}
    (out / 'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(f"Selected {selected}; 2020 MAE {results[selected]['holdout_2020']['mae_tonnes_per_ha']:.3f} tonnes/ha; historical baseline {baselines['holdout_2020']['mae_tonnes_per_ha']:.3f} tonnes/ha.")
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
