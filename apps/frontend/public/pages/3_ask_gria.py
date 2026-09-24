"""Ask Gria — public chat interface for Gria AI assistant."""
import streamlit as st

from shared.gauges import risk_gauge
from shared.sidebar import render_sidebar, get_quick_county
from shared.chat import render_chat, gria_quick_prompts
from shared.api_client import get_available_counties

st.set_page_config(page_title="Ask Gria", page_icon="🤖", layout="wide")
render_sidebar()

st.title("🤖 Ask Gria")
st.write("Ask any question about agricultural risks in plain English. Gria will use real-time data to answer.")

# Get available counties
try:
    county_options = get_available_counties()
except Exception:
    from shared.constants import PUBLIC_COUNTIES
    county_options = PUBLIC_COUNTIES

default_county = get_quick_county()
county = st.selectbox(
    "Select County for Context", 
    county_options,
    index=county_options.index(default_county) if default_county in county_options else 0
)

st.divider()

render_chat(county_name=county)

st.divider()
st.subheader("Quick Prompts")
gria_quick_prompts(county_name=county)
