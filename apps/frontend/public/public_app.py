"""AgriShield Streamlit application — public portal (no authentication required)."""
import streamlit as st

st.set_page_config(
    page_title="AgriShield — Public Portal",
    page_icon="🌾",
    layout="wide",
)

# Set app type for sidebar navigation
if "app_type" not in st.session_state:
    st.session_state["app_type"] = "public"

from shared.sidebar import render_sidebar
render_sidebar()
