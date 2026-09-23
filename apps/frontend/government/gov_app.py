"""Government portal — administrative dashboard for officials."""
import streamlit as st

from government.pages import *  # noqa: F401, F403

st.set_page_config(
    page_title="AgriShield — Government Portal",
    page_icon="🏛️",
    layout="wide",
)

from shared.sidebar import render_sidebar
render_sidebar()
