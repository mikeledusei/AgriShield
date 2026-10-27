# AgriShield Project Documentation

## Overview

AgriShield is a Kenya-focused agricultural risk intelligence platform designed to help stakeholders monitor, understand, and act on crop and forage risk conditions across the country. The system combines a Streamlit dashboard, a FastAPI backend, and predictive analytics to surface county-level risk insights in a way that is accessible to farmers, extension officers, and agricultural decision-makers.

The platform is built around a simple principle: turn technical agricultural risk results into practical farm guidance and clear operational decisions.

## Current Status

The project is in a working, validated state:

- Frontend app is running as a Streamlit dashboard.
- Backend API is running and reporting healthy status.
- Core regression checks pass.
- The dashboard includes county selection, dashboards, comparison, regional views, scenario analysis, PDF report generation, and Gria AI workflow.
- Authentication has been removed from the application flow as requested.
- Gria AI is designed to explain results in farmer-friendly language and accept uploaded documents for contextual analysis.

## System Goals

1. Predict agricultural risk at the county level.
2. Present data in a clear, premium dashboard experience.
3. Remove unnecessary auth-related friction from the product.
4. Give agricultural users simple, actionable explanations rather than raw model output.
5. Support document-aware AI reasoning and report generation.
6. Ensure the dashboard remains responsive and readable across screen sizes.

## Solution Architecture

AgriShield follows a lightweight three-layer structure:

```text
┌──────────────────────────────┐
│ Streamlit Frontend           │
│ - dashboard views            │
│ - county selection           │
│ - scenario controls          │
│ - Gria chat interface        │
│ - reports and download       │
└──────────────┬───────────────┘
               │ HTTP / JSON
               ▼
┌──────────────────────────────┐
│ FastAPI Backend              │
│ - prediction endpoints       │
│ - comparison and region APIs │
│ - report endpoints           │
│ - Gria chat endpoint         │
│ - document upload pipeline   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Data & Intelligence Layer    │
│ - ML model artifacts         │
│ - county metadata            │
│ - document processing       │
│ - AI summaries / reports    │
└──────────────────────────────┘
```

## Key Code Areas

- Frontend dashboard: [apps/frontend/streamlit_app.py](../apps/frontend/streamlit_app.py)
- Backend API entry: [apps/backend/main.py](../apps/backend/main.py)
- Prediction routes: [apps/backend/routers/predictions.py](../apps/backend/routers/predictions.py)
- Gria chat route: [apps/backend/routers/gria.py](../apps/backend/routers/gria.py)
- Upload route: [apps/backend/routers/uploads.py](../apps/backend/routers/uploads.py)
- Reports route: [apps/backend/routers/reports.py](../apps/backend/routers/reports.py)
- Shared frontend API wrapper: [apps/frontend/shared/api_client.py](../apps/frontend/shared/api_client.py)
- County metadata: [apps/frontend/shared/kenya_counties.py](../apps/frontend/shared/kenya_counties.py)
- Gria agent logic: [apps/backend/agents/gria_agent.py](../apps/backend/agents/gria_agent.py)
- File processor: [apps/backend/agents/file_processor.py](../apps/backend/agents/file_processor.py)

## Technology Stack

### Frontend
- Streamlit
- Pandas
- Altair
- pydeck (optional fallback)

### Backend
- FastAPI
- Pydantic
- SQLAlchemy
- Uvicorn

### AI / Prediction
- XGBoost model artifacts
- joblib for model loading
- Gria AI response layer
- Document processing utilities

### Data / Geography
- County geolocation and metadata
- Risk and trend datasets
- Kenyan county coverage for all 47 counties

## Features and Modules

### 1. Overview Dashboard
The overview page presents the selected county’s current risk status, including:

- risk score
- risk level
- focus area
- primary driver
- actionable recommendation
- recent trend chart
- national map and risk distribution

### 2. County Comparison
Users can compare multiple counties side by side, view risk ranking, and identify which areas are under the most stress.

### 3. Regional Overview
Regional summaries aggregate county-level conditions and provide a high-level risk interpretation by region such as Rift Valley, Coast, Eastern, Central, and others.

