"""Data and experimental workflow tests."""
from pathlib import Path

import pandas as pd
import pytest

from data_pipeline.scripts.experiment import DEFAULT_PANEL, FEATURES, build_experiment, load_panel

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
        # duplicate detection is performed while loading, tested separately below
        assert bad.duplicated(['county', 'year', 'month']).any()
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.csv') as tmp:
            bad.to_csv(tmp.name, index=False)
            load_panel(tmp.name)


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
    import pandas as pd

    from data_pipeline.scripts.experiment import load_panel
    panel = pd.read_csv(DEFAULT_PANEL)
    panel = panel.drop(index=panel.index[1])
    filename = tmp_path / 'gap.csv'
    panel.to_csv(filename, index=False)
    with pytest.raises(ValueError, match='consecutive'):
        load_panel(filename)


def test_download_external_verifies_and_never_overwrites(tmp_path, monkeypatch):
    import hashlib
    from io import BytesIO

    from data_pipeline.scripts import download_external
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
