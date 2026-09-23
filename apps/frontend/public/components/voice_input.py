"""Voice input — speech-to-text for hands-free interaction (placeholder)."""
import streamlit as st

st.subheader("🎤 Voice Input")
st.info("🎤 **Placeholder / Simulated** — Real voice input requires browser SpeechRecognition API integration.")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("🎤 Start Listening", type="primary"):
        st.warning("Voice input not implemented. Use keyboard input below instead.")
with col2:
    if st.button("🔇 Stop", type="secondary"):
        st.info("Stopped.")

st.divider()
st.markdown("""
### Implementation Notes
- **Real implementation** would use Web Speech API (`window.SpeechRecognition`) via Streamlit custom component
- **Current workaround**: Use the text chat on "Ask Gria" page
- **Required**: HTTPS origin for microphone access in browsers
- **Backend**: Could integrate with Whisper API or similar for server-side transcription
""")
