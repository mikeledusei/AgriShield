"""Upload Data — government bulk data upload and processing."""
import streamlit as st
from shared.api_client import upload_and_analyze
from shared.uploader import render_uploader
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")
render_sidebar()

st.title("📤 Government Data Upload")
st.write("Upload and analyze agricultural data for regional planning.")

render_uploader(title="Upload Government Data File")

st.divider()
st.subheader("📋 Upload Guidelines for Government")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    **CSV/Excel Files**
    - County-level data preferred
    - Include timestamps where available
    - Multiple file uploads supported
    """)
with col2:
    st.markdown("""
    **PDF/Word Documents**
    - Government reports and policy docs
    - Annual agricultural assessments
    - Disaster response reports
    """)
with col3:
    st.markdown("""
    **Images**
    - Satellite imagery for regional analysis
    - Drone survey photos
    - Damage assessment photos
    """)
