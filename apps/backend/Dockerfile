# Build from the repository root:
#   docker build -f apps/backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libgomp1 is required by LightGBM.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY apps/backend/requirements.txt /app/apps/backend/requirements.txt
# requirements.txt covers runtime, research and test tooling so one venv serves local
# development. The image installs only the runtime deps: filter out the research and
# tooling blocks marked by "# ----- Data pipeline" and "# ----- Test and lint".
RUN awk '/^# ----- (Data pipeline|Test and lint)/{skip=1} /^# ----- /&&!/^# ----- (Data pipeline|Test and lint)/{skip=0} !skip' \
      /app/apps/backend/requirements.txt > /tmp/runtime.txt \
    && pip install -r /tmp/runtime.txt \
    && rm /tmp/runtime.txt

COPY apps/backend /app/apps/backend

# The historical feature matrices the explorer and health probe read.
COPY data_pipeline/data/processed/train_matrix.csv data_pipeline/data/processed/test_matrix.csv \
     /app/data_pipeline/data/processed/
COPY data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv \
     /app/data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv

# Run as a non-root user; the app writes nothing to disk except an optional dev SQLite file.
RUN useradd --create-home --uid 10001 agrishield && chown -R agrishield:agrishield /app
USER agrishield

WORKDIR /app/apps/backend
EXPOSE 8000

# Migrations are a release step, not a container start step: a rolling deploy must
# not race several containers to alter the same schema.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
