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

Each component has **one** `requirements.txt` and its **own** virtual environment.
There is no environment at the repository root; there is no second requirements file
per component.

```bash
# Run from the repository root. Windows: use <dir>\venv\Scripts\activate
for d in apps/backend apps/frontend data_pipeline ml-models; do
  python -m venv "$d/venv"
  "$d/venv/bin/pip" install -r "$d/requirements.txt" -c constraints.txt
done
```

| Component | Environment | Contains |
| --- | --- | --- |
| `apps/backend` | `apps/backend/venv` | API, tests and linting, plus the research stack |
| `apps/frontend` | `apps/frontend/venv` | Streamlit dashboard (HTTP-only, no ML stack) |
| `data_pipeline` | `data_pipeline/venv` | cleaning scripts and EDA notebooks |
| `ml-models` | `ml-models/venv` | research notebooks: sklearn, xgboost, lightgbm, shap |

You do not need all four to work on one part: the backend venv alone can run the API
and the whole test suite, because that is where the tests live.

### 1. Backend (terminal 1)

```bash
source apps/backend/venv/bin/activate
cd apps/backend
alembic upgrade head     # creates/updates every table (init_db.py is an alias)
python seed_counties.py  # idempotent; adds the 47 counties
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

No configuration is needed for local use: with `DATABASE_URL` unset the API uses a
SQLite file at `apps/backend/agrishield.db`, and `PUBLIC_MODE` defaults to on. Check it is
healthy before moving on:

```bash
curl http://127.0.0.1:8000/api/v1/health/ready
# {"status":"ready", ..., "problems":[]}     <- 200 when ready, 503 with a problems list when not
```

`/health` is only liveness. `/health/ready` is the one that proves the model loaded and
the migrations were applied.

### 2. Frontend (terminal 2)

```bash
source apps/frontend/venv/bin/activate
cd apps/frontend
cp .env.example .env             # optional; the default already points at :8000
streamlit run streamlit_app.py
```

Open <http://localhost:8501>. `apps/frontend/.env` is read automatically (a real
environment variable still takes precedence), so `AGRISHIELD_API_URL` can be set in the
file instead of the shell:

```bash
AGRISHIELD_API_URL=http://127.0.0.1:8000/api/v1
```

The dashboard talks to the API **from the Streamlit server process**, not from your
browser, so a Docker-hosted API must be reachable from the machine running Streamlit.

The local API documentation is at `http://127.0.0.1:8000/docs` and Streamlit uses port 8501. `GET /api/v1/health` is a liveness probe; `GET /api/v1/health/ready` checks the model hash, a probe inference, and the database, and returns 503 when the deployment cannot score. See [the deployment runbook](docs/DEPLOYMENT.md) for release, rollback, retention and backup steps. The API URL is resolved by the **Streamlit server**, not the user's browser. See [frontend setup and input definitions](apps/frontend/README.md) for deployment and configuration. The Render blueprint deploys the backend; it does not deploy Streamlit. Build the API container from the repository root with `docker build -f apps/backend/Dockerfile .`.

## Data pipeline

`data_pipeline/` is notebook-only; there are no scripts. Run the notebooks in order:

| Notebook | Does | Needs network |
| --- | --- | --- |
| `00a_raw_data_acquisition.ipynb` | Downloads every raw source into `data/raw/`, verifies and hashes it, writes `MANIFEST.json` | **yes, first time only** |
| `00_data_ingest.ipynb` | Loads and inspects the raw files, checks all 47 counties are present | no |
| `01_data_cleaning.ipynb` | Cleans each source, joins the panel, validates it, writes `data/processed/*_FINAL.csv` and `master_cleaned_2015_2025.csv` | no |
| `02_eda.ipynb` | Produces seven charts in `outputs/eda_<date>/figures/` with a `.md` explanation for each, plus `CHART_EXPLANATIONS.md` | no |

### Getting the raw data

Only two of the six raw sources need any manual work; the rest are fetched with no API key:

```bash
source data_pipeline/venv/bin/activate
cd data_pipeline/notebooks
jupyter notebook 00a_raw_data_acquisition.ipynb   # run all cells
```

- **Automatic:** NDVI and CHIRPS rainfall (WFP via HDX), and monthly temperature, rainfall,
  soil wetness and runoff per county (NASA POWER point API, 47 counties × 11 years).
- **Manual:** the 2019 census agricultural households table and the FAOSTAT bulk download.
  The notebook prints exactly what to fetch and where to save it if it cannot download.

`01_data_cleaning.ipynb` **refuses to build the panel** while a source is missing rather
than zero-filling demographics for 47 counties, so a partial download fails loudly.

### Reading the EDA output

`02_eda.ipynb` writes one markdown file per chart *and* a combined
`CHART_EXPLANATIONS.md`. Each explanation states how to read the chart, why it matters for
the model, and what it does not prove. Start with the combined document.

## Research pipeline

The research pipeline uses already-harmonized local source tables; its research inputs are not live. The dashboard has a separate Open-Meteo current-weather layer. To explicitly join the local tables and impute missing values using the national mean for the same month, then run the retrospective comparison:

The research workflow is the notebook sequence in `ml-models/notebooks/`, run in order:

| Notebook | Produces |
| --- | --- |
| `00_data_loading.ipynb` | `ml_base_2015_2025.csv` — joins NDVI, Weather and Demographics |
| `01_target_synthesis.ipynb` | `county_ndvi_stats.csv`, `master_train_2015_2023.csv`, `master_test_2024_2025.csv` |
| `02_feature_engineering.ipynb` | `X/y_train`, `X/y_test`, `train_matrix`, `test_matrix`, `scaler.joblib` |
| `03_model_training.ipynb` | four fitted models + `feature_columns.json` |
| `04_model_evaluation.ipynb` | metrics and plots for the deployed champion |
| `05_model_comparison.ipynb` | `model_comparison_2015_2025.csv`, the report, and synced backend artifacts |

All six execute end to end from a clean clone. `05_model_comparison.ipynb` **copies its
models into `apps/backend/ml_artifacts/`**, overwriting the served artifacts, so treat
running it as a deployment action and review `git status` afterwards.

The clean step refuses to overwrite existing output and emits imputation flags. The experiment uses 2015–2021 for training, 2022–2023 for model selection, and reports 2024–2025 separately. **All these years have been explored before; 2024–2025 is not an independent final test.** It uses same-month weather, historical baseline statistics, and retrospective demographic data, so it is not a demonstrated forward-looking forecast. It outputs metrics, per-county and per-month breakdowns, predictions, dataset hash, package versions, and a research candidate artifact and all four fitted models. It never replaces the production model.

Read the [data and model card](docs/DATA_MODEL_CARD.md) before interpreting results. The [original model comparison report](docs/reports/ML_Model_Comparison_Report_2015_2025.md) describes the existing champion, not the new experiment.

## Tests and linting

```bash
source apps/backend/venv/bin/activate   # the venv with tests, lint and research deps
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

The maize outcome experiment trains four models against reported maize yield and evaluates 2020 after 2018 selection. It is archived under `ml-models/legacy_reference/` (it was previously a script in `ml-models/scripts/`, which has been removed in favour of the notebooks). Its results and limitations are saved under `ml-models/research_runs/maize_2026_11_20/`. The selected research model was slightly worse on 2020 MAE than the prior-county-yield baseline and uses full-year weather; it has **not** been deployed as a live crop-risk model. No genuine forage outcome model or live agricultural risk map has been validated.
