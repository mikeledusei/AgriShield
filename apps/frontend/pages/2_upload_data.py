"""Upload data page - upload and analyze agricultural data files."""
import streamlit as st

from shared.sidebar import render_sidebar
from shared.uploader import render_uploader

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")

render_sidebar()
st.title("📤 Upload Agricultural Data")
st.write("Upload CSV, Excel, PDF, Word documents, or images for automated analysis.")

render_uploader()

st.divider()
st.subheader("📋 Upload Guidelines")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    **CSV/Excel Files**
    - Include columns: county_name, rainfall_anomaly_30d, ndvi_pasture_index, temp_max_avg, soil_moisture_deficit
    - Column names can vary (auto-detected)
    """)
with col2:
    st.markdown("""
    **PDF/Word Documents**
    - Any agricultural report or document
    - Gria extracts key indicators from text
    """)
with col3:
    st.markdown("""
    **Images**
    - Satellite or field photos
    - Vegetation analysis via color detection
    """)
