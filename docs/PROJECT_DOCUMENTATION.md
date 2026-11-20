# AgriShield project documentation

AgriShield is a research prototype for analyzing a synthesized county-level vegetation-stress proxy. It is not a validated live crop or livestock early-warning service.

The authoritative current setup and architecture are in the [repository README](../README.md), [frontend guide](../apps/frontend/README.md), and [data and model card](DATA_MODEL_CARD.md). Historical thesis documents and older notebooks can reflect prior versions or describe proposed rather than completed functionality.

The current frontend is an API-only Streamlit application. The backend scores complete user-supplied vectors, can calculate features from supplied measurements, extracts reviewed document text, provides historical views, and generates capability-protected snapshot reports. Unsafe legacy endpoints are retired rather than silently substituting values. Optional external AI, authentication and database services require configuration and are not validated by the offline tests.
