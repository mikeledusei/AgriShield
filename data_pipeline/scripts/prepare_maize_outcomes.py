"""Normalize a third-party mirror of historical county maize yield records.

Original workbook is retained. Invalid or inconsistent rows are flagged, never repaired.
"""
import argparse
import hashlib
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data_pipeline/data/external/knbs_candidate/maize_2012_2020_mirror.xlsx'
ALIASES = {'Elgeyo/Marakwet': 'Elgeyo Marakwet', 'Homabay': 'Homa Bay',
           'Taita/Taveta': 'Taita Taveta', 'Tharaka-Nthi': 'Tharaka Nithi'}
EXPECTED = 'bf3a9c79d1c090cd73d82086e9b266967a4ad1c65377ebb0591697c366b02dfe'


def prepare(source=SOURCE):
    source = Path(source)
    if hashlib.sha256(source.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('The source workbook does not match the reviewed mirror checksum.')
    raw = pd.read_excel(source, sheet_name='Sheet4')
    if set(raw.columns) != {'County', 'Year', 'Indicator', 'Value'} or raw.duplicated(['County', 'Year', 'Indicator']).any():
        raise ValueError('Unexpected source structure or duplicate entries.')
    if set(raw['Indicator']) != {'Area (HA)', 'Production (MT)', 'Yield(MT/HA)'}:
        raise ValueError('Unexpected outcome indicators.')
    df = raw.pivot(index=['County', 'Year'], columns='Indicator', values='Value').reset_index()
    df = df.rename(columns={'County': 'county', 'Year': 'year', 'Area (HA)': 'harvested_area_ha',
                            'Production (MT)': 'production_tonnes', 'Yield(MT/HA)': 'yield_tonnes_per_ha'})
    df['county_original'] = df['county']
    df['county'] = df['county'].str.strip().replace(ALIASES)
    if df.duplicated(['county', 'year']).any():
        raise ValueError('Duplicate county-year after normalization.')
    area = df['harvested_area_ha']
    diff = (df['production_tonnes'] / area.where(area > 0) - df['yield_tonnes_per_ha']).abs()
    df['quality_flag'] = 'ok'
    df.loc[area <= 0, 'quality_flag'] = 'nonpositive_area'
    df.loc[(area > 0) & (diff > .01), 'quality_flag'] = 'yield_inconsistent_with_production_and_area'
    df.loc[df[['production_tonnes', 'yield_tonnes_per_ha']].isna().any(axis=1), 'quality_flag'] = 'missing_value'
    return df.sort_values(['year', 'county']).reset_index(drop=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output already exists; refusing to overwrite it.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = prepare()
    result.to_csv(args.output, index=False)
    print(f'Saved {len(result)} reported county-year observations; quality flags: {result.quality_flag.value_counts().to_dict()}')
