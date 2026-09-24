"""Historical trends page."""
import streamlit as st

from shared.api_client import get_history, get_batch_predictions, get_available_counties
from shared.sidebar import render_sidebar
from shared.charts import risk_score_trend_chart, risk_distribution_chart
from shared.gauges import risk_gauge

st.set_page_config(page_title="Historical Trends", page_icon="📈", layout="wide")

render_sidebar()
st.title("📈 Historical Risk Trends")
st.write("Track how agricultural risk has changed over time.")

# Fetch available counties from backend
try:
    county_options = get_available_counties()
except Exception:
    county_options = ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"]

county = st.selectbox("Select County", county_options)
months = st.slider("Time Range (months)", 1, 60, 12)

if st.button("Load Trends", type="primary", use_container_width=True):
    with st.spinner("Loading trends..."):
        try:
            result = get_history(county, months)
            trend = result.get("trend", [])
            if not trend:
                st.info(f"No historical predictions recorded for {county} yet. "
                        "Generate predictions from the Dashboard to build history.")
            else:
                st.subheader(f"Risk Score Over Time — {county}")
                risk_score_trend_chart(trend, county_name=county)
                st.write(f"**Data points:** {len(trend)}")
                latest = trend[-1]
                risk_gauge(latest.get("risk_score"), latest.get("risk_level"),
                           title="Latest Risk Score")
        except Exception as e:
            st.error(f"Failed to load trends: {e}")

st.divider()
st.subheader("Current Risk Distribution Across Counties")
if st.button("Load Batch Predictions", use_container_width=True):
    with st.spinner("Loading batch predictions..."):
        try:
            batch = get_batch_predictions()
            counties = batch.get("counties", [])
            if counties:
                risk_distribution_chart(counties)
                st.caption(f"Generated at: {batch.get('generated_at', 'N/A')}")
            else:
                st.info("No county data available.")
        except Exception as e:
            st.error(f"Failed to load batch predictions: {e}")
