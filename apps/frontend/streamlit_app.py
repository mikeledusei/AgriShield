"""AgriShield home page — landing, health status, and quick overview."""
import streamlit as st

from shared.api_client import check_health, get_root
from shared.sidebar import render_sidebar

st.set_page_config(
    page_title="AgriShield Home",
    page_icon="🌾",
    layout="wide",
)

# Set app type for sidebar navigation
if "app_type" not in st.session_state:
    st.session_state["app_type"] = "main"

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

# System status is now in the sidebar via render_sidebar()

root = get_root()
if root:
    st.caption(f"Powered by AgriShield API v{root.get('version', '1.0.0')} | Backend Host: Render")
else:
    st.caption("Powered by AgriShield API | Backend Host: Render")
