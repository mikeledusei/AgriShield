# Build from repository root: docker build -f apps/backend/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY apps/backend/requirements.txt /app/apps/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/apps/backend/requirements.txt
COPY apps/backend /app/apps/backend
COPY data_pipeline/data/processed/train_matrix.csv data_pipeline/data/processed/test_matrix.csv /app/data_pipeline/data/processed/
COPY data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv /app/data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv
WORKDIR /app/apps/backend
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
