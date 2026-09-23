"""Voice input — speech-to-text for hands-free interaction."""
import streamlit as st
from shared.sidebar import render_sidebar

st.subheader("🎤 Voice Input")
st.write("Speak your question and Gria will read the response aloud.")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("🎤 Start Listening", type="primary"):
        st.info("Listening... (simulated — use keyboard input in production)")
with col2:
    if st.button("🔇 Stop", type="secondary"):
        st.info("Stopped listening.")

st.divider()
st.markdown("""
### Recent Transcriptions
- "What is the risk in Turkana?" → 45% — HIGH
- "Will there be drought this year?" → Moderate risk of drought
- "How to prepare for floods?" → Elevated flood risk in low-lying areas
""")
