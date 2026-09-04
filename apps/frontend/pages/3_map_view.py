import os
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium

# Page Configuration
st.set_page_config(page_title="County Risk Map", page_icon="🗺️", layout="wide")

# Backend Configuration
BACKEND_URL = st.secrets.get("BACKEND_URL") or os.getenv("BACKEND_URL", "https://agrishield-dnao.onrender.com")

st.title("🗺️ Kenya Agricultural Risk Map")
st.write("Interactive spatial visualization of crop yield and livestock forage risks across target counties.")

# Target Counties with Coordinates
COUNTIES = [
    {"name": "Turkana", "lat": 3.1167, "lon": 35.6000},
    {"name": "Kajiado", "lat": -1.8523, "lon": 36.7768},
    {"name": "Uasin Gishu", "lat": 0.5143, "lon": 35.2698},
    {"name": "Nakuru", "lat": -0.3031, "lon": 36.0800},
    {"name": "Kilifi", "lat": -3.5107, "lon": 39.9093},
]

# Color & Marker Mapping based on Backend risk_level contract
# (SAFE / MODERATE / HIGH / CRITICAL)
COLOR_MAP = {
    "SAFE": "green",
    "MODERATE": "orange",
    "HIGH": "red",
    "CRITICAL": "darkred",
    "UNKNOWN": "gray"
}

# Sector/Focus Selector
focus_area = st.radio("Select Risk Focus", ["crops", "livestock"], horizontal=True)

# Fetch Live Predictions via Loop (Fallback until /predictions/batch is live)
county_map_data = []

with st.spinner("Fetching live county risk predictions from backend... (Note: Cold starts may take ~30s)"):
    for c in COUNTIES:
        risk_level = "UNKNOWN"
        risk_score = "N/A"
        
        try:
            payload = {"county_name": c["name"], "focus": focus_area}
            res = requests.post(
                f"{BACKEND_URL}/api/v1/predictions/crop-yield", 
                json=payload, 
                timeout=10
            )
            
            if res.status_code == 200:
                data = res.json()
                risk_level = str(data.get("risk_level", "UNKNOWN")).upper()
                risk_score = data.get("risk_score", "N/A")
        except Exception:
            pass  # Fall back to UNKNOWN if network timeout occurs
            
        county_map_data.append({
            "county": c["name"],
            "lat": c["lat"],
            "lon": c["lon"],
            "risk_level": risk_level,
            "risk_score": risk_score,
            "color": COLOR_MAP.get(risk_level, "gray")
        })

# Create Folium Map centered on Kenya
m = folium.Map(location=[0.0236, 37.9062], zoom_start=6, tiles="OpenStreetMap")

# Add Live County Risk Markers
for item in county_map_data:
    folium.Marker(
        location=[item["lat"], item["lon"]],
        popup=f"<b>{item['county']}</b><br>Level: {item['risk_level']}<br>Score: {item['risk_score']}",
        tooltip=f"{item['county']} ({item['risk_level']})",
        icon=folium.Icon(color=item["color"], icon="info-sign")
    ).add_to(m)

# Render Map in Streamlit
st_data = st_folium(m, width=900, height=500)

st.markdown("""
**Legend:**
* 🟢 **SAFE:** Normal agricultural conditions
* 🟠 **MODERATE:** Monitor closely for environmental stress
* 🔴 **HIGH:** High vulnerability detected
* 🔴 **CRITICAL:** Immediate relief/intervention required
* ⚪ **UNKNOWN / GRAY:** Backend cold starting or unreachable
""")
