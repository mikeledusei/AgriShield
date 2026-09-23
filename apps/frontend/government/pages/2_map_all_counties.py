"""Map All Counties — government comprehensive map view."""
import streamlit as st
from shared.api_client import predict
from shared.map_renderer import create_risk_map
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Map — All Counties", page_icon="🗺️", layout="wide")
render_sidebar()

st.title("🗺️ All Counties Risk Map")
st.write("Comprehensive spatial view of all Kenyan counties with real-time risk data.")

COUNTIES = [
    {"name": "Turkana", "lat": 3.1167, "lon": 35.6000},
    {"name": "Kajiado", "lat": -1.8523, "lon": 36.7768},
    {"name": "Uasin Gishu", "lat": 0.5143, "lon": 35.2698},
    {"name": "Nakuru", "lat": -0.3031, "lon": 36.0800},
    {"name": "Kilifi", "lat": -3.5107, "lon": 39.9093},
    {"name": "Meru", "lat": 0.0467, "lon": 37.6536},
    {"name": "Kisumu", "lat": -0.0917, "lon": 34.7680},
    {"name": "Kitui", "lat": -1.3670, "lon": 38.0129},
    {"name": "Machakos", "lat": -1.5172, "lon": 37.2661},
    {"name": "Makueni", "lat": -1.7829, "lon": 37.6220},
    {"name": "Bungoma", "lat": 0.5639, "lon": 34.5639},
    {"name": "Kakamega", "lat": 0.2817, "lon": 34.7583},
    {"name": "Nakuru", "lat": -0.3031, "lon": 36.0800},
    {"name": "Nakuru", "lat": -0.3031, "lon": 36.0800},
]

focus = st.radio("Risk Focus", ["crops", "livestock"], horizontal=True)

county_map_data = []
errors = []
with st.spinner("Fetching all county predictions..."):
    seen = set()
    for c in COUNTIES:
        if c["name"] in seen:
            continue
        seen.add(c["name"])
        try:
            data = predict(c["name"], focus)
            risk_level = str(data.get("risk_level", "UNKNOWN")).upper()
            risk_score = data.get("risk_score", "N/A")
        except Exception as e:
            errors.append(f"{c['name']}: {e}")
            risk_level = "UNKNOWN"
            risk_score = "N/A"
        county_map_data.append({
            "county": c["name"],
            "lat": c["lat"],
            "lon": c["lon"],
            "risk_level": risk_level,
            "risk_score": risk_score,
        })

if errors:
    with st.expander("⚠️ Some counties could not be loaded"):
        for err in errors:
            st.caption(err)

create_risk_map(county_map_data)
