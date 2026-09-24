"""Trends — government historical analysis."""
import streamlit as st
import pandas as pd
from shared.api_client import get_history, get_batch_predictions, get_available_counties
from shared.charts import risk_score_trend_chart, risk_distribution_chart
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Trends", page_icon="📈", layout="wide")
render_sidebar()

st.title("📈 Government Trends Analysis")
st.write("Analyze historical agricultural risk trends across all counties.")

# Fetch available counties
try:
    county_options = get_available_counties()
except Exception:
    from shared.constants import PUBLIC_COUNTIES
    county_options = PUBLIC_COUNTIES

col1, col2 = st.columns(2)
with col1:
    county = st.selectbox("Select County", county_options)
    months = st.slider("Time Range (months)", 1, 60, 12)

with col2:
    focus = st.radio("Focus", ["crops", "livestock"], horizontal=True)

st.divider()

st.subheader("Risk Score Over Time")
try:
    result = get_history(county, months)
    trend = result.get("trend", [])
    if trend:
        risk_score_trend_chart(trend, county_name=county)
        st.write(f"**Data points:** {len(trend)}")
    else:
        st.info(f"No historical data for {county} yet.")
except Exception as e:
    st.error(f"Failed to load trends: {e}")

st.divider()
st.subheader("National Risk Distribution")
try:
    batch = get_batch_predictions()
    counties = batch.get("counties", [])
    if counties:
        risk_distribution_chart(counties)
        st.caption(f"Generated: {batch.get('generated_at', 'N/A')}")
except Exception as e:
    st.error(f"Failed to load distribution: {e}")
