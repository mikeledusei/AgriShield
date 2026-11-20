# CHANGELOG

Every change made in this release, grouped by area. Each entry names the files touched
and why the change matters, so a reviewer can check one without reading everything.

Two entries change behaviour for existing callers; they are listed under
[Breaking changes](#breaking-changes) first.

---

## Breaking changes

### 1. Out-of-distribution input is rejected, not silently scored

**Files:** `apps/backend/schemas/manual_prediction.py`, `apps/backend/routers/manual_predictions.py`,
`apps/frontend/streamlit_app.py`, `apps/frontend/README.md`

`POST /predictions/from-inputs`, `/from-measurements` and `/from-csv` now return **422**
when a feature value falls outside the range recorded in
`ml_artifacts/training_feature_ranges.json`, naming the offending field and its unit.
Resubmit with `accept_extrapolation=true` (JSON) or an `accept_extrapolation` column
(CSV) to score it anyway; the response then carries `extrapolated: true`.

**Why.** The champion model is a tree ensemble: outside the training range it returns
the boundary leaf's value with no indication that the input is unlike anything it saw.
The motivating case was forage dryness entered as `40` instead of `0.4` — a physically
impossible value that previously produced a confident-looking score.

**Not a blunt cutoff.** The bounds are derived from the training matrix, not hand-written.
An earlier hand-drafted set would have rejected five legitimate 2024 flood-season
counties; the derived set does not. Stored historical rows are scored directly and are
unaffected.

### 2. One risk vocabulary

**Files:** `apps/backend/core/scales.py`, `apps/frontend/shared/scales.py`,
`services/prediction_service.py`

`Lower / Moderate / Elevated / High` everywhere. The unused
`SAFE / MODERATE / HIGH / CRITICAL` ladder is gone from API responses. `core/scales.py` is
the single definition; the dashboard mirrors it and `tests/test_scales.py` asserts the
two stay identical.

**Why.** Four different band vocabularies existed across the codebase, so the same score
could be labelled differently depending on which layer produced the label.

---

## Bugs fixed

| File | Bug | Effect if unfixed |
| --- | --- | --- |
| `apps/frontend/streamlit_app.py` | `hoverinfo='text+marker'` is not a valid plotly value | The maize-yields page raised on render |
| `apps/frontend/streamlit_app.py`, `shared/map_data.py` | Read `latitude`/`longitude` from GeoJSON properties that do not exist | Every county plotted at (0, 0) in the Gulf of Guinea |
| `apps/backend/app/main.py` | Module defined no `app` | The documented entry point could not start |
| `apps/backend/core/database.py` | Module was a docstring only, yet routers imported `get_db` from it | `ImportError` at collection; the whole suite failed |
| `services/prediction_service.py` | `get_risk_level` / `RECOMMENDATIONS` defined twice | The trailing copy silently won; edits to the first did nothing |
| `routers/manual_predictions.py` | `/predictions/{path:path}` catch-all returned 410 | It shadowed every live route under `/predictions` |
| `routers/health.py` | `/health` reported healthy with a missing model or unapplied migrations | A broken deployment passed its health check |
| `apps/frontend/shared/county_map.py` | Label anchor placed on the edge facing *away* from the dot | Every label sat one line height onto its neighbour |

### Health probes split

**Files:** `routers/health.py`, `render.yaml`, `apps/backend/Dockerfile`, `docs/DEPLOYMENT.md`

`GET /health` is liveness and touches nothing. `GET /health/ready` performs a probe
inference, compares the artifact SHA-256, checks the database and required tables, and
returns **503** with a `problems` list. `render.yaml` and the image `HEALTHCHECK` use the
readiness path.

**Why.** Liveness and readiness were the same endpoint, so the only signal a platform
had was "the process is up" — which is true of a process that cannot score.

---

## Reliability

- **Schema owned by Alembic.** Four revisions
  (`20261120_baseline → _snapshots → _history → _retention_indexes`) adopt every table
  that `create_all` used to create. `init_db.py` is now an alias. The test database is
  built from migrations only, so a missing revision fails CI. `alembic.ini` sets
  `path_separator = os`, clearing a deprecation warning.
- **Artifact integrity.** `joblib.load` executes arbitrary code, so the file is hashed
  and compared with the recorded digest *before* deserialisation
  (`services/prediction_service.py`). A mismatch makes scoring unavailable; the score is
  never substituted.
- **Bounded database waits.** `core/config.py` sets pool size, connection timeout and
  recycle for PostgreSQL, so a Neon cold start cannot pin a request thread indefinitely.
- **Live weather.** Fetches outside the cache lock and backs off 30 s after a failure, so
  a slow provider cannot block concurrent requests.
- **Analysis caching.** Historical analysis (three full model passes per report) is
  memoised on `(county, month, model digest)`.
- **Error classes separated.** Report persistence distinguishes a storage failure (503)
  from a serialisation bug (500) and logs both differently.
- **Bounded DOCX extraction.** Extraction stops at the text limit instead of building the
  whole document first.
- **Per-request logging.** Request ids are bound per request, returned in `X-Request-ID`,
  and included in every access-log line (`middleware/request_context.py`).
  `LOG_LEVEL` is honoured.

## Security

- **Production fails closed** (`core/config.py`): `APP_ENV=production` refuses to start on
  placeholder secrets, anonymous access, a missing `DATABASE_URL`, or wildcard/empty CORS.
- **CORS** enumerates methods and headers; wildcard-plus-credentials is refused.
- **Authentication** distinguishes a bad token (401 with `WWW-Authenticate: Bearer`) from
  an unconfigured identity provider (503).
- **Streamlit** no longer disables CORS. `enableCORS` and XSRF protection stay on; host and
  origin allowlists are supplied per environment and expanded at container start
  (`apps/frontend/.streamlit/config.toml`, `apps/frontend/Dockerfile`).

## County map

- **One builder** (`apps/frontend/shared/county_map.py`) serves all three map pages, so
  Live conditions, Reported maize yields and the Historical explorer behave alike.
- **Every county labelled**, with a leader line where a name must clear its marker; long
  names wrap at the hyphen; a caption reports how many names fit.
- **Dot colour is the score band**, one trace per band so the legend matches the palette
  exactly. Weather and yield values use a separate continuous scale so they cannot be
  read as a risk band.
- **No third-party tile basemap.** Tiles load from the viewer's browser, so the map would
  be blank offline and would add a licence obligation. Rationale and the placement
  algorithm are in `docs/MAP_DESIGN.md`.
- **Payload 6.8 MB → 323 KB.** `apps/frontend/scripts/simplify_geojson.py` applies
  Douglas-Peucker (0.01°, ~1 km) to produce
  `assets/kenya_counties_simplified.geojson`; the full file remains for GIS use.
- **Label placement bug fixed:** all marker positions are now registered before placement
  begins, so a label cannot land on a dot of a county processed later.

## Wording

- **Gria no longer over-claims** (`services/prediction_service.py`). The summary said the
  model "predicts drought and forage risk". It now says it scores how unusual the month's
  vegetation is against that county's training baseline, and does not forecast a future
  month, crop loss or forage deficit.

  **Why.** The model's target is `ndvi_mean < ndvi_25th_pct` for the *same* month — a
  one-month classification with no future label anywhere in the training code. Calling it
  a forecast misstates it to the person making the decision. A regression test pins the
  wording.

## Removed

- **~2,300 lines of unreachable backend code**, and the `test_imports` list that was the
  only thing keeping it importable: `routers/{predictions,reports,uploads,storage}.py`,
  `agents/file_processor.py`,
  `services/{pdf_generator,export_service,feature_service,cache_service}.py`,
  `core/redis_client.py`, `middleware/auth.py`, `schemas/predictions.py`, `app/main.py`.
- **The fictional rule-based fallback scorer.** It invented a score when no model was
  loaded. Scoring now fails loudly instead.
- **~1,100 lines of unused frontend helpers**: `shared/{ui_helpers,types,constants,kenya_counties}.py`.
- **Unused dependencies** — see the table below.

## Dependencies, CI and containers

- **One `requirements.txt` per component** — see "Dependency and environment layout"
  below. (Historically the backend had three: runtime, research and dev. The API image
  still installs only the runtime subset, now filtered from the single file by the
  Dockerfile.)
- **Dependencies nothing imported removed**:

  | File | Removed | Evidence |
  | --- | --- | --- |
  | `data_pipeline/requirements.txt` | `geopandas`, `shapely`, `fiona` | Nothing imports them; the GeoJSON is read with the standard `json` module |
  | `data_pipeline/requirements.txt` | `tqdm`, `python-dotenv` | No import anywhere in `data_pipeline/scripts` |
  | `data_pipeline/requirements.txt` | `jupyter`, `ipykernel` | Notebook-only; the scripts do not need them |
  | `ml-models/requirements.txt` | `jupyter`, `ipykernel`, `python-dotenv` | Same |

  Verified afterwards: every third-party import in `apps/`, `data_pipeline/scripts/` and
  the `ml-models` research scripts is declared in a requirements file, and
  `clean_data.py` and `prepare_maize_outcomes.py` still start. (The `ml-models/scripts/`
  copies of `train.py` were later removed in favour of the notebooks; see the entry below.)
- **No `constraints.txt`** — each `requirements.txt` resolves its own dependencies directly.
  `scikit-learn==1.9.0` remains pinned in the backend file because the artifact was fitted with it.
- **CI** (`.github/workflows/ci.yml`): Python 3.12, install from the four requirements files,
  `ruff check`, `compileall`, apply → roll back → apply migrations on a throwaway SQLite
  database, run the suite, and an informational `pip-audit`.
- **Clean-environment proof:** a fresh venv installed from the declared files alone passes
  **79 tests, ruff, compileall and the migration round-trip**. This is what CI does.
- **`apps/backend/Dockerfile`**: Python 3.12-slim, `libgomp1` for LightGBM, non-root uid
  10001, readiness-based `HEALTHCHECK`, migrations documented as a release step.
  Rehearsed outside Docker against a replica of the image layout: migrations → seed (47
  counties) → `/health/ready` returns **200**.
- **`apps/frontend/Dockerfile`**: non-root uid 10002, health check on `/_stcore/health`,
  start-time expansion of the host/origin allowlists. Rehearsed the same way: health `ok`,
  page returns 200.
- **`render.yaml`**: `preDeployCommand` runs migrations and seeding, readiness health
  check, `PUBLIC_MODE=False`, secrets generated or marked `sync: false`.
- **`.dockerignore`** cuts the build context. **`.devcontainer`** starts both services and
  passes `allowedHosts` for localhost.

## Repository

- **`.gitignore` no longer un-ignores every CSV.** `data_pipeline/data/` is ignored and
  the tracked data files are an explicit allowlist, verified with `git check-ignore`.
- **Untracked binaries** (files remain on disk): the 12.5 MB slide deck, research
  `.joblib` files, the maize `.xlsx` mirror, 16 raw and processed CSVs, and the duplicate
  `data_pipeline/data/kenya_counties.geojson` (byte-identical to the frontend copy, md5
  `61a522a6…`, unread by any script). Tracked size fell from 23 MB to ~13 MB. The policy
  for research artifacts is in `ml-models/research_runs/README.md`.
- **`pyproject.toml`** adds ruff (F, E, W, I, B, UP, S) and pytest configuration with
  targeted per-file ignores, rather than blanket disables.

## Tests added

`tests/conftest.py` provisions an isolated SQLite database from the migrations, so a test
run never touches a development database. New coverage:

| Test | Guards |
| --- | --- |
| `test_scales.py` | Frontend and backend band definitions stay identical |
| `test_auth.py` | Protected mode returns 401/503 correctly (previously untested) |
| `test_backend.py::test_readiness_*` | Readiness fails on a missing model, bad hash or unapplied migrations |
| `test_backend.py::test_csv_upload_accepts_the_extrapolation_column` | The opt-in works through the CSV path, not only JSON |
| `test_backend.py::test_summary_does_not_claim_a_forecast` | The Gria wording cannot regress |
| `test_backend.py::test_document_extraction_is_bounded_for_docx` | Extraction truncates instead of materialising a huge document |
| `test_backend.py::test_outcomes_survive_a_malformed_row` | One bad reported row does not break the endpoint |
| `test_frontend.py::test_county_map_places_labels_without_overlap` | No two labels overlap; none leaves the frame |

Suite total: **79 passing**, no deprecation warnings (`-W error::DeprecationWarning`
clean).

## Documentation

- **`README.md`** — corrected claims to match the code, real setup steps, the 422
  behaviour, the readiness endpoints, and a pointer to the runbook.
- **`docs/DEPLOYMENT.md`** (new) — preconditions, startup validation, release sequence,
  rollback, health checks, dashboard deployment, retention cron, backups, model promotion,
  known limitations.
- **`docs/MAP_DESIGN.md`** (new) — map decisions, colour scale, label algorithm, assets.
- **`docs/CHANGELOG.md`** (this file) — supersedes `CHANGES_MADE.md` and
  `docs/RELEASE_NOTES.md`, which described a session rather than the product.
- **`docs/PROJECT_DOCUMENTATION.md`** — now an index of the documents above rather than a
  pointer to documents that had moved on.
- **`docs/DATA_MODEL_CARD.md`** — added the accepted-input-distribution section.
- **`apps/backend/.env.example`, `apps/frontend/.env.example`** — rewritten. The old files
  listed variables the code never read and omitted several it requires.

## Dependency and environment layout

One `requirements.txt` and one virtual environment per component. There is no environment
at the repository root and no second requirements file anywhere.

| Component | File | Environment |
| --- | --- | --- |
| `apps/backend` | `requirements.txt` | `apps/backend/venv` |
| `apps/frontend` | `requirements.txt` | `apps/frontend/venv` |
| `data_pipeline` | `requirements.txt` | `data_pipeline/venv` |
| `ml-models` | `requirements.txt` | `ml-models/venv` |

- **Merged and deleted** `apps/backend/requirements-dev.txt` and
  `apps/backend/requirements-research.txt`. Their contents are now sections of
  `apps/backend/requirements.txt`, so a single venv there can serve the API, run the
  test suite and retrain models. `data_pipeline/requirements.txt` gained `joblib`,
  `scikit-learn`, `jupyter` and `ipykernel`, which `ml-models` needs too; `ml-models`
  gained `jupyter` and `ipykernel`. Every file is self-sufficient: the notebooks address
  `data_pipeline/data/processed/` by path and never import the `data_pipeline` package,
  so per-component venvs need no cross-installs. The one exception is `data_pipeline/scripts/experiment.py`,
  which is imported from the repository root; it resolves because nothing else is needed
  on `sys.path` beyond the repo itself.
- **The API image stays lean** without a second file: `apps/backend/Dockerfile` filters
  the research and test blocks out of `requirements.txt` with `awk` before installing, so
  `jupyter`, `xgboost`, `seaborn` and `pytest` never enter the image.
- **CI installs all four** into one interpreter, because the root `tests/` import the
  backend, the dashboard, `data_pipeline` and the research libraries. Locally they are
  separate venvs.
- **`.env.example` files completed.** `apps/backend/.env.example` now documents all 27
  settings including `API_KEY`, the real `SECRET_KEY`/`API_KEY` defaults, and
  `MODEL_PATH`, and separates the "required in production" group that
  `validate_production_safety` actually enforces. `apps/frontend/.env.example` documents
  `BACKEND_URL` (a supported alias) and states that the two
  `AGRISHIELD_ALLOWED_*` variables are read by the Dockerfile's `streamlit` flags, not by
  the application code.

## Data pipeline is notebook-only, with data acquisition and documented EDA

- **`data_pipeline/scripts/` removed** (10 modules). The pipeline is now four notebooks in
  `data_pipeline/notebooks/`. Logic that only existed in scripts was ported, not dropped:
  the panel builder and its validation from `clean_data.py`/`experiment.py` now live in
  `01_data_cleaning.ipynb` as explicit cells, and the archived originals remain readable in
  `data_pipeline/legacy_reference/`.
- **`00a_raw_data_acquisition.ipynb` is new.** It downloads every raw source into
  `data/raw/`, verifies it, and writes `MANIFEST.json` with sizes and SHA-256 hashes:
  NDVI and CHIRPS from HDX, monthly temperature / rainfall / soil wetness / runoff per
  county from the NASA POWER point API (no key required), FAOSTAT bulk crops, and the
  2019 census household table. The last two print manual instructions when they cannot be
  fetched automatically. County centroids are derived from the tracked GeoJSON rather than
  hard-coded, and reconciled against the crosswalk with an assertion — the GeoJSON spells
  three counties with hyphens (`Elgeyo-Marakwet`) while the crosswalk and every processed
  table use spaces, so a silent mismatch would have quietly produced a 44-county pipeline.
- **`02_eda.ipynb` rewritten** to produce seven charts, each with its own `.md` explanation
  and a combined `CHART_EXPLANATIONS.md` plus `figures.json`. Every chart is saved through a
  single helper that requires the explanation text, so a figure cannot be written without
  one. The explanations state the reading, the modelling consequence, and the limit.
- **`tests/test_pipeline.py` rewritten.** It previously imported the scripts. It now asserts
  against the notebook files and the committed outputs: the panel is 6,204 rows with 132
  months per county and no gaps, imputation is flagged (132 soil-moisture cells), the ML
  base table satisfies the champion's column contract, every EDA figure has an explanation
  of at least 200 characters that references its own file, and only the acquisition
  notebook makes network calls. **Coverage is genuinely lower than before** — the old suite
  unit-tested `load_panel()` and `build_experiment()` directly; a regression in that logic
  now surfaces as a failed notebook run rather than a red test.
- **Consequence to be explicit about:** the tests that verified `download_external.py`'s
  MD5 checking and `save_eda.py`'s no-overwrite behaviour were removed with those scripts.
  The acquisition notebook verifies hashes, but that verification is now asserted only by
  reading the notebook, not by executing it.

## Notebook-only research workflow

`ml-models/scripts/` has been **removed** (four files: `train.py`, `evaluate.py`,
`predict.py`, `maize_outcome_experiment.py`). The research workflow is now the notebook
sequence in `ml-models/notebooks/`.

- **`00_data_loading.ipynb` no longer needs files that do not exist.** It read
  `master_cleaned_2015_2025.csv`, plus `Crop_Production_WIDE/LONG_FINAL.csv` in its
  inventory cell. None of the three is tracked in Git or produced by any committed
  script, so the notebook could not run from a clean clone. It now joins
  `NDVI_FINAL.csv` + `Weather_FINAL.csv` + `Demographic_Crop_Activity_FINAL.csv`
  directly and asserts the row count and grain after joining. The rebuild reproduces
  `ml_base_2015_2025.csv` exactly: **6,204 rows × 15 columns**, 47 counties, 132 months
  each, 0 nulls — confirmed by executing all six notebooks in order in a fresh clone.
- **The maize yield experiment has no notebook equivalent.** The notebooks model the
  NDVI drought-risk target only. The script is archived at
  `ml-models/legacy_reference/maize_outcome_experiment.py.txt` so the results under
  `ml-models/research_runs/maize_2026_11_20/` stay reproducible.
- **Two tests removed** with the scripts they exercised:
  `test_end_to_end_experiment_does_not_promote_model` and
  `test_maize_experiment_holdout_and_baseline_are_separate`. The first asserted that a
  research run never promotes itself to the deployed champion; that guarantee now rests
  on notebook discipline instead, because `05_model_comparison.ipynb` **does** copy its
  models into `apps/backend/ml_artifacts/`.
- **Pointers updated** so nothing dangles: `ci.yml` `compileall` target, the
  `pyproject.toml` per-file ruff ignore, `README.md` (research section rewritten as a
  notebook table), `docs/DATA_MODEL_CARD.md`, both requirements headers, and
  `ml-models/research_runs/maize_2026_11_20/README.md`.

## Local development

- **`apps/frontend/.env` is now read** (`shared/api_client.py`). The backend reads its
  `.env` through pydantic-settings, but the dashboard is a plain script and only read
  real environment variables, so a `.env` beside `streamlit_app.py` was silently ignored
  and the app fell back to the localhost default while the file looked authoritative. A
  real environment variable still takes precedence, so containers and Streamlit are
  unaffected.
- **README quickstart rewritten** into two numbered terminals with the readiness check
  inline. `--reload` added for backend development, the optional `.env` copy documented,
  and the Windows activate path noted.

## Known limitations

Stated here so they are not mistaken for oversights:

- **No real forecast.** The champion model classifies the current month's vegetation
  against the county's training baseline. A genuine forecast needs a future-month label,
  rolling-origin validation, and measured skill against a seasonal baseline; see
  `docs/DATA_MODEL_CARD.md`.
- **No in-process rate limiting.** Quotas belong at the edge for `/gria/*`,
  `/documents/extract` and `/live/weather`.
- **Per-process caches.** Multiple workers multiply upstream provider calls.
- **`PUBLIC_MODE=True`** is a prototype setting, not a security boundary.
- **Docker images were rehearsed outside Docker** (no daemon in the build environment) by
  reproducing the image filesystem layout and running the same commands. `docker build`
  itself is unverified here.
- **External services are untested by the suite**: Supabase, NVIDIA NIM and Open-Meteo all
  degrade to a labelled unavailable state and are never faked.

## Dependency install simplified (2026-11-20)

**Files:** `scripts/install_venvs.sh` (updated),
`apps/backend/requirements.txt`, `apps/frontend/requirements.txt`,
`data_pipeline/requirements.txt`, `ml-models/requirements.txt`,
`constraints.txt` (removed), `.github/workflows/ci.yml`, `render.yaml`,
`README.md`

Removed `constraints.txt` entirely — it added a second source of truth for
dependency versions and caused install failures when a pin lacked a wheel for
the local Python version (`ruff>=0.6` resolved to nothing on Python 3.12
because `ruff` was unpinned, and `jupyter>=1.0.0` made pip backtrack through
dozens of jupyter-server/jupyterlab versions).

- **`constraints.txt` deleted** — each `requirements.txt` now resolves its own
  dependencies directly, which is simpler and avoids stale-pin failures.
- **`scripts/install_venvs.sh`** — updated to install without `-c
  constraints.txt`; still upgrades pip first and uses `--retries 10
  --timeout 300` to survive network hiccups on large wheel downloads.
- **All four `requirements.txt` headers** — manual install command now omits
  `-c constraints.txt`.
- **CI (`.github/workflows/ci.yml`)** — removed `-c constraints.txt` from the
  pip install and `constraints.txt` from `cache-dependency-path`.
- **Render (`render.yaml`)** — `buildCommand` no longer passes `-c constraints.txt`.
- **`README.md`** — removed the `constraints.txt` reference from the repository map.

**Why.** One `requirements.txt` per component is the standing rule; `constraints.txt`
was a second, easily-out-of-sync file. The install script's `--retries`,
`--timeout`, and `pip --upgrade` handle the real failure modes (timeouts and
stale indexes) without a separate constraints file.
