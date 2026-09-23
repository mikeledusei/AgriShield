"""County risk map page with live predictions."""
import streamlit as st

from components.api_client import predict
from shared.sidebar import render_sidebar
from components.map import create_risk_map

st.set_page_config(page_title="County Risk Map", page_icon="🗺️", layout="wide")

render_sidebar()

st.title("🗺️ Kenya Agricultural Risk Map")
st.write("Interactive spatial visualization of crop yield and livestock forage risks across target counties.")

COUNTIES = [
    {"name": "Turkana", "lat": 3.1167, "lon": 35.6000},
    {"name": "Kajiado", "lat": -1.8523, "lon": 36.7768},
    {"name": "Uasin Gishu", "lat": 0.5143, "lon": 35.2698},
    {"name": "Nakuru", "lat": -0.3031, "lon": 36.0800},
    {"name": "Kilifi", "lat": -3.5107, "lon": 39.9093},
]

focus_area = st.radio("Select Risk Focus", ["crops", "livestock"], horizontal=True)

county_map_data = []
errors = []

with st.spinner("Fetching live county risk predictions from backend..."):
    for c in COUNTIES:
        risk_level = "UNKNOWN"
        risk_score = "N/A"
        try:
            data = predict(c["name"], focus_area)
            risk_level = str(data.get("risk_level", "UNKNOWN")).upper()
            risk_score = data.get("risk_score", "N/A")
        except Exception as e:
            errors.append(f"{c['name']}: {e}")

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

st.markdown("""
**Legend:**
* 🟢 **SAFE:** Normal agricultural conditions
* 🟠 **MODERATE:** Monitor closely for environmental stress
* 🔴 **HIGH:** High vulnerability detected
* 🔴 **CRITICAL:** Immediate relief/intervention required
* ⚪ **UNKNOWN:** Backend cold starting or unreachable
""")
