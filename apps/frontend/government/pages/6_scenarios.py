"""Scenarios — government scenario planning."""
import streamlit as st
from shared.api_client import scenario_analysis, get_available_counties
from shared.gauges import risk_gauge, status_card
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Scenarios", page_icon="🎛️", layout="wide")
render_sidebar()

st.title("🎛️ Government Scenario Planning")
st.write("Model 'what-if' scenarios for policy planning and resource allocation.")

# Fetch available counties
try:
    county_options = get_available_counties()
except Exception:
    from shared.constants import PUBLIC_COUNTIES
    county_options = PUBLIC_COUNTIES

county = st.selectbox("Select County", county_options)

st.subheader("Adjust Parameters")
col1, col2, col3 = st.columns(3)
with col1:
    rainfall_change = st.slider("Rainfall Change (%)", -50.0, 50.0, 0.0, 0.5)
with col2:
    temp_change = st.slider("Temperature Change (°C)", -5.0, 5.0, 0.0, 0.1)
with col3:
    ndvi_shock = st.slider("NDVI Shock", -0.5, 0.5, 0.0, 0.01)

scenarios = [
    ("Baseline", 0.0, 0.0, 0.0),
    ("Light Drought", -20.0, 1.0, -0.2),
    ("Severe Drought", -40.0, 2.0, -0.4),
    ("Heavy Rains", 30.0, -1.0, 0.3),
    ("Heat Wave", 0.0, 3.0, -0.3),
]

if st.button("Run Scenarios", type="primary", use_container_width=True):
    for name, rf, tmp, ndvi in scenarios:
        with st.spinner(f"Running {name} scenario..."):
            try:
                result = scenario_analysis(county, rf, tmp, ndvi)
                original = result.get("original", {})
                scenario = result.get("scenario", {})
                delta = result.get("score_delta", 0)

                with st.expander(f"📊 {name}: {delta:+d} points"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        risk_gauge(original.get("risk_score"), original.get("risk_level"), title="Current")
                    with col_b:
                        risk_gauge(scenario.get("risk_score"), scenario.get("risk_level"), title="Scenario")
                    status_card("Change", f"{delta:+d} points", result.get("narrative", ""))
            except Exception as e:
                st.error(f"{name} scenario failed: {e}")
