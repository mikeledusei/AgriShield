"""My County — personal county risk dashboard for public users."""
import streamlit as st

from shared.api_client import predict, get_history
from shared.gauges import risk_gauge
from shared.charts import risk_score_trend_chart
from shared.sidebar import render_sidebar

st.set_page_config(page_title="My County", page_icon="🏘️", layout="wide")
render_sidebar()

st.title("🏘️ My County")
st.write("View your county's current risk level and historical trends.")

county = st.selectbox("Select Your County", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])
focus = st.radio("Risk Focus", ["crops", "livestock"], horizontal=True)

st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Current Risk")
    try:
        data = predict(county, focus)
        risk_gauge(data.get("risk_score"), data.get("risk_level"), title="Risk Score")
        st.write(f"**Main Driver:** {data.get('main_driver', 'N/A')}")
        st.write(f"**Recommendation:** {data.get('recommendation', 'N/A')}")
        st.caption(f"Model: {data.get('model_used', 'N/A')}")
    except Exception as e:
        st.error(f"Failed to load prediction: {e}")

with col2:
    st.subheader("Risk Trend (12 months)")
    try:
        result = get_history(county, 12)
        trend = result.get("trend", [])
        if trend:
            risk_score_trend_chart(trend, county_name=county)
            st.write(f"**Data points:** {len(trend)}")
        else:
            st.info("No historical data available yet. Generate predictions from the Dashboard.")
    except Exception as e:
        st.warning(f"Could not load history: {e}")
