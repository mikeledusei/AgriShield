# Deployment runbook

AgriShield ships a FastAPI backend and a Streamlit dashboard. They are separate
processes with separate images and separate failure modes.

## 1. Preconditions

| Requirement | Why | Where |
| --- | --- | --- |
| Python 3.11+ (CI uses 3.12) | `pyproject.toml` requires it | — |
| PostgreSQL (or Neon) URL | The container filesystem is ephemeral; SQLite would lose reports | `DATABASE_URL` |
| Supabase project | Identity for `PUBLIC_MODE=False` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| Outbound HTTPS to `api.open-meteo.com` | Live conditions page | network policy |
| NVIDIA NIM key (optional) | Gria AI answers; without it Gria returns a labelled summary | `NVIDIA_API_KEY` |

## 2. Configuration is validated at startup

`core/config.py` refuses to construct settings when `APP_ENV=production` and any of
these are still prototype defaults:

- `PUBLIC_MODE=True` (anonymous access), or `PUBLIC_MODE=False` without Supabase
- `DATABASE_URL` empty
- `SECRET_KEY` / `API_KEY` still holding placeholder values
- `CORS_ORIGINS` empty or `*`

The process exits with a message naming the offending variable. This is deliberate:
a misconfigured production deploy is a hard failure, not a degraded service.

## 3. Release sequence

```bash
# 1. Apply schema (never inside the container start command: a rolling deploy
#    must not race several instances against the same migrations).
cd apps/backend
alembic upgrade head
python seed_counties.py          # idempotent; safe on every deploy

# 2. Start the API (migrations are already applied)
uvicorn main:app --host 0.0.0.0 --port 8000
```

On Render this is `preDeployCommand` in `render.yaml`. Rollback is
`alembic downgrade -1`; every revision has a working `downgrade()`.

## 4. Health checks

| Endpoint | Meaning | Use for |
| --- | --- | --- |
| `GET /api/v1/health` | The process is serving. Touches nothing. | Load-balancer liveness |
| `GET /api/v1/health/ready` | Model loaded, artifact hash matches, a probe row scored, database reachable, required tables present. Returns **503** on failure with a `problems` list. | Deploy gate, `healthCheckPath` |

A green liveness probe and a red readiness probe means "the process is up and cannot
do its job" — check `problems` first.

## 5. Dashboard

```bash
docker build -f apps/frontend/Dockerfile -t agrishield-dashboard .
docker run -p 8501:8501 \
  -e AGRISHIELD_API_URL=https://api.example.com/api/v1 \
  -e AGRISHIELD_ALLOWED_HOSTS=dashboard.example.com \
  -e AGRISHIELD_ALLOWED_ORIGINS=https://dashboard.example.com \
  agrishield-dashboard
```

- `AGRISHIELD_API_URL` must be reachable **from the dashboard container**.
- XSRF protection and CORS stay enabled. Host/origin allowlists come from the
  environment; do not disable `enableCORS`.
- Set `AGRISHIELD_ENV=production` so an unset `AGRISHIELD_API_URL` fails at startup
  instead of silently pointing at localhost.

## 6. Retention job

Report snapshots expire after 7 days and saved history after 90 days. Expired rows
are also purged opportunistically on the next save, but that is not a guarantee.
Schedule:

```bash
cd apps/backend && python scripts/cleanup_reports.py
```

Run it daily from a scheduler with `DATABASE_URL` set. It is idempotent.

## 7. Backups

Neon: enable point-in-time restore and take a daily logical dump.

```bash
pg_dump "$DATABASE_URL" --no-owner --format=custom -f agrishield-$(date +%F).dump
```

Data at risk is limited to `assessment_report_snapshots` and `assessment_history`
(both capability-protected and time-limited). Counties are reseeded on deploy.

## 8. Model artifact changes

The API verifies `apps/backend/ml_artifacts/lightgbm_agrishield_v1.joblib` against the
`model_sha256` recorded in `training_feature_ranges.json` and **refuses to load a
mismatch** (`joblib` deserialisation executes code, so the digest is checked first).
To promote a new model:

1. Replace the artifact and `feature_columns.json` / `training_feature_ranges.json` together.
2. Update `schemas/manual_prediction.py` `MODEL_INPUTS` if the feature list changed.
3. Run `pytest tests -q`; the contract tests compare the schema with the artifact.
4. Confirm `/api/v1/health/ready` reports the new digest after deploy.

`REQUIRE_MODEL_HASH=False` exists only for research tooling; never set it in production.

## 9. Known limitations

- No rate limiting is applied in-process. Put quotas in front of `/gria/*`,
  `/documents/extract` and `/live/weather` at the edge.
- The live weather cache is per-process; multiple workers multiply upstream calls.
- `PUBLIC_MODE=True` is a prototype mode. It is not a security boundary.
