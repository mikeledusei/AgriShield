# Deployment runbook

AgriShield ships a FastAPI backend (Neon PostgreSQL + XGBoost champion) and a Streamlit dashboard. They are separate processes.

## 1. Preconditions

| Requirement | Why | Where |
| --- | --- | --- |
| Python 3.12.9 | pinned `scikit-learn==1.9.0` needs it | — |
| Neon PostgreSQL pooled URL | ephemeral SQLite would lose reports | `DATABASE_URL` |
| Outbound HTTPS to `api.open-meteo.com` | live weather | network policy |
| NVIDIA NIM key (optional) | Gria AI; else labelled summary | `NVIDIA_API_KEY` |

## 2. Configuration is validated at startup

`core/config.py` refuses to start in `APP_ENV=production` when:
- `DATABASE_URL` empty
- `SECRET_KEY` / `API_KEY` still placeholder
- `CORS_ORIGINS` empty or `*`

## 3. Release sequence

```bash
cd apps/backend
alembic upgrade head
python seed_counties.py          # idempotent; safe on every deploy
uvicorn main:app --host 0.0.0.0 --port $PORT
```

On Render this is `preDeployCommand` in `render.yaml`.

## 4. Health checks

| Endpoint | Meaning |
| --- | --- |
| `GET /api/v1/health` | liveness |
| `GET /api/v1/health/ready` | model loaded, hash OK, Neon reachable, tables present — 503 with `problems` on fail |

## 5. Dashboard

```bash
docker build -f apps/frontend/Dockerfile -t agrishield-dashboard .
docker run -p 8501:8501 \
  -e AGRISHIELD_API_URL=https://api.example.com/api/v1 \
  agrishield-dashboard
```

- `AGRISHIELD_API_URL` must be reachable from the dashboard container.
- Set `AGRISHIELD_ENV=production` to fail fast if unset.

## 6. Champion model

XGBoost `champion_model.joblib` (validation F1 0.8689 on 2022-2023, 47 counties, 6204 rows). Hash in `training_feature_ranges.json` is verified on load. `REQUIRE_MODEL_HASH=True` must stay True in production.

## 7. Retention

Reports 7 days, history 90 days. Run `python scripts/cleanup_reports.py` daily with `DATABASE_URL` set.

## 8. Backups

Neon: enable point-in-time restore + `pg_dump "$DATABASE_URL" --no-owner --format=custom -f dump-$(date +%F).dump`.
