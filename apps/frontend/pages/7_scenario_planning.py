"""Scenario planning - what-if analysis."""
import streamlit as st

from shared.api_client import scenario_analysis
from shared.sidebar import render_sidebar
from shared.gauges import risk_gauge, status_card

st.set_page_config(page_title="Scenario Planning", page_icon="🎛️", layout="wide")

render_sidebar()
st.title("🎛️ Scenario Planning")
st.write("Model 'what-if' scenarios by adjusting environmental factors.")

county = st.selectbox("Select County", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])

st.subheader("Adjust Parameters")
col1, col2, col3 = st.columns(3)
with col1:
    rainfall_change = st.slider("Rainfall Change (%)", -50.0, 50.0, 0.0, 0.5,
                                help="Positive = more rain, Negative = less rain")
with col2:
    temp_change = st.slider("Temperature Change (°C)", -5.0, 5.0, 0.0, 0.1,
                            help="Positive = warmer, Negative = cooler")
with col3:
    ndvi_shock = st.slider("NDVI Shock", -0.5, 0.5, 0.0, 0.01,
                           help="Positive = better vegetation, Negative = worse")

if st.button("Run Scenario Analysis", type="primary", use_container_width=True):
    with st.spinner("Running scenario analysis..."):
        try:
            result = scenario_analysis(county, rainfall_change, temp_change, ndvi_shock)

            original = result.get("original", {})
            scenario = result.get("scenario", {})

            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("🔴 Current Status")
                risk_gauge(original.get("risk_score"), original.get("risk_level"),
                           title="Current Risk")
                st.write(f"**Driver:** {original.get('main_driver', 'N/A')}")
                st.write(f"**Recommendation:** {original.get('recommendation', 'N/A')}")

            with col_b:
                st.subheader("🔵 Scenario Projection")
                risk_gauge(scenario.get("risk_score"), scenario.get("risk_level"),
                           title="Scenario Risk")
                st.write(f"**Driver:** {scenario.get('main_driver', 'N/A')}")
                st.write(f"**Recommendation:** {scenario.get('recommendation', 'N/A')}")

            st.divider()
            score_delta = result.get("score_delta", 0)
            status_card("Change", f"{score_delta:+d} points", result.get("narrative", ""))

            if score_delta > 0:
                st.warning(f"⚠️ Risk increases by {score_delta} points under this scenario.")
            elif score_delta < 0:
                st.success(f"✅ Risk decreases by {abs(score_delta)} points under this scenario.")
            else:
                st.info("No change in risk level under this scenario.")
        except Exception as e:
            st.error(f"Scenario analysis failed: {e}")
