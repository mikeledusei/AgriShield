"""Join the checked-in harmonized source tables with explicit imputation provenance.

This begins with the already-harmonized NDVI, weather and demographics tables;
it does not re-download raw provider data. Missing climate values are rejected
unless national same-month imputation is explicitly requested.
"""
import argparse
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / 'data' / 'processed'


def clean_data(data_dir: Path = DATA_DIR, impute_national_monthly: bool = False) -> pd.DataFrame:
    ndvi = pd.read_csv(data_dir / 'NDVI_FINAL.csv')
    weather = pd.read_csv(data_dir / 'Weather_FINAL.csv')
    demographics = pd.read_csv(data_dir / 'Demographic_Crop_Activity_FINAL.csv')
    keys = ['county', 'year', 'month']
    if ndvi.duplicated(keys).any() or weather.duplicated(keys).any() or demographics.duplicated(['county']).any():
        raise ValueError('Input tables contain duplicate keys.')
    df = ndvi.merge(weather, on=keys, how='outer', validate='one_to_one', indicator=True)
    if (df['_merge'] != 'both').any():
        raise ValueError('NDVI and weather county-month keys do not match.')
    df = df.drop(columns='_merge').merge(demographics, on='county', how='left', validate='many_to_one', indicator=True)
    if (df['_merge'] != 'both').any():
        raise ValueError('Some counties are missing demographic data.')
    df = df.drop(columns='_merge')
    source_columns = ['ndvi_mean', 'temperature_mean', 'rainfall_sum', 'soil_moisture_mean']
    for col in source_columns:
        df[f'{col}_imputed'] = df[col].isna()
        if df[col].isna().any():
            if not impute_national_monthly:
                raise ValueError(f'{col} contains missing values. Explicitly choose a documented imputation method.')
            df[col] = df[col].fillna(df.groupby(['year', 'month'])[col].transform('mean'))
    if df[source_columns].isna().any().any():
        raise ValueError('Some missing values could not be imputed from the same month.')
    for col in source_columns:
        df[col] = df[col].round(4)
    df = df.rename(columns={'temperature_mean': 'temp_mean_c', 'rainfall_sum': 'rainfall_mm', 'soil_moisture_mean': 'soil_moisture'})
    df['year_month'] = df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2)
    return df.sort_values(keys).reset_index(drop=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Output CSV path (existing tracked inputs are never overwritten automatically).')
    parser.add_argument('--impute-national-monthly', action='store_true', help='Explicitly fill missing climate values from the national mean for the same year and month.')
    args = parser.parse_args()
    result = clean_data(impute_national_monthly=args.impute_national_monthly)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit(f'Refusing to overwrite {args.output}; choose a new output path.')
    result.to_csv(args.output, index=False)
    print(f'Saved {len(result)} rows to {args.output}; imputation flags are included.')
