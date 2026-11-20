# 🌿 AgriShield

**A Kenya-focused agricultural data science and decision-support prototype.** AgriShield brings together a Streamlit dashboard, FastAPI, an existing LightGBM model, historical county-level data, and Gria, an optional AI assistant.

> **Research limitation:** The deployed model estimates a synthesized low-vegetation-greenness (NDVI) proxy. It is **not** a validated prediction of crop loss or livestock forage deficit, a calibrated probability, a live forecast, or an official warning. Historical inputs include proxy and imputed data. Do not use it alone for operational decisions.

## What works

- Enter a complete set of model features or supply underlying measurements for backend feature engineering.
- Upload a one-row CSV with the exact model inputs; the backend validates and scores it without filling missing values.
- Inputs outside the model's recorded training ranges are **rejected** with the offending field and a unit hint. A deliberate `accept_extrapolation=true` opt-in scores them and flags the result as an extrapolation everywhere it appears.
- View reported historical county maize yields separately from model outputs; source provenance is not independently verified.
- View a live modelled weather map at representative county points when Open-Meteo is reachable; this is not a live crop/forage risk map.
- Save assessments privately for up to 90 days using a user-held history key.
- View visual SHAP contributions, training-range checks, historical county maps, score distributions, comparisons, and weather/vegetation trends. Compare two complete user-provided scenarios without treating them as forecasts.
- Create capability-protected, immutable, branded PDF reports, with optional Gria analysis of a user assessment or historical county evidence.
- Extract text from TXT, text-based PDF and DOCX for review and optionally send it to Gria. Text does **not** become model input. Image-based NDVI and OCR are not supported.
- Run a repeatable four-model retrospective research experiment on local data without overwriting the deployed model.

The Streamlit frontend calls the FastAPI backend for all scoring and application operations. It does not run an embedded model or fabricate fallback results.

## Getting started

Requires Python 3.11 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/backend/requirements.txt -r apps/frontend/requirements.txt \
  -r data_pipeline/requirements.txt -c constraints.txt

cd apps/backend
alembic upgrade head     # creates/updates every table (init_db.py is an alias)
python seed_counties.py  # idempotent
uvicorn main:app --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
source .venv/bin/activate
export AGRISHIELD_API_URL=http://127.0.0.1:8000/api/v1
cd apps/frontend
streamlit run streamlit_app.py --server.address 0.0.0.0
```

The local API documentation is at `http://127.0.0.1:8000/docs` and Streamlit uses port 8501. `GET /api/v1/health` is a liveness probe; `GET /api/v1/health/ready` checks the model hash, a probe inference, and the database, and returns 503 when the deployment cannot score. See [the deployment runbook](docs/DEPLOYMENT.md) for release, rollback, retention and backup steps. The API URL is resolved by the **Streamlit server**, not the user's browser. See [frontend setup and input definitions](apps/frontend/README.md) for deployment and configuration. The Render blueprint deploys the backend; it does not deploy Streamlit. Build the API container from the repository root with `docker build -f apps/backend/Dockerfile .`.

## Research pipeline

The research pipeline uses already-harmonized local source tables; its research inputs are not live. The dashboard has a separate Open-Meteo current-weather layer. To explicitly join the local tables and impute missing values using the national mean for the same month, then run the retrospective comparison:

```bash
python data_pipeline/scripts/clean_data.py --impute-national-monthly \
  --output ml-models/experiments/cleaned_panel.csv
python ml-models/scripts/train.py --panel ml-models/experiments/cleaned_panel.csv \
  --output ml-models/experiments/run-01
python ml-models/scripts/evaluate.py
# Optional, on a network that can reach data.4tu.nl:
python data_pipeline/scripts/download_external.py
```

The clean step refuses to overwrite existing output and emits imputation flags. The experiment uses 2015–2021 for training, 2022–2023 for model selection, and reports 2024–2025 separately. **All these years have been explored before; 2024–2025 is not an independent final test.** It uses same-month weather, historical baseline statistics, and retrospective demographic data, so it is not a demonstrated forward-looking forecast. It outputs metrics, per-county and per-month breakdowns, predictions, dataset hash, package versions, and a research candidate artifact and all four fitted models. It never replaces the production model.

Read the [data and model card](docs/DATA_MODEL_CARD.md) before interpreting results. The [original model comparison report](docs/reports/ML_Model_Comparison_Report_2015_2025.md) describes the existing champion, not the new experiment.

## Tests and linting

```bash
pip install -r apps/backend/requirements-dev.txt -r apps/frontend/requirements.txt -c constraints.txt
ruff check .
python -m pytest tests -q
```

Tests cover the real model/input contract, the training-range rejection and
extrapolation flags, raw feature derivation, the API-only UI (every dashboard page is
rendered in-process), protected-mode authentication, document extraction limits,
report authorization and retention, history capabilities, live-weather failure
handling, migration round-trips, and the research training pipeline. `tests/conftest.py`
provisions a throwaway SQLite database from the migrations, so a run never touches
your development database. CI additionally runs `ruff`, applies and rolls back
migrations, and audits dependencies.

