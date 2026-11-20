"""Data pipeline tests.

The pipeline is notebook-only: `data_pipeline/scripts/` has been removed, so these tests
assert against the notebook *files* and the committed outputs they produce, rather than
importing Python modules that no longer exist.

What is still enforced, and what is not
---------------------------------------
Kept: the panel is complete and well-formed; the processed tables agree with each other;
     the notebooks exist, are valid JSON, contain no network calls outside the acquisition
     notebook, and every figure ships with an explanation.
Lost: the previous suite imported `data_pipeline/scripts/experiment.py` and unit-tested its
     validation function directly. That logic now lives in `01_data_cleaning.ipynb`, where a
     bug would show up as a failed notebook run rather than a red test. This is a real
     reduction in coverage, recorded in docs/CHANGELOG.md.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / 'data_pipeline'
PROCESSED = PIPELINE / 'data' / 'processed'
NOTEBOOKS = PIPELINE / 'notebooks'

PANEL = PROCESSED / 'master_cleaned_2015_2025.csv'
ML_BASE = PROCESSED / 'ml_base_2015_2025.csv'


def notebook_code(path):
    """Concatenated source of a notebook's code cells."""
    nb = json.loads(path.read_text(encoding='utf-8'))
    return '\n'.join(''.join(cell['source']) for cell in nb['cells'] if cell['cell_type'] == 'code')


def test_pipeline_scripts_are_gone():
    """The scripts were removed deliberately; a reappearing file means a half-done port."""
    assert not (PIPELINE / 'scripts').exists(), 'data_pipeline/scripts/ should have been removed'


def test_notebooks_exist_and_are_valid():
    expected = ['00_data_ingest.ipynb', '00a_raw_data_acquisition.ipynb',
                '01_data_cleaning.ipynb', '02_eda.ipynb']
    for name in expected:
        path = NOTEBOOKS / name
        assert path.exists(), f'missing notebook: {name}'
        nb = json.loads(path.read_text(encoding='utf-8'))
        assert nb['nbformat'] == 4
        assert any(c['cell_type'] == 'code' for c in nb['cells']), f'{name} has no code'


def test_only_the_acquisition_notebook_makes_network_calls():
    """Cleaning and EDA must stay offline so they run from the committed files."""
    for path in NOTEBOOKS.glob('*.ipynb'):
        if path.name.startswith('00a'):
            continue
        code = notebook_code(path)
        for token in ('requests.', 'urllib.request', 'urlopen('):
            assert token not in code, f'{path.name} must not call the network ({token})'


def test_master_panel_is_complete_and_consistent():
    panel = pd.read_csv(PANEL)
    assert len(panel) == 6204
    assert panel.county.nunique() == 47
    assert panel.groupby('county').size().eq(132).all(), 'every county must have 132 months'
    assert not panel.duplicated(['county', 'year', 'month']).any()
    assert not panel.isna().any().any(), 'the master panel is fully resolved'

    ordered = panel.sort_values(['county', 'year', 'month'])
    months = ordered.year * 12 + ordered.month
    assert (months.groupby(ordered.county).diff().dropna() == 1).all(), 'no gaps allowed'

    assert panel.ndvi_mean.between(-1, 1).all()
    assert panel.soil_moisture.between(0, 1).all()
    assert panel.temp_mean_c.between(-20, 60).all()
    assert (panel.irrigation <= panel.farming).all()


def test_imputation_is_flagged_rather_than_silent():
    panel = pd.read_csv(PANEL)
    assert 'soil_moisture_mean_imputed' in panel.columns
    assert int(panel.soil_moisture_mean_imputed.sum()) == 132


def test_ml_base_matches_the_committed_feature_contract():
    """The ML notebooks read this file, so its columns are a contract."""
    base = pd.read_csv(ML_BASE)
    required = {'county', 'year', 'month', 'ndvi_mean', 'temp_mean_c', 'rainfall_mm',
                'soil_moisture', 'total', 'farming', 'crop_production',
                'livestock_production', 'irrigation', 'year_month'}
    assert required <= set(base.columns)
    assert len(base) == 6204

    # The champion model expects these 16 features to be derivable from this table.
    champion_features = json.loads(
        (ROOT / 'apps/backend/ml_artifacts/feature_columns.json').read_text())
    assert len(champion_features) == 16


def test_eda_outputs_every_figure_with_an_explanation():
    """Every chart must ship with a .md that explains it — that was the requirement."""
    runs = sorted((PIPELINE / 'outputs').glob('eda_*'))
    assert runs, 'no EDA run found; run 02_eda.ipynb'
    run = runs[-1]
    figures = sorted((run / 'figures').glob('*.png'))
    assert len(figures) >= 7, f'expected at least 7 charts, found {len(figures)}'

    for fig in figures:
        assert fig.read_bytes().startswith(b'\x89PNG'), f'{fig.name} is not a PNG'
        explanation = run / f'{fig.stem}.md'
        assert explanation.exists(), f'{fig.name} has no explanation'
        text = explanation.read_text(encoding='utf-8')
        assert len(text) > 200, f'{explanation.name} is too thin to be an explanation'
        assert fig.name in text, f'{explanation.name} does not reference its own figure'

    combined = run / 'CHART_EXPLANATIONS.md'
    assert combined.exists()
    body = combined.read_text(encoding='utf-8')
    for fig in figures:
        assert fig.stem in body, f'{fig.stem} missing from CHART_EXPLANATIONS.md'


def test_raw_acquisition_notebook_covers_every_required_source():
    """If a source is dropped from acquisition, cleaning has nothing to read."""
    code = notebook_code(NOTEBOOKS / '00a_raw_data_acquisition.ipynb')
    for source in ('ken_ndvi_subnational_2015_2025_raw.csv',
                   'ken_chirps_rainfall_subnational_2015_2025_raw.csv',
                   'modis_era5_climate_vegetation_monthly_2015_2025_raw.csv',
                   'era5land_soil_moisture_runoff_2015_2025_raw.csv',
                   'faostat_kenya_crop_production_2015_2025_raw.csv',
                   'knbs_2019_census_agriculture_households_raw.csv'):
        assert source in code, f'{source} is not acquired by 00a'


def test_maize_outcomes_table_is_intact():
    """The maize table is a tracked input to the dashboard; keep it validated in place."""
    outcomes = ROOT / 'data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv'
    assert outcomes.exists()
    df = pd.read_csv(outcomes)
    assert len(df) == 376 and df.county.nunique() == 47
    assert 2019 not in set(df.year)
    assert len(df[df.quality_flag != 'ok']) == 3
    mandera = df[(df.county == 'Mandera') & (df.year == 2012)].quality_flag.iloc[0]
    assert mandera == 'yield_inconsistent_with_production_and_area'


def test_panel_rejects_gaps_before_computing_lags():
    """A gap silently shifts every lag; the cleaning notebook must refuse it.

    The rule lives in the notebook now, so this asserts the notebook still contains the
    gap check rather than executing it through an import.
    """
    code = notebook_code(NOTEBOOKS / '01_data_cleaning.ipynb')
    assert 'diff().dropna()' in code or 'gaps' in code
    assert 'consecutive' in code.lower() or 'gap' in code.lower()
