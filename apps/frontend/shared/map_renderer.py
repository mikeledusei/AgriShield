"""Map component for AgriShield."""
import folium
import streamlit as st
from streamlit_folium import st_folium
from typing import Optional


def create_risk_map(counties_data: list, center: Optional[tuple] = None,
                    zoom: int = 6, height: int = 500, width: int = 900):
    """Create an interactive risk map with county markers."""
    if center is None:
        center = [0.0236, 37.9062]

    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")

    color_map = {
        "SAFE": "green",
        "MODERATE": "orange",
        "HIGH": "red",
        "CRITICAL": "darkred",
        "UNKNOWN": "gray",
    }

    for county in counties_data:
        lat = county.get("lat", county.get("latitude"))
        lon = county.get("lon", county.get("longitude"))
        name = county.get("name", county.get("county", "Unknown"))
        risk_level = str(county.get("risk_level", county.get("level", "UNKNOWN"))).upper()
        risk_score = county.get("risk_score", county.get("score", "N/A"))
        color = color_map.get(risk_level, "gray")

        if lat is None or lon is None:
            st.warning(f"Missing coordinates for {name}")
            continue

        popup_html = f"""
        <div style="font-family:Arial;min-width:150px">
            <h4 style="color:#2e7d32;margin:5px">{name}</h4>
            <p><b>Risk Level:</b> {risk_level}</p>
            <p><b>Risk Score:</b> {risk_score}</p>
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{name} ({risk_level})",
            icon=folium.Icon(color=color, icon="info-sign", icon_color="white"),
        ).add_to(m)

    return st_folium(m, width=width, height=height)


def create_county_selector_map(counties: list, selected_county: str = ""):
    """Create map with a dropdown selector."""
    st.subheader("🗺️ County Risk Map")
    selected = st.selectbox("Select County to View", counties, index=0 if not selected_county else counties.index(selected_county))
    return selected
