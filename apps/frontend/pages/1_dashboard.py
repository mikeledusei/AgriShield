"""Risk dashboard page — single-county prediction."""
import streamlit as st

from shared.api_client import predict, get_available_counties
from shared.sidebar import render_sidebar, get_quick_county
from shared.gauges import risk_gauge
from shared.chat import render_chat

st.set_page_config(
    page_title="AgriShield Dashboard",
    page_icon="🌾",
    layout="wide",
)

render_sidebar()

st.title("🌾 AgriShield: Agricultural Risk Intelligence")

# Fetch available counties from backend
try:
    county_options = get_available_counties()
except Exception:
    from shared.constants import PUBLIC_COUNTIES
    county_options = PUBLIC_COUNTIES

default_county = get_quick_county()
selected_county = st.selectbox(
    "Select County",
    county_options,
    index=county_options.index(default_county) if default_county in county_options else 0,
)
focus_area = st.radio("Select Focus", ["crops", "livestock"], horizontal=True)

if st.button("Generate Risk Prediction", type="primary"):
    with st.spinner("Fetching prediction from backend... (cold starts may take ~30s)"):
        try:
            data = predict(selected_county, focus_area)
            risk_gauge(data.get("risk_score"), data.get("risk_level"), title="Risk Score")
            st.subheader(f"Risk Level: {data.get('risk_level', 'UNKNOWN')}")
            st.write(f"**Main Driver:** {data.get('main_driver', 'N/A')}")
            st.info(f"**Recommendation:** {data.get('recommendation', 'N/A')}")
            st.caption(f"Model: {data.get('model_used', 'N/A')} | Region: {data.get('region', 'N/A')}")
        except Exception as e:
            st.error(f"Prediction failed: {e}")

st.divider()
render_chat(county_name=selected_county)
