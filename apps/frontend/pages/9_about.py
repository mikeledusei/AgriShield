"""About page."""
import os
import streamlit as st
from shared.api_client import get_root, check_health
from shared.sidebar import render_sidebar

st.set_page_config(page_title="About", page_icon="ℹ️", layout="wide")

render_sidebar()
st.title("ℹ️ About AgriShield")

st.markdown("""
## 🌾 AgriShield — Agricultural Risk Intelligence & Early Warning System

AgriShield provides data-driven risk insights, machine learning predictions,
and AI-generated evaluations to safeguard crop yields and livestock forage
across Kenyan counties.
""")

st.divider()

st.subheader("System Architecture")
st.markdown("""
```
┌─────────────────────────────────┐
│  STREAMLIT FRONTEND             │
│  (Dashboard, Maps, Uploads)     │
└──────────────┬──────────────────┘
               │ HTTP Requests
               ▼
┌─────────────────────────────────┐
│  FASTAPI BACKEND                │
│  (Predictions, Reports, AI)     │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  XGBoost Model + Gria AI        │
└─────────────────────────────────┘
```
""")

st.divider()

st.subheader("Key Features")
features = [
    ("📊 Risk Dashboard", "Real-time risk scores with visual gauges for any county"),
    ("🗺️ Interactive Map", "Color-coded map of Kenyan counties by risk level"),
    ("🤖 Gria AI Chat", "Ask questions in plain English and get instant insights"),
    ("📤 Smart File Upload", "Upload CSV, PDF, Word, or images — Gria converts them"),
    ("📈 Dynamic Charts", "AI-generated charts that update based on your questions"),
    ("⚖️ County Comparison", "Compare risk levels between counties side by side"),
    ("🎛️ Scenario Planning", "Adjust rainfall and temperature for what-if outcomes"),
    ("📄 PDF Reports", "One-click professional reports for decision makers"),
]
for title, desc in features:
    st.markdown(f"**{title}** — {desc}")

st.divider()

st.subheader("System Status")
health = check_health()
if health:
    st.json(health)
else:
    st.warning("Unable to fetch system status.")

st.divider()
st.markdown("**Version:** 1.0.0 | **License:** Proprietary | **Copyright © 2026 AgriShield")
