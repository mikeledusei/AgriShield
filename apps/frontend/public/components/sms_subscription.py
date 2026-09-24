"""SMS subscription for risk alerts — requires SMS gateway integration (placeholder)."""
import streamlit as st

from shared.api_client import get_available_counties

st.subheader("📱 SMS Alerts Subscription")
st.info("📱 **Placeholder** — Real SMS integration requires an SMS gateway provider (Africa's Talking, Twilio, etc.) and a backend worker for scheduled alerts.")

# Try to get available counties
try:
    county_options = get_available_counties()
except Exception:
    from shared.constants import PUBLIC_COUNTIES
    county_options = PUBLIC_COUNTIES

county = st.selectbox("Your County", county_options)
phone = st.text_input("Phone Number", placeholder="+254 7XX XXX XXX")
frequency = st.selectbox("Alert Frequency", [
    "Daily summary",
    "Immediate on critical changes",
    "Weekly digest",
    "Only when risk changes level",
])

if st.button("Subscribe", type="primary", disabled=True):
    pass

st.caption("""
**Integration needed:**
- SMS gateway provider (Africa's Talking, Twilio, or local Kenyan provider)
- Backend worker for scheduled alert processing
- User subscription management in database
- Compliance with Kenya's data protection regulations
""")
