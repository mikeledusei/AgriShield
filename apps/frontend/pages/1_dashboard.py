"""Risk dashboard page — single-county prediction."""
import streamlit as st

from components.api_client import predict
from shared.sidebar import render_sidebar
from components.gauges import risk_gauge
from components.chat import render_chat

st.set_page_config(
    page_title="AgriShield Dashboard",
    page_icon="🌾",
    layout="wide",
)

render_sidebar()

st.title("🌾 AgriShield: Agricultural Risk Intelligence")

selected_county = st.selectbox(
    "Select County",
    ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"],
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
