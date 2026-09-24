"""Voice input component — requires Web Speech API integration (placeholder)."""
import streamlit as st

st.subheader("🎤 Voice Input")
st.info("🎤 **Placeholder** — Real voice input requires browser Web Speech API integration via a custom Streamlit component.")

st.markdown("""
### Current Limitations
- **Streamlit native** does not support microphone access
- **Real implementation** would require a custom component using `window.SpeechRecognition`
- **HTTPS required** for microphone access in browsers

### Workaround
Use the text chat on the **Ask Gria** page for now.

### Future Integration
- Custom component with Web Speech API
- Server-side transcription via Whisper API
- Audio recording + upload to backend
""")

if st.button("🎤 Start Listening (Not Implemented)", disabled=True):
    pass
