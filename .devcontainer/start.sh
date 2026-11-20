#!/usr/bin/env bash
# Start the API and the dashboard together so the devcontainer is usable on attach.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f apps/backend/.env ]; then
  cp apps/backend/.env.example apps/backend/.env
fi

export DATABASE_URL="${DATABASE_URL:-sqlite:///$PWD/apps/backend/agrishield.db}"

(cd apps/backend && python init_db.py && python seed_counties.py \
  && exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload) > /tmp/api.log 2>&1 &

export AGRISHIELD_API_URL="${AGRISHIELD_API_URL:-http://127.0.0.1:8000/api/v1}"
(cd apps/frontend && exec streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501 \
  --server.allowedHosts=localhost,127.0.0.1) \
  > /tmp/dashboard.log 2>&1 &

echo "API log: /tmp/api.log   Dashboard log: /tmp/dashboard.log"
