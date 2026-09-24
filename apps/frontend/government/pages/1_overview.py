"""Overview — government administrative dashboard."""
import streamlit as st
import pandas as pd

from shared.api_client import get_batch_predictions, compare_counties, list_reports, predict
from shared.gauges import risk_gauge, metric_row, status_card
from shared.charts import risk_distribution_chart, county_comparison_chart
from shared.sidebar import render_sidebar
from shared.map_renderer import create_risk_map
from shared.constants import PUBLIC_COUNTIES, KENYAN_COUNTIES

st.set_page_config(page_title="Overview", page_icon="🏛️", layout="wide")
render_sidebar()

st.title("🏛️ Government Overview")
st.write("Administrative dashboard — view national agricultural risk intelligence.")

st.divider()

st.subheader("📊 National Risk Summary")
try:
    batch = get_batch_predictions()
    counties = batch.get("counties", [])
    if counties:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Counties Monitored", len(counties))
        with col2:
            critical = [c for c in counties if c.get("risk_level", "").upper() == "CRITICAL"]
            st.metric("Critical Risk", len(critical))
        with col3:
            safe = [c for c in counties if c.get("risk_level", "").upper() == "SAFE"]
            st.metric("Safe", len(safe))

        st.divider()
        risk_distribution_chart(counties)
        county_comparison_chart(counties)
    else:
        st.info("No county data available yet.")
except Exception as e:
    st.error(f"Could not load overview data: {e}")

st.divider()
st.subheader("🗺️ All Counties Map")
try:
    batch = get_batch_predictions()
    counties = batch.get("counties", [])
    counties_data = []
    for c in counties:
        counties_data.append({
            "name": c["county_name"],
            "lat": 0,  # Will be filled from constants
            "lon": 0,
            "risk_level": c.get("risk_level", "UNKNOWN"),
            "risk_score": c.get("risk_score", 0),
        })
    
    # Add coordinates from constants
    from shared.constants import KENYAN_COUNTIES
    coord_map = {c["name"]: (c["lat"], c["lon"]) for c in KENYAN_COUNTIES}
    for c in counties_data:
        if c["name"] in coord_map:
            c["lat"], c["lon"] = coord_map[c["name"]]
    
    if counties_data:
        create_risk_map(counties_data)
    else:
        st.warning("Map data unavailable.")
except Exception as e:
    st.error(f"Could not load map: {e}")

st.divider()
st.subheader("📋 Recent Reports")
try:
    reports = list_reports()
    if reports and reports.get("reports"):
        df = pd.DataFrame(reports["reports"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No reports generated yet.")
except Exception:
    pass
