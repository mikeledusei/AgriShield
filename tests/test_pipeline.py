"""Data and experimental workflow tests."""
import importlib.util
from pathlib import Path
import pandas as pd
import pytest
from data_pipeline.scripts.experiment import FEATURES, build_experiment, load_panel, DEFAULT_PANEL

ROOT = Path(__file__).resolve().parents[1]


def test_panel_validation_and_split_baselines():
    panel = load_panel()
    assert len(panel) == 6204
    features = build_experiment(panel, train_end=2021)
    assert features[FEATURES].notna().all().all()
    # Changing validation observations must not affect the fitted county threshold.
    changed = panel.copy()
    changed.loc[changed.year >= 2022, 'ndvi_mean'] = 0.99
    modified = build_experiment(changed, train_end=2021)
    old = features.loc[features.year <= 2021, 'ndvi_25th_pct'].reset_index(drop=True)
    new = modified.loc[modified.year <= 2021, 'ndvi_25th_pct'].reset_index(drop=True)
    pd.testing.assert_series_equal(old, new)
    with pytest.raises(ValueError, match='Duplicate'):
        bad = pd.concat([panel, panel.iloc[[0]]])
        file = ROOT / 'data_pipeline/data/processed/ml_base_2015_2025.csv'
        # duplicate detection is performed while loading, tested separately below
        assert bad.duplicated(['county', 'year', 'month']).any()
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.csv') as tmp:
            bad.to_csv(tmp.name, index=False)
            load_panel(tmp.name)


def test_end_to_end_experiment_does_not_promote_model(tmp_path):
    path = ROOT / 'ml-models/scripts/train.py'
    spec = importlib.util.spec_from_file_location('research_train', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.run_experiment(DEFAULT_PANEL, tmp_path)
    assert report['selected_on_validation'] in report['results']
    assert 'NOT an independent holdout' in report['evaluation']
    assert (tmp_path / 'research_candidate.joblib').exists()
    for name in ['logistic_regression', 'random_forest', 'xgboost', 'lightgbm']:
        assert (tmp_path / f'{name}.joblib').exists()
    with pytest.raises(ValueError, match='not empty'):
        module.run_experiment(DEFAULT_PANEL, tmp_path)
    assert (tmp_path / 'metrics.json').exists()
    assert (tmp_path / 'predictions.csv').exists()
    for result in report['results'].values():
        assert result['validation_2022_2023']['samples'] > 0


def test_cleaning_requires_explicit_imputation_and_preserves_flags():
    from data_pipeline.scripts.clean_data import clean_data
    with pytest.raises(ValueError, match='imputation'):
        clean_data()
    cleaned = clean_data(impute_national_monthly=True)
    assert len(cleaned) == 6204
    assert cleaned['soil_moisture_mean_imputed'].sum() == 132
    assert cleaned['soil_moisture'].notna().all()
    assert cleaned['county'].nunique() == 47


def test_panel_rejects_gaps_before_computing_lags(tmp_path):
    from data_pipeline.scripts.experiment import DEFAULT_PANEL, load_panel
    import pandas as pd
    panel = pd.read_csv(DEFAULT_PANEL)
    panel = panel.drop(index=panel.index[1])
    filename = tmp_path / 'gap.csv'
    panel.to_csv(filename, index=False)
    with pytest.raises(ValueError, match='consecutive'):
        load_panel(filename)


def test_download_external_verifies_and_never_overwrites(tmp_path, monkeypatch):
    import hashlib
    from data_pipeline.scripts import download_external
    from io import BytesIO
    content = b'original research data\n'
    monkeypatch.setattr(download_external, 'OUT', tmp_path / 'external')
    monkeypatch.setattr(download_external, 'FILES', {'source.csv': ('https://example.invalid/data', hashlib.md5(content, usedforsecurity=False).hexdigest())})
    monkeypatch.setattr(download_external.urllib.request, 'urlopen', lambda *args, **kwargs: BytesIO(content))
    download_external.download()
    assert (download_external.OUT / 'source.csv').read_bytes() == content
    (download_external.OUT / 'source.csv').write_bytes(b'modified')
    with pytest.raises(ValueError, match='refusing to overwrite'):
        download_external.download()


def test_eda_saves_flagged_data_and_plots_without_overwriting(tmp_path):
    from data_pipeline.scripts.save_eda import save_eda
    out = tmp_path / 'eda'
    save_eda(out)
    panel = pd.read_csv(out / 'cleaned_panel.csv')
    assert panel['soil_moisture_mean_imputed'].sum() == 132
    assert (out / 'rainfall_by_month.png').read_bytes().startswith(b'\x89PNG')
    assert (out / 'ndvi_by_month.png').read_bytes().startswith(b'\x89PNG')
    assert '6,204' in (out / 'EDA_ANALYSIS.md').read_text()
    with pytest.raises(ValueError, match='not empty'):
        save_eda(out)


def test_maize_outcomes_have_real_years_and_quality_flags():
    from data_pipeline.scripts.prepare_maize_outcomes import prepare
    result = prepare()
    assert len(result) == 376 and result['county'].nunique() == 47
    assert 2019 not in set(result.year)
    assert len(result[result.quality_flag != 'ok']) == 3
    assert result.loc[(result.county == 'Mandera') & (result.year == 2012), 'quality_flag'].iloc[0] == 'yield_inconsistent_with_production_and_area'


def test_maize_experiment_holdout_and_baseline_are_separate(tmp_path):
    path = ROOT / 'ml-models/scripts/maize_outcome_experiment.py'
    spec = importlib.util.spec_from_file_location('maize_experiment', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = pd.read_csv(module.OUTCOMES)
    original = module.build_panel()
    # An altered validation target must not influence the held-out county baseline.
    data.loc[data.year == 2018, 'yield_tonnes_per_ha'] = 999
    changed = tmp_path / 'changed.csv'
    data.to_csv(changed, index=False)
    altered = module.build_panel(changed, module.CLIMATE)
    pd.testing.assert_series_equal(original.loc[original.year == 2020, 'prior_yield_mean'].reset_index(drop=True),
                                   altered.loc[altered.year == 2020, 'prior_yield_mean'].reset_index(drop=True))
    out = tmp_path / 'results'
    report = module.run(out)
    assert report['target'].startswith('Reported annual maize yield')
    assert report['results'][report['selected_model']]['holdout_2020']['samples'] == 46
    assert all((out / f'{name}.joblib').exists() for name in ['ridge', 'random_forest', 'xgboost', 'lightgbm'])
    with pytest.raises(ValueError, match='not empty'):
        module.run(out)
