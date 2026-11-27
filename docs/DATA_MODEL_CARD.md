# AgriShield data and model card

## Purpose and target

The deployed artifact is `apps/backend/ml_artifacts/champion_model.joblib` (XGBoost, validation F1 0.8689) with the feature ordering in `feature_columns.json`. The original notebooks create a binary label when a county-month's NDVI falls below that county's 2015–2023 25th percentile. This is a **synthesized proxy for low vegetation greenness**, not a measurement of crop loss, pasture biomass, animal feed demand, or food insecurity. Crop and livestock selections do not represent two independently validated outcome models.

The classifier's output has not been calibrated as a real-world probability. The four displayed bands are descriptive interface groupings, not validated alert thresholds. SHAP contributions explain this model's output in log-odds, not causal effects or percentage-point changes. Ground-truth data, independent evaluation, threshold selection, expert review and stakeholder testing are needed before operational use.

## Data and provenance

The checked-in panel contains 6,204 county-month rows for 47 counties from 2015 through 2025. The repository labels the inputs as satellite vegetation, weather/reanalysis and 2019 census household data. The original notebooks provide the available transformations; source acquisition, licenses, publication dates, revision history, and complete provenance have **not been independently verified** by the new workflow. There is no live data connection in this repository. Review the raw data and provider terms before external use.

The harmonized `Weather_FINAL.csv` has 132 missing soil-moisture entries. `clean_data.py` refuses missing values by default; the explicit `--impute-national-monthly` option fills them with the mean across available counties in that same year and month and records `*_imputed` flags. This is an assumption, not an observation. The existing `ml_base_2015_2025.csv` was already imputed by earlier notebooks. The demographic counts are based on a static 2019 snapshot, repeated across the panel.

The deployed model uses 16 columns: cyclic month sine/cosine; one- and three-month NDVI lags; three-month NDVI mean and standard deviation; NDVI anomaly; same-month temperature, rainfall and soil moisture; rainfall anomaly and three-month total; forage dryness indicator; farming, livestock and irrigation ratios. The backend form lists units and exact calculation guidance. `training_feature_ranges.json` records per-feature minimum and maximum values from the existing 2015–2023 training matrix, tied to the saved model by SHA-256. Out-of-range inputs are flagged; being inside each range does not prove the combined input is in distribution. The same-month weather variables are not available at the beginning of that month, so the current model is not established as an early forecast. Training-wide county baselines and 2019 demographics also contain retrospective information when applied to early training rows.

## Evaluation

The original comparison chose the LightGBM champion using 2024–2025 results, so those results are **not independent final-test estimates**. For the checked-in labels and champion, the existing evaluation yields 44 true positives, 67 false positives, 1,017 true negatives and zero false negatives (44 positives among 1,128 county-months, at the model's class threshold). This is performance against the synthesized label, not verified disasters. The reported 100% recall is based on only 44 positive examples; it does not establish performance on future events.

The notebook sequence in `ml-models/notebooks/` is a separate retrospective research experiment (the former `ml-models/scripts/train.py` is archived in `ml-models/legacy_reference/`). It fits county thresholds and rainfall baselines on 2015–2021, selects among logistic regression, random forest, XGBoost and LightGBM using 2022–2023 F1 and ROC-AUC, and separately reports 2024–2025. The earlier work has already examined all these periods. The output includes confusion counts, precision, recall, F1, ROC-AUC, average precision, Brier score, county/month slices, feature list, source hash, and software versions. The model is **not** promoted automatically. No claim of leakage-free forecasting or independent validation is made.

## What is needed next

- Verify original sources, quality flags, missingness, licenses and processing history.
- Agree on separately measured, dated crop-yield and forage-deficit outcomes and acquire appropriate data.
- Define forecast issue time, lead time, source availability and publication delay for every feature.
- Build rolling, time-aware training/validation and obtain truly untouched, later external evaluation data.
- Calibrate outputs and choose decision thresholds with domain experts; evaluate false alarms and misses by county, season and livelihood.
- Test Gria grounding, accessibility, decision-making and report comprehension with consented intended users.
- Review privacy, authorization, retention and operational risks before a public or government pilot.

## Requirements for genuine live crop and forage outcomes

To replace the proxy responsibly, agree with data owners and agricultural experts on (1) crop and forage targets, units, county boundaries, forecast horizons and decision thresholds; (2) trusted, dated county-level outcome records, provenance, coverage and rights; and (3) reliable observation feeds with publication timestamps, quality flags, allowed use, and refresh schedules. County yield or measured crop loss and measured forage availability or deficit require **separate outcome definitions and models**. The national marketed-value crop table in this repository does not provide county-level crop losses or forage outcomes.

## Accepted input distribution

The API rejects feature values outside the ranges recorded in
`apps/backend/ml_artifacts/training_feature_ranges.json`, which are the min/max of the
training matrix. This is a distribution check, not a guarantee of accuracy: an
in-range value can still be rare, correlated implausibly with the others, or measured
with a different definition. A caller who supplies `accept_extrapolation=true` receives
a score with `extrapolated: true` and `training_range_warnings`; stored reports, PDFs and
the dashboard all carry that label. Of the 6,204 packaged county-months, five (all in
the held-out 2024 flood season) fall outside the training range — an example of why the
check exists rather than evidence that the model is right everywhere else.

A production pipeline then needs source adapters, automated ingestion and monitoring, freshness indicators, handling for missing and delayed data, as-of feature generation, independent temporal and geographic validation, calibration, documented alert thresholds, expert review of suggested actions, audit and monitoring, and live service/security verification. Until those prerequisites exist, neither a real-time map nor genuine outcome forecasts can be verified. Displaying the latest stored historical period as live would be misleading.
