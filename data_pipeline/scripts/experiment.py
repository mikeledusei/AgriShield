"""Build a reproducible retrospective NDVI-proxy experiment from a cleaned panel.

The target is a synthesized low-NDVI label, not a measured loss. Same-month
weather is used; this is not a lead-time forecast. Baselines are fitted only on
the specified training years; their use for earlier training rows is still
retrospective, as are the 2019 demographic covariates.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PANEL = ROOT / 'data_pipeline/data/processed/ml_base_2015_2025.csv'
FEATURES = ['month_sin', 'month_cos', 'ndvi_lag1', 'ndvi_lag3', 'ndvi_roll3_mean',
            'ndvi_roll3_std', 'ndvi_anomaly', 'temp_mean_c', 'rainfall_mm', 'soil_moisture',
            'rainfall_anomaly', 'rain_3m_sum', 'forage_dryness_index', 'farming_ratio',
            'livestock_share', 'irrigation_ratio']
REQUIRED = ['county', 'year', 'month', 'ndvi_mean', 'temp_mean_c', 'rainfall_mm', 'soil_moisture',
            'total', 'farming', 'crop_production', 'livestock_production', 'irrigation']


def load_panel(path=DEFAULT_PANEL):
    df = pd.read_csv(path)
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        raise ValueError(f'Missing panel columns: {sorted(missing)}')
    if df[REQUIRED].isna().any().any():
        raise ValueError('Missing values in the input panel; resolve and document them before training.')
    if df.duplicated(['county', 'year', 'month']).any():
        raise ValueError('Duplicate county-month observations.')
    if not df['month'].between(1, 12).all() or not (df['month'] % 1 == 0).all() or not ((df['year'] % 1 == 0) & df['year'].between(1, 9999)).all():
        raise ValueError('Invalid year or month in panel.')
    if df['county'].astype(str).str.strip().eq('').any():
        raise ValueError('County names must not be empty.')
    ordered = df.sort_values(['county', 'year', 'month'])
    month_index = ordered['year'] * 12 + ordered['month']
    if (month_index.groupby(ordered['county']).diff().dropna() != 1).any():
        raise ValueError('County-month series must be consecutive; gaps make lag and rolling features invalid.')
    if (df[['rainfall_mm', 'soil_moisture', 'total', 'farming', 'crop_production', 'livestock_production', 'irrigation']] < 0).any().any():
        raise ValueError('Negative rainfall, moisture, or household counts in panel.')
    numeric = [c for c in REQUIRED if c != 'county']
    if not np.isfinite(df[numeric].to_numpy(dtype=float)).all():
        raise ValueError('Input panel contains non-finite numeric values.')
    if not df.ndvi_mean.between(-1, 1).all() or not df.soil_moisture.between(0, 1).all():
        raise ValueError('NDVI or soil moisture is outside its physical range.')
    if not df.temp_mean_c.between(-20, 60).all():
        raise ValueError('Temperature is outside the supported range.')
    if (df[['farming', 'crop_production', 'livestock_production']].gt(df['total'], axis=0)).any().any() or (df.irrigation > df.farming).any():
        raise ValueError('Inconsistent household counts in panel.')
    return df.sort_values(['county', 'year', 'month']).reset_index(drop=True)


def build_experiment(panel, train_end=2021):
    """Return engineered rows using train-only county and month baselines."""
    df = panel.copy().sort_values(['county', 'year', 'month']).reset_index(drop=True)
    train = df[df.year <= train_end]
    if train.empty or df[df.year > train_end].empty:
        raise ValueError('The requested split must contain both training and later observations.')
    stats = train.groupby('county')['ndvi_mean'].agg(ndvi_25th_pct=lambda x: np.percentile(x, 25),
                                                    ndvi_mean_hist='mean', ndvi_std_hist='std').reset_index()
    rain = train.groupby(['county', 'month'], as_index=False)['rainfall_mm'].mean().rename(columns={'rainfall_mm': 'rain_normal'})
    df = df.merge(stats, on='county', how='left').merge(rain, on=['county', 'month'], how='left')
    if df[['ndvi_25th_pct', 'ndvi_mean_hist', 'ndvi_std_hist', 'rain_normal']].isna().any().any():
        raise ValueError('A county or month lacks a training baseline.')
    df['target_risk'] = (df.ndvi_mean < df.ndvi_25th_pct).astype(int)
    df['month_sin'] = np.sin(2 * np.pi * df.month / 12).round(6)
    df['month_cos'] = np.cos(2 * np.pi * df.month / 12).round(6)
    ndvi = df.groupby('county')['ndvi_mean']
    df['ndvi_lag1'] = ndvi.shift(1).fillna(df.ndvi_mean_hist)
    df['ndvi_lag3'] = ndvi.shift(3).fillna(df.ndvi_mean_hist)
    df['ndvi_roll3_mean'] = ndvi.transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean()).fillna(df.ndvi_mean_hist)
    df['ndvi_roll3_std'] = ndvi.transform(lambda x: x.shift(1).rolling(3, min_periods=1).std()).fillna(0)
    df['ndvi_anomaly'] = (df.ndvi_lag1 - df.ndvi_mean_hist).round(6)
    df['rainfall_anomaly'] = (df.rainfall_mm - df.rain_normal).round(4)
    df['rain_3m_sum'] = df.groupby('county')['rainfall_mm'].transform(lambda x: x.rolling(3, min_periods=1).sum()).round(4)
    deficit = (0.45 - df.soil_moisture).clip(lower=0).round(4)
    drop = (df.ndvi_mean_hist - df.ndvi_lag1).clip(lower=0) / (df.ndvi_std_hist + 1e-6)
    df['forage_dryness_index'] = (0.5 * drop + 0.5 * deficit * df.temp_mean_c / 25).round(4)
    df['farming_ratio'] = (df.farming / (df.total + 1)).round(4)
    df['livestock_share'] = (df.livestock_production / (df.crop_production + df.livestock_production + 1)).round(4)
    df['irrigation_ratio'] = (df.irrigation / (df.farming + 1)).round(4)
    if not np.isfinite(df[FEATURES].to_numpy()).all():
        raise ValueError('Feature matrix has non-finite values.')
    return df
