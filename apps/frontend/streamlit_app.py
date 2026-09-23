"""AgriShield home page — landing, health status, and quick overview."""
import streamlit as st

from components.api_client import check_health, get_root
from shared.sidebar import render_sidebar

st.set_page_config(
    page_title="AgriShield Home",
    page_icon="🌾",
    layout="wide",
)

render_sidebar()

st.title("🌾 Welcome to AgriShield")
st.subheader("Agricultural Risk Intelligence & Early Warning System")

st.markdown("""
AgriShield provides data-driven risk insights, machine learning predictions,
and AI-generated evaluations to safeguard crop yields and livestock forage
across Kenyan counties.

### 🚀 Key Features
* **Risk Predictions:** Analyze county-level agricultural vulnerabilities for crops and livestock.
* **Spatial Risk Maps:** Interactive map visualizations highlighting high-risk regions.
* **Gria AI Insights:** Natural language risk explanations and actionable mitigation advice.
* **PDF Report Generation:** Export standardized regional risk assessments for government and NGO planning.

---
**Use the sidebar on the left to navigate between application tools.**
""")

st.divider()

st.sidebar.title("📌 System Status")
health = check_health()
if health and health.get("status") == "healthy":
    st.sidebar.success("🟢 API Status: Online")
elif health:
    st.sidebar.warning("🟡 API Status: Degraded")
else:
    st.sidebar.error("🔴 API Status: Cold Starting / Offline")
st.sidebar.info("Note: Render free tier may take 30–60s on first load.")

st.divider()
root = get_root()
if root:
    st.caption(f"Powered by AgriShield API v{root.get('version', '1.0.0')} | Backend Host: Render")
else:
    st.caption("Powered by AgriShield API | Backend Host: Render")
