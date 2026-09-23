"""Farming Tips — agricultural advice and best practices for Kenyan farmers."""
import streamlit as st
from shared.sidebar import render_sidebar
from shared.gauges import risk_badge

st.set_page_config(page_title="Farming Tips", page_icon="🌱", layout="wide")
render_sidebar()

st.title("🌱 Farming Tips & Best Practices")
st.write("Practical agricultural guidance based on current risk conditions across Kenya.")

st.divider()

st.subheader("🌦️ Seasonal Farming Calendar")
calendar = [
    ("March–May (Long Rains)", "Plant maize, beans, sorghum. Prepare terraces for erosion control."),
    ("June–September (Dry Season)", "Focus on irrigation. Harvest early-maturing crops. Store fodder."),
    ("October–December (Short Rains)", "Plant second-season crops. Prepare for possible flooding."),
    ("January–February (Short Dry)", "Soil conservation. Planning for next season. Livestock management."),
]
for season, tip in calendar:
    st.markdown(f"### {season}")
    st.info(tip)

st.divider()

st.subheader("🌾 Crop-Specific Tips")
crop_tips = [
    ("Maize", "Use certified seed. Apply fertilizer at planting and tillering. Monitor for fall armyworm."),
    ("Beans", "Intercrop with maize. Practice crop rotation. Harvest when pods are dry."),
    ("Sorghum", "Drought-resistant variety. Plant in well-drained soils. Reduce planting density in dry years."),
    ("Cassava", "Use disease-free cuttings. Rotate planting sites. Harvest after 8–12 months."),
    ("Livestock", "Ensure vaccination schedules. Provide supplementary feed during drought. Rotate pastures."),
]
for crop, tip in crop_tips:
    st.markdown(f"**{crop}:** {tip}")

st.divider()

st.subheader("⚠️ Risk-Based Recommendations")
st.markdown(f"""
- **SAFE**: Normal operations. Continue regular farming practices.
- **MODERATE**: Monitor weather forecasts. Reduce irrigation water usage. Check storage facilities.
- **HIGH**: Implement drought mitigation measures. Consider crop insurance. Reduce livestock stocking density.
- **CRITICAL**: Seek government assistance. Activate emergency irrigation. Relocate livestock to safer areas.
""")
