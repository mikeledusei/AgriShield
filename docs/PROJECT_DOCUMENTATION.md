# AgriShield project documentation

AgriShield is a research prototype for analyzing a synthesized county-level
vegetation-stress proxy. It is not a validated live crop or livestock early-warning
service.

## Where to look

| Document | Answers |
| --- | --- |
| [README](../README.md) | What the project does, how to run it locally, what it does and does not claim. |
| [CHANGELOG](CHANGELOG.md) | Every change made in this release, with file paths and the reason for each. |
| [DEPLOYMENT](DEPLOYMENT.md) | Release sequence, migrations as a release step, secrets, health checks, retention cron, backups, model promotion. |
| [MAP_DESIGN](MAP_DESIGN.md) | How the county map is built, the colour scale, label placement, and why there is no tile basemap. |
| [DATA_MODEL_CARD](DATA_MODEL_CARD.md) | What the model is trained on, what a score means, the accepted input distribution, and the requirements for a genuine outcome forecast. |
| [frontend guide](../apps/frontend/README.md) | Dashboard configuration, input definitions, deployment of the Streamlit image. |
| [research release policy](../ml-models/research_runs/README.md) | Why research model binaries are release assets rather than tracked files. |

Historical thesis documents and older notebooks can reflect prior versions or describe
proposed rather than completed functionality. Where they disagree with the documents
above, the documents above are current.

## Architecture in one paragraph

The Streamlit dashboard is an API-only client: it never loads a model and never
fabricates a result. The FastAPI backend owns inference. It scores complete
user-supplied feature vectors, can derive features from raw measurements, extracts
reviewed document text, serves historical county views, and generates
capability-protected snapshot reports and PDFs. A missing, unreadable or hash-mismatched
model artifact makes scoring unavailable (503) rather than substituted. Unsafe legacy
endpoints return 410 and are listed one path at a time rather than behind a catch-all.
Optional external services — Supabase identity, NVIDIA NIM for Gria, Open-Meteo for live
weather — degrade to a labelled unavailable state rather than a fabricated one, and are
not exercised by the test suite, which runs fully offline.
