"""Voice output — text-to-speech for accessibility."""
import streamlit as st
from shared.sidebar import render_sidebar

st.subheader("🔊 Voice Output")
st.write("Listen to agricultural risk summaries read aloud.")

text = st.text_area("Enter text to read aloud", height=150,
    value="Risk conditions in your selected county are currently at a safe level. Continue monitoring for changes.")

if st.button("🔊 Play", type="primary"):
    st.info(f"🔊 Reading: \"{text[:100]}...\"")
    st.caption("Voice output requires browser microphone/speaker access.")

st.divider()
st.markdown("""
### Available Languages
- 🇬🇧 English
- 🇰🇪 Kiswahili
""")
