"""Ask Gria — public chat interface for Gria AI assistant."""
import streamlit as st

from shared.gauges import risk_gauge
from shared.sidebar import render_sidebar
from shared.chat import render_chat, gria_quick_prompts

st.set_page_config(page_title="Ask Gria", page_icon="🤖", layout="wide")
render_sidebar()

st.title("🤖 Ask Gria")
st.write("Ask any question about agricultural risks in plain English. Gria will use real-time data to answer.")

county = st.selectbox("Select County for Context", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])

st.divider()

render_chat(county_name=county)

st.divider()
st.subheader("Quick Prompts")
gria_quick_prompts(county_name=county)
