# Changes made

This log maps the current work on the AgriShield branch. No repository data, notebooks, or trained champion artifact was deleted for the current request. Existing frontend helper files that had been removed during earlier work on this branch were restored as inactive reference code. The active frontend remains API-only.

## Live weather map

- `apps/backend/routers/live.py`, `apps/backend/main.py`: new authenticated-by-existing-mode `/api/v1/live/weather` endpoint. Requests current modelled weather from Open-Meteo for 47 representative county coordinates; validates coverage, ordering, timestamps, values and interval; caches successful data for ten minutes; rejects stale or failed responses. No historical fallback or fabricated risk score.
- `apps/frontend/shared/api_client.py`, `apps/frontend/streamlit_app.py`: new Live conditions page, point map, timestamps, indicator selection and table. It identifies data as modelled point weather, not county-average weather, a crop/forage outcome or official risk. Refreshes every ten minutes. Open-Meteo attribution and terms are linked.
- `data_pipeline/data/external/SOURCES.md`: documents Open-Meteo, source restrictions and the distinction from outcome data.
- The API requires outbound access to `api.open-meteo.com`. In this sandbox, direct requests from the backend are blocked. We verified the provider response using the web retrieval tool, and tested the application with a controlled HTTP response; the actual backend-to-provider connection remains unverified here. The dashboard reports unavailability instead of substituting data.

## Private assessment history

- `apps/backend/database/models.py`, `apps/backend/migrations/versions/20261120_history.py`: new separate history table and migration; existing report records and model artifacts remain unchanged.
- `apps/backend/routers/history.py`, `apps/backend/main.py`: create a random private key, explicitly save complete verified manual or historical results, list/retrieve/download/delete only with that key. Only its SHA-256 hash is stored. Saved snapshots are rendered without rescoring. Valid records expire after 90 days; 500 most recent are listed. Losing the key means losing access; anyone with it has access.
- `apps/frontend/shared/api_client.py`, `apps/frontend/streamlit_app.py`: History page, private key creation/recovery and download, explicit save buttons, SHAP display, PDF download, deletion and session locking. Old separate seven-day report snapshots are not automatically imported.
- `apps/backend/scripts/cleanup_reports.py`: also purges expired history; schedule this command for physical deletion. Records are additionally purged when later history is saved. This is capability access, not per-user account ownership; production privacy and rate limiting still need review.

## Data sources, cleaning and EDA

- `data_pipeline/data/external/SOURCES.md`: source catalogue covering 4TU/NDMA impact research, HDX Kisumu crop data, Kilimo maize data, NDMA bulletins and Open-Meteo, including links, licenses where reported, time/spatial coverage and caveats.
- `data_pipeline/scripts/download_external.py`: additive downloader for the two 4TU files. Checks the publisher's MD5, size and existing files before writing. The original CSV and README were **not** downloaded here because direct access to `data.4tu.nl` is blocked in this sandbox. Run the script from a permitted network. The 4TU dataset covers six counties and includes only impact periods; missing periods must not be assumed negative. It was not used as nationwide model ground truth.
- `data_pipeline/scripts/save_eda.py`, `data_pipeline/requirements.txt`: additive reproducible EDA; preserves prior output by refusing to overwrite nonempty directories. Existing dependencies were retained; NumPy/Matplotlib limits were updated.
- `data_pipeline/outputs/panel_2026_11_20/`: saved 6,204-row cleaned panel, imputation flags, rainfall/NDVI seasonality charts and `EDA_ANALYSIS.md`. The output is based on existing harmonized sources; 132 soil-moisture values were filled with explicit same-month national means. The panel's original provenance and licenses still need verification.
- `data_pipeline/legacy_reference/`: reference copies of the branch-base versions of the four pipeline scripts that were updated earlier in this session. The current pipeline scripts and notebooks remain in place; the archive is not executed.

## Model retraining

- `ml-models/scripts/train.py`: patched to save all four trained models and refuse to overwrite a nonempty output directory. The script retains the existing split and does not promote a model.
- `ml-models/research_runs/2026_11_20/`: saved logistic regression, random forest, XGBoost and LightGBM research artifacts; selected research candidate; dataset hash, package versions, metrics, individual predictions and county/month breakdowns. XGBoost was selected on 2022–2023 validation. This run uses the existing NDVI-derived target and explicitly imputed panel; it does not train real crop loss or forage outcomes. The 2024–2025 evaluation was used previously and is not an independent holdout. Deployed LightGBM unchanged.
- `ml-models/legacy_reference/`: reference copies of branch-base train/evaluate scripts; not used for inference.
- `.gitignore`: narrowly permits the small generated panel and research-run CSV evidence to be saved. Normal large/generated output exclusions remain.

## Tests, setup and documentation

- `tests/test_frontend.py`: weather response validation, cache/stale/failure handling, key isolation and expiration, immutable history, and UI flows.
- `tests/test_pipeline.py`: source download hash/no-overwrite, saved EDA outputs, all four model artifacts and no-overwrite training.
- `.github/workflows/ci.yml`: installs Matplotlib required by the EDA test.
- `README.md`, `apps/frontend/README.md`: setup, data sources, live weather limits, private history and generated research outputs.
- Verification: `pytest tests -q` passed 46 tests; local SQLite migration to `20261120_history` succeeded; `git diff --check` clean. Tests for the live provider are controlled contract tests, not proof of a working production connection. No external AI, hosted database or authentication service was verified.

