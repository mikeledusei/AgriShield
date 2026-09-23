"""SMS subscription for risk alerts (placeholder)."""
import streamlit as st

st.subheader("📱 SMS Alerts Subscription")
st.info("📱 **Placeholder / Simulated** — Real SMS integration requires a provider (Africa's Talking, Twilio, etc.)")

county = st.selectbox("Your County", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])
phone = st.text_input("Phone Number", placeholder="+254 7XX XXX XXX")
frequency = st.selectbox("Alert Frequency", [
    "Daily summary",
    "Immediate on critical changes",
    "Weekly digest",
    "Only when risk changes level",
])

if st.button("Subscribe", type="primary"):
    if phone:
        st.warning("SMS subscription not yet implemented. This is a UI mockup.")
        st.info(f"Would subscribe: {phone} for {county} alerts ({frequency})")
    else:
        st.error("Please enter a phone number.")

st.caption("**Integration needed**: SMS gateway (Africa's Talking, Twilio, or local provider). Requires backend worker for scheduled alerts.")
