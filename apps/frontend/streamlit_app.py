import os
import requests
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="AgriShield Home",
    page_icon="🌾",
    layout="wide"
)

# Backend URL Configuration
BACKEND_URL = st.secrets.get("BACKEND_URL") or os.getenv("BACKEND_URL", "https://agrishield-dnao.onrender.com")

# -----------------------------------------------------------------------------
# SIDEBAR: API HEALTH STATUS BADGE
# -----------------------------------------------------------------------------
st.sidebar.title("📌 System Status")

try:
    # 5-second timeout to handle Render cold starts gracefully
    health_res = requests.get(f"{BACKEND_URL}/api/v1/health", timeout=5)
    if health_res.status_code == 200:
        st.sidebar.success("🟢 API Status: Online")
    else:
        st.sidebar.warning(f"🟡 API Status: Degraded ({health_res.status_code})")
except Exception:
    st.sidebar.error("🔴 API Status: Cold Starting / Offline")

st.sidebar.info("Note: Render free tier may take 30–60s on first load.")

# -----------------------------------------------------------------------------
# MAIN CONTENT: PUBLIC HOME LANDING
# -----------------------------------------------------------------------------
st.title("🌾 Welcome to AgriShield")
st.subheader("Agricultural Risk Intelligence & Early Warning System")

st.markdown("""
AgriShield provides data-driven risk insights, machine learning predictions, 
and AI-generated evaluations to safeguard crop yields and livestock forage across Kenyan counties.

### 🚀 Key Features
* **Risk Predictions:** Analyze county-level agricultural vulnerabilities for crops and livestock.
* **Spatial Risk Maps:** Interactive map visualizations highlighting high-risk regions.
* **Gria AI Insights:** Natural language risk explanations and actionable mitigation advice.
* **PDF Report Generation:** Export standardized regional risk assessments for government and NGO planning.

---
**Use the sidebar on the left to navigate between application tools.**
""")

# -----------------------------------------------------------------------------
# FOOTER: METADATA FETCHING (GET /)
# -----------------------------------------------------------------------------
st.divider()
try:
    meta_res = requests.get(f"{BACKEND_URL}/", timeout=3)
    if meta_res.status_code == 200:
        meta_data = meta_res.json()
        st.caption(f"Powered by AgriShield API v{meta_data.get('version', '1.0.0')} | Backend Host: Render")
    else:
        st.caption("Powered by AgriShield API | Backend Host: Render")
except Exception:
    st.caption("Powered by AgriShield API | Backend Host: Render")
