"""SMS subscription for risk alerts."""
import streamlit as st
from shared.sidebar import render_sidebar

st.subheader("📱 SMS Alerts Subscription")
st.write("Get SMS alerts when risk levels change in your county.")

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
        st.success(f"✅ You will receive SMS alerts for {county} at {phone}")
    else:
        st.error("Please enter a phone number.")

st.caption("Standard SMS rates may apply. You can unsubscribe anytime.")
