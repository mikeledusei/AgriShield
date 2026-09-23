"""Settings — government configuration and preferences."""
import streamlit as st
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
render_sidebar()

st.title("⚙️ Government Settings")
st.write("Configure government portal settings and preferences.")

st.divider()

st.subheader("Portal Configuration")

app_name = st.text_input("Application Name", value="AgriShield Government Portal")
language = st.selectbox("Default Language", ["en", "sw"], index=0)
theme = st.selectbox("Theme", ["Light", "Dark", "Auto"], index=0)

st.divider()
st.subheader("Notification Settings")
email_notifications = st.checkbox("Email Notifications", value=True)
sms_alerts = st.checkbox("SMS Alerts", value=True)
critical_only = st.checkbox("Critical Events Only", value=False)

st.divider()
st.subheader("Data Settings")
refresh_interval = st.slider("Data Refresh Interval (minutes)", 5, 120, 30)
default_region = st.selectbox("Default Region",
    ["Rift Valley", "Eastern", "Central", "Nyanza", "Western", "Coast", "North Eastern"])

st.divider()
st.subheader("About")
st.markdown("""
**AgriShield Government Portal v1.0.0**

Manage agricultural risk intelligence for county officials and national government.

- **Region:** Kenya
- **Focus:** Crop Yield & Livestock Forage Risk
- **AI:** Gria Agentic AI Assistant
- **Models:** XGBoost (agri-pred-v1)
""")

if st.button("Save Settings", type="primary"):
    st.success("✅ Settings saved successfully!")