## Security and deployment

The default is a public prototype. **Production fails closed:** with `APP_ENV=production`, `core/config.py` refuses to start unless `PUBLIC_MODE=False`, Supabase is configured, `DATABASE_URL` is set, secrets are non-placeholder, and `CORS_ORIGINS` lists explicit origins. Protected mode requires a configured Supabase identity provider; see `apps/backend/.env.example`.

The model artifact is verified against its recorded SHA-256 before `joblib.load`, and `/health/ready` reports a mismatch instead of serving scores from an unexpected model. The dashboard can use an authorized `AGRISHIELD_API_TOKEN` when protected mode is enabled. Gria is optional; without a configured working NVIDIA service it returns a labelled historical summary, not an AI answer. Questions and optional document text may be sent to the AI provider; avoid personal or sensitive information.

Assessment reports use a random access capability; the API returns it once, and it must be supplied in `X-Report-Token`. Reports expire after seven days, can be deleted with their token, and expired rows are removed when a later report is created. This is not a scheduled deletion guarantee; schedule `python apps/backend/scripts/cleanup_reports.py` against the configured database for a strict retention policy. The UI keeps the capability only in the active session and lets the user delete the current saved report.

The former prediction, forecast, upload, storage and report-history APIs could produce assumed values, expose files, or regenerate a different report. They now return **410 Gone**, listed one path at a time in `routers/legacy.py`: an earlier catch-all pattern also swallowed every live route under `/predictions`, so retirement is explicit and a new endpoint cannot be shadowed by accident. Public deployment still needs a security review, HTTPS, edge rate limits and quotas, durable storage, backups, monitoring, controlled credentials, a retention job, and an approved privacy policy. No claim of legal compliance or production readiness is made.

## Repository map

- `apps/frontend/` — Streamlit presentation and API client. The county map (colour scale, labelling, why it is not a tile basemap) is documented in [docs/MAP_DESIGN.md](docs/MAP_DESIGN.md).
- `apps/backend/` — FastAPI, inference, document extraction, reports, auth, database and migrations. Every module here is reachable from `main.py`; retired routes live in `routers/legacy.py` and answer 410 explicitly.
- `pyproject.toml` — ruff and pytest configuration. `constraints.txt` pins the resolved dependency set.
- `docs/` — [CHANGELOG](docs/CHANGELOG.md) (every change with file paths and reasons), [deployment runbook](docs/DEPLOYMENT.md), [map design](docs/MAP_DESIGN.md), [data and model card](docs/DATA_MODEL_CARD.md).
- `data_pipeline/` — local data, cleaning, feature-building and exploration.
- `ml-models/` — retrospective model training and evaluation.
- `tests/` — API, model, UI, data and database tests.
- `docs/` — research documents and reports; some historical documents describe earlier project iterations.

## License

See [LICENSE](LICENSE).

## Live weather and private history

The **Live conditions** page asks the backend for Open-Meteo's current model estimates at one representative point in each county. It refreshes approximately every ten minutes, displays provider timestamps and interval, and refuses stale or unavailable data rather than substituting history. These are not field observations, county averages, crop/forage outcomes or risk predictions. Open-Meteo's free service is intended for non-commercial use; check [its terms](https://open-meteo.com/en/terms) and attribution. Deployment must permit outbound access to `api.open-meteo.com`; this sandbox's network policy blocks the backend from reaching it.

The **History** page creates or accepts a private key. Save that key securely outside the app: anyone holding it can read and delete the associated records, and it cannot be recovered. Save a manual or historical assessment explicitly; older reports are not imported automatically. Stored history snapshots remain accessible for 90 days, with deletion available in the UI. Expired rows are purged on future saves or by the scheduled cleanup command above. This capability is separate from account ownership, and user data must not be stored there without appropriate security review and consent.

Saved research output: `data_pipeline/outputs/panel_2026_11_20/` contains the cleaned panel, charts and EDA; `ml-models/research_runs/2026_11_20/` contains all four fitted models, metrics and predictions. The run is retrospective and does not promote the model. Candidate external sources and download instructions are in `data_pipeline/data/external/SOURCES.md`.

## Reported maize outcome research

`data_pipeline/data/external/knbs_candidate/` contains a third-party mirror of a historical county maize workbook and a quality-flagged table; the primary file and redistribution rights have not been verified. The Reported maize yields dashboard page displays annual historical yield, not live crop-loss risk. `data_pipeline/outputs/maize_2026_11_20/` contains a descriptive chart and analysis.

`ml-models/scripts/maize_outcome_experiment.py` trains four models against reported maize yield and evaluates 2020 after 2018 selection. The results and limitations are saved under `ml-models/research_runs/maize_2026_11_20/`. The selected research model was slightly worse on 2020 MAE than the prior-county-yield baseline and uses full-year weather; it has **not** been deployed as a live crop-risk model. No genuine forage outcome model or live agricultural risk map has been validated.
