"""Home — public landing page with quick overview and featured content."""
import streamlit as st

from shared.api_client import check_health, predict
from shared.gauges import risk_gauge
from shared.sidebar import render_sidebar
from shared.risk_helpers import RISK_THRESHOLDS

st.set_page_config(page_title="Home", page_icon="🏠", layout="wide")
render_sidebar()

st.title("🏠 Welcome to AgriShield Public Portal")
st.markdown("**Your trusted source for agricultural risk intelligence across Kenya.**")

st.markdown("""
AgriShield helps farmers, county officials, and stakeholders understand
agricultural risks before disasters strike. Explore risk levels across
Kenyan counties, get AI-powered insights, and access actionable recommendations.
""")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("🗺️ Featured County Risk")
    county = st.selectbox("Select a county", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])
    focus = st.radio("Focus", ["crops", "livestock"], horizontal=True, key="home_focus")
    try:
        data = predict(county, focus)
        risk_gauge(data.get("risk_score"), data.get("risk_level"), title="Current Risk")
        st.write(f"**Main Driver:** {data.get('main_driver', 'N/A')}")
        st.write(f"**Recommendation:** {data.get('recommendation', 'N/A')}")
        st.caption(f"Model: {data.get('model_used', 'N/A')}")
    except Exception as e:
        st.warning(f"Could not load prediction: {e}")

with col2:
    st.subheader("⚡ Quick Stats")
    health = check_health()
    if health:
        st.metric("API Status", "🟢 Online" if health.get("status") == "healthy" else "🟡 Degraded")
        services = health.get("services", {})
        for svc, status in services.items():
            st.write(f"• **{svc.capitalize()}:** {status}")
    else:
        st.warning("API is checking...")

    st.divider()
    st.subheader("🌍 Public Portal")
    st.info("This portal provides open access to agricultural risk data. No login required.")
    st.caption("Use the sidebar to navigate or explore the pages below.")

st.divider()
st.subheader("📊 County Risk Overview")
st.markdown("""
- **SAFE** (0–25): Normal agricultural conditions
- **MODERATE** (25–50): Monitor closely for environmental stress
- **HIGH** (50–75): High vulnerability detected
- **CRITICAL** (75–100): Immediate relief/intervention required
""")
