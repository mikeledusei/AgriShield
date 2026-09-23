"""AgriShield Streamlit application — public portal (no authentication required)."""
import streamlit as st

from public.pages import *  # noqa: F401, F403

st.set_page_config(
    page_title="AgriShield — Public Portal",
    page_icon="🌾",
    layout="wide",
)

from shared.sidebar import render_sidebar
render_sidebar()
