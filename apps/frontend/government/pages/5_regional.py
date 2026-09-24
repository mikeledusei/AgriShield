"""Regional — government regional aggregation view."""
import streamlit as st
from shared.api_client import get_region_aggregation, predict
from shared.gauges import risk_gauge, status_card
from shared.charts import risk_distribution_chart
from shared.sidebar import render_sidebar
from shared.constants import KENYAN_REGIONS

st.set_page_config(page_title="Regional", page_icon="🌍", layout="wide")
render_sidebar()

st.title("🌍 Regional Overview")
st.write("Aggregated risk intelligence for Kenyan regions.")

region = st.selectbox("Select Region", KENYAN_REGIONS)

st.divider()

st.subheader(f"Region: {region}")
try:
    result = get_region_aggregation(region)
    counties = result.get("counties", [])
    if counties:
        st.metric("Counties in Region", len(counties))

        col1, col2, col3 = st.columns(3)
        with col1:
            avg_risk = sum(c.get("risk_score", 0) for c in counties) / len(counties)
            st.metric("Average Risk", f"{avg_risk:.1f}%")
        with col2:
            critical = [c for c in counties if c.get("risk_level", "").upper() == "CRITICAL"]
            st.metric("Critical", len(critical))
        with col3:
            safe = [c for c in counties if c.get("risk_level", "").upper() == "SAFE"]
            st.metric("Safe", len(safe))

        st.divider()
        risk_distribution_chart(counties)
    else:
        st.info(f"No data available for {region}.")
except Exception as e:
    st.error(f"Failed to load regional data: {e}")

st.divider()
st.subheader("Regional Risk Breakdown")
# Get counties in this region from backend
try:
    result = get_region_aggregation(region)
    counties_in_region = [c["county_name"] for c in result.get("counties", [])]
except Exception:
    counties_in_region = ["Turkana", "Kajiado", "Kitui"]

for c in counties_in_region:
    try:
        data = predict(c)
        with st.expander(f"📍 {c}"):
            risk_gauge(data.get("risk_score"), data.get("risk_level"), title="Risk Score")
            st.write(f"**Main Driver:** {data.get('main_driver', 'N/A')}")
    except:
        pass
