# Historical maize outcome experiment

This experiment estimates **reported annual maize yield in tonnes per harvested hectare**, rather than the NDVI proxy. Four fixed regressors were fitted to 2015–2017, selected by 2018 validation MAE, and evaluated on a 2020 time-held-out sample. 2019 is absent. Training uses full-year weather, which makes this **retrospective estimation**, not an early forecast. The third-party workbook is unverified against its primary source; the climate data provenance is also unverified. The small single-year evaluation is insufficient for an operational system.

The selected Ridge model's 2020 MAE was 0.394 tonnes/ha for 46 counties; a simple prior-county-yield average achieved 0.383 tonnes/ha. The chosen model therefore did not outperform this baseline on MAE. This is an important reason it is **not promoted for live predictions**. Selection and all-model 2020 metrics are now visible, so this year must not be treated as untouched for subsequent tuning. Future deployment requires independently verified outcomes, publication/availability dates, forecast-time features, later holdout evaluation, calibration, and expert review.

`metrics.json` contains all metrics and source hashes; `model_panel.csv` and `predictions.csv` provide the evaluated inputs and row-level outputs. Four fitted artifacts are research-only. No forage outcome model has been trained from these maize records.

Reproduce into a new empty directory: `python ml-models/scripts/maize_outcome_experiment.py --output <new-directory>`.