### 4. Scenario Planning
The scenario tab lets users simulate how rainfall change, temperature change, and NDVI stress affect a selected county’s risk level.

### 5. Reports
Users can generate report entries for different report types and download a PDF version when available. Reports are organized in a recent history list.

### 6. Gria AI Chat
Gria AI provides farmer-friendly explanations and responses in plain language. It is designed to:

- answer questions about risk conditions
- summarize model outcomes
- explain the impact of specific county conditions
- work with uploaded file context
- generate human-readable recommendations

### 7. File Upload and Document Analysis
Uploaded files may be processed and summarized to enrich the AI response. Supported file types include:

- CSV
- XLSX/XLS
- PDF
- DOCX
- JPG/JPEG
- PNG

This allows the system to read uploaded documents and include their findings in the Gria conversation.

## Data Flow

### Prediction flow
1. User selects a county or region from the dashboard.
2. The frontend sends a request to the FastAPI backend.
3. The backend uses a prediction endpoint and returns risk values.
4. The dashboard renders the score, chart, and narrative.

### Gria flow
1. User asks a question in the chat panel.
2. The frontend sends the prompt and optional county context to the backend.
3. The backend routes the request to the Gria AI agent.
4. The agent returns a farmer-friendly explanation.
5. If a document is attached, its context is included in the conversation.

### Report flow
1. User selects a county and report type.
2. Frontend calls the report creation API.
3. The backend saves and returns report metadata.
4. The frontend offers PDF download when available.

## Setup and Run Instructions

### Prerequisites

- Python 3.10+
- pip
- access to the project workspace
- optional backend runtime configuration for AI / storage integrations

### Install dependencies

```bash
pip install -r apps/backend/requirements.txt
pip install -r apps/frontend/requirements.txt
```

### Start the backend

```bash
cd apps/backend
uvicorn main:app --reload
```

### Start the frontend

```bash
cd apps/frontend
streamlit run streamlit_app.py
```

### Local service URLs

- Streamlit: http://127.0.0.1:8501
- FastAPI: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

## Validation and Quality Checks

The project was verified with the following checks:

```bash
cd /home/mikel/AgriShield
pytest tests/test_backend.py -q
python -m py_compile apps/frontend/streamlit_app.py apps/backend/main.py
```

Validation result:

- 7 backend tests passed
- Python compilation completed without syntax errors
- local dashboard and API responded successfully

## Important Implementation Notes

### County coverage
The county selector uses the full Kenya county list and is designed to avoid missing counties. This avoids the common issue where only a subset of counties is exposed in the dashboard.

### No authentication
Authentication was intentionally removed from both frontend and backend flows. The system operates without login/signup requirements.

### Dashboard cleanliness
The UI avoids exposing internal request noise or debug-style status output in the sidebar. The original issue of noisy background status messages was removed.

### Light-mode visibility
Charts and map visuals were adjusted to a lighter theme for readability, ensuring contrast on the dashboard remains strong in normal daylight conditions.

### WhatsApp-style Gria experience
The Gria interaction panel was redesigned to behave like a modern chat shell with a clear message flow, upload prompt, and input area.

## Known Operational Behavior

- Some AI integrations are optional and may remain unconfigured in the local environment.
- The backend health endpoint reports optional services such as Supabase and Redis as unavailable when not configured.
- The Gria flow still works in a graceful fallback mode even when an external AI service is not connected.

## Production / Deployment Considerations

For a production deployment, the project should consider:

- secure environment variables for backend configuration
- persistent storage for reports and uploaded files
- real model integration and expected API credentials
- monitoring for failed prediction or AI analysis requests
- role-based access if the system expands beyond the current no-auth dashboard model

## Summary

AgriShield is a practical agricultural intelligence platform that combines prediction, mapping, scenario analysis, reporting, and AI-augmented explanation. The current implementation focuses on a reliable Kenya county dashboard, clean user experience, and accessible interpretations for farmers and agricultural decision-makers.

This project is now in a stable, functionally validated state, with the codebase aligned to the major requirements around feature completeness, dashboard usability, no-auth operation, and AI-assisted interpretation.
