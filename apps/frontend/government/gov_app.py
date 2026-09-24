"""Government portal — administrative dashboard for officials."""
import streamlit as st

st.set_page_config(
    page_title="AgriShield — Government Portal",
    page_icon="🏛️",
    layout="wide",
)

# Set app type for sidebar navigation
if "app_type" not in st.session_state:
    st.session_state["app_type"] = "government"

from shared.sidebar import render_sidebar
render_sidebar()