## Prior branch work retained

- Earlier work on this same branch added the validated manual and historical prediction API, API-only Streamlit dashboard, Gria evidence/SHAP analysis, protected report snapshots, document text extraction, dataset preparation and four-model retrospective comparison. The relevant earlier modifications include `apps/backend/routers/{manual_predictions,snapshot_reports,gria,documents,legacy}.py`, `apps/backend/services/{prediction_service,analysis_service}.py`, `apps/backend/agents/`, `apps/backend/schemas/`, `apps/frontend/streamlit_app.py`, `data_pipeline/scripts/`, `ml-models/scripts/`, and `docs/DATA_MODEL_CARD.md`. Legacy unsafe HTTP endpoints remain explicitly retired. Original frontend helper files and branch-base pipeline/model script references are preserved; they are not the active path.

## Additional work: reported maize outcomes (follow-up request)

- `data_pipeline/data/external/knbs_candidate/`: preserved the downloaded third-party mirrored workbook, SHA-256 and source details, and added normalized outcome rows with quality flags. The primary source and redistribution rights have not been independently verified; 2019 is missing. Three questionable records are flagged, not changed.
- `data_pipeline/scripts/prepare_maize_outcomes.py`, `data_pipeline/scripts/maize_eda.py`, `data_pipeline/outputs/maize_2026_11_20/`: reproducible non-destructive preparation and maize outcome chart/analysis. `data_pipeline/data/external/SOURCES.md` records source and caveats.
- `apps/backend/routers/outcomes.py`, `apps/backend/main.py`, `apps/backend/Dockerfile`, `apps/frontend/shared/api_client.py`, `apps/frontend/streamlit_app.py`: historical **reported maize yield** map, data table and quality flags; no claim of live risk.
- `ml-models/scripts/maize_outcome_experiment.py`, `ml-models/research_runs/maize_2026_11_20/`, `.gitignore`: trained and saved four regressors against reported maize yield, validation on 2018 and time-held-out 2020 metrics and predictions. Selected Ridge 2020 MAE 0.394 tonnes/ha vs 0.383 for a historical county-mean baseline. The full-year weather inputs and unverified sources do not support a live forecast or operational promotion.
- `README.md`, `tests/`: documentation and checks. No source data or existing models were overwritten.

## Verification and current state (2026-11-20)

- **Test suite:** 50 tests passed (including new pipeline preparation, experiment holdout, and frontend outcome map tests). `git diff --check` clean; `.venv/bin/python -m compileall` clean.
- **Process state:** API server (port 8000) and Streamlit dashboard (port 8501) restarted and healthy. `/api/v1/health` returns 200 OK. `/api/v1/outcomes/maize-years` returns `[2020,2018,2017,2016,2015,2014,2013,2012]`. `/api/v1/outcomes/maize?year=2020` returns 47 observations (46 valid, 1 zero-area flagged).
- **Git tracking:** `data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv` is explicitly tracked via `.gitignore` exception `!data_pipeline/data/** data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv` (line 54). All other `.csv` files remain globally ignored.
- **Docker packaging:** `apps/backend/Dockerfile` explicitly copies `maize_outcomes_clean.csv` to `/app/data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv`.
- **County metadata:** `COUNTY_METADATA` imported successfully in `apps/backend/routers/outcomes.py` and used for validation.

## Outstanding constraints

- **Validated crop/forage outcomes:** The delivered data is **historical reported maize yield** (KNBS/Kilimodata mirror), which is an outcome candidate but **not independently validated crop-loss or forage data** (e.g., NDMA or field-verified forage loss). The primary workbook and redistribution rights remain unverified.
- **Fully functional live agricultural risk map:** The requested live risk map requires **current feature feeds and operational crop/forage loss targets**, which are **not available** in this sandbox or verified from external sources. The current implementation provides:
  1. Historical reported maize yield map (retrospective, not live risk).
  2. Live weather map (modelled point weather, explicitly not agricultural risk; returns 503 in sandbox backend connectivity).
  3. Private assessment history (capability-key snapshots, not live risk).
- **Model deployment:** The four-model maize experiment (Ridge selected, 2020 MAE 0.394 t/ha vs baseline 0.383 t/ha) is **research-only** and **not promoted** for live predictions. No forage outcome model exists.
- **No false claims:** The implementation explicitly labels historical yields and weather data, refusing to label them as live risk or operational forecasts. No external AI, hosted database, or production live connectivity has been demonstrated.

**Conclusion:** The requested validated crop/forage outcomes and fully functional live agricultural risk map **remain unmet** due to the absence of verified nationwide live outcome datasets, operational risk models, and permitted live backend connections in this sandbox. The delivered work provides the closest compliant implementation: historical reported maize outcome endpoints, experiment artifacts, and process-verified tests, while preserving all existing code and documentation.
