# AgriShield dashboard

The Streamlit application is a presentation layer. It makes HTTP requests to the FastAPI backend for health, the model-input schema, county names, prediction, CSV scoring, reports, historical maps and Gria. It does not load or run model artifacts or supply fallback values. If the API is unavailable, the dashboard displays an error and does not create a substitute result.

## Run locally

From the repository root, with Python 3.11+ (the model artifact requires the pinned scikit-learn version):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/backend/requirements.txt -r apps/frontend/requirements.txt
cd apps/backend
python init_db.py
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000
```

In a second terminal:

```bash
source .venv/bin/activate
export AGRISHIELD_API_URL=http://127.0.0.1:8000/api/v1
cd apps/frontend
streamlit run streamlit_app.py --server.address 0.0.0.0
```

`AGRISHIELD_API_URL` must be reachable **from the Streamlit server**, not necessarily from the end user's browser. It is validated at startup: a malformed URL raises immediately, and with `AGRISHIELD_ENV=production` an unset URL is a startup error rather than a silent fallback to localhost. `/api/v1` can be omitted. When backend authentication is enabled, set `AGRISHIELD_API_TOKEN` to an authorized bearer token. The default local SQLite database is initialized with `init_db.py`; configure a durable `DATABASE_URL` for deployment. NVIDIA credentials are optional; when absent, Gria displays a clearly labelled historical summary instead of an AI response. Do not commit credentials.

For the API Docker image, build from the repository root: `docker build -f apps/backend/Dockerfile .`. The image includes the historical feature matrices needed by the explorer. If deployed separately, the frontend must be configured to reach the backend. The Render blueprint deploys the backend, not the Streamlit frontend.

## Assessment inputs

The backend exposes `/api/v1/predictions/input-schema` as the source of truth for the UI. A complete observation has a county, `YYYY-MM` period, and 14 numeric fields:

- Monthly mean temperature and soil moisture, monthly rainfall, rainfall anomaly, three-month rainfall sum and forage dryness index.
- NDVI one and three months previously, previous-three-month NDVI mean and sample standard deviation, and NDVI anomaly.
- Farming household ratio, livestock activity share and irrigation ratio.

The backend computes the two cyclical month features (sine and cosine), making the 16 columns in the champion model artifact. No missing model inputs are silently replaced. Fields have bounds; the three-month total must include at least the selected month's rainfall. The input ranges are plausibility checks, not proof that data is compatible with training or within its distribution. Derived indicators entered directly must be calculated consistently with training.

The **Calculate from measurements** form accepts three months of rainfall and NDVI, monthly temperature and soil moisture, the historical rainfall and NDVI baselines, and household counts. The backend reproduces the feature engineering in `ml-models/notebooks/02_feature_engineering.ipynb`, including the sample standard deviation, rounding and `+1` household denominators. Baselines should use the county's 2015–2023 training period, and temperature, soil moisture, NDVI and household data should use definitions compatible with the training data. No data sources are fetched automatically. Inputs must be supplied by the user.

A CSV upload uses the same 14-feature contract; download the empty template in the app. It must contain exactly one complete row. Values outside the model's training ranges are rejected with the offending field and a unit hint; add an `accept_extrapolation` column (or use the form checkbox) to score them anyway, and the result will be labelled as an extrapolation. The backend validates and scores it. PDFs are generated from an immutable database snapshot that preserves the scored inputs, output and model hash. Report access requires a random token; records expire after seven days and are cleaned up when later reports are created. Use a scheduled cleanup for strict retention.

## Interpretation and limitations

The existing model was trained on a synthesized label for unusually low county NDVI. Its score is an uncalibrated model output for this vegetation-stress proxy, not a verified crop-yield shock, forage deficit, current alert, or operational forecast. The historical explorer is derived from the checked-in research dataset and may include imputed or proxy values; it is not live data. Historical displays only show periods actually available on the backend. Separate crop and livestock outcome models, independent validation, live feeds and reviewed operational advice remain future work. Gria requires a configured NVIDIA service to answer questions; otherwise only a labelled deterministic historical summary is available.

Unsafe legacy prediction, forecast, upload, storage and report-history endpoints return HTTP 410. Use the strict endpoints documented in the API. TXT, text-based PDF and DOCX can be extracted as user-reviewed Gria context; they are never automatically scored. No OCR or image-to-NDVI conversion is provided.

## Maps, explanations, Gria and reports

The historical explorer scores every available county row for the selected month, displays a county map, coverage count, score-band distribution, comparisons, and a 12-month county trend with rainfall, lagged NDVI and soil moisture. Map markers are placed at polygon centroids computed from `assets/kenya_counties.geojson` (the file carries no coordinate properties), and the GeoJSON is parsed once per server process rather than on every rerun. The display flags incomplete coverage and shows the latest packaged month; no live feed is implied. A county's SHAP chart uses the exact stored feature row and the loaded LightGBM artifact. Contributions are on the model's log-odds scale and are not causes. Manual assessments have the same chart and can be sent for analysis.

`POST /api/v1/gria/analyze` calculates the evidence server-side. Historical analysis includes the selected county's scores and SHAP contributions, the 12-month series and all available county scores for the selected month; manual analysis verifies the model hash and score. When AI is configured, evidence is sent to that provider. AI text is not independently verified. If the provider is unavailable, a labelled deterministic summary and conservative verification steps are shown instead. The action buttons make this sharing explicit; questions and selected document text can also be sent to the provider. No external live conditions are queried.

Reports can include a fresh Gria analysis (or a labelled fallback) with a vector AgriShield leaf emblem and wordmark, model details, SHAP, and historical context and trend when available. The generated analysis is stored in the protected snapshot, so PDF downloads do not rerun the model or AI. An analysis generated while preparing the report may differ from one requested earlier. No official AgriShield logo asset was provided, so the report uses the project's new vector emblem; replace it with an approved brand asset when available.

## Current weather and saved history

The Live conditions page shows Open-Meteo modelled weather at one representative point per county, not county averages, crop/forage outcomes or live risk. The backend caches successful results for ten minutes and refuses stale values; provider failures are visible. Deployment requires outbound access to api.open-meteo.com and adherence to Open-Meteo's attribution and usage terms.

Create a private key in History, save it securely, and use the save buttons on assessments or county history. A key is a bearer capability: anyone who has it can access/delete its records, and it cannot be recovered. Saved records expire in 90 days. Existing report snapshots are separate and expire in seven days. Schedule `python apps/backend/scripts/cleanup_reports.py` for regular physical deletion of expired records.
