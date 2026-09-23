"""Gria AI Chat component for shared usage."""
import streamlit as st
from shared.api_client import chat_with_gria


def render_gria_chat(county_name: str = None, placeholder_text: str = "Ask Gria about agricultural risks..."):
    """Render a chat interface for Gria AI."""
    if "gria_messages" not in st.session_state:
        st.session_state.gria_messages = []

    st.subheader("🤖 Gria AI Assistant")

    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.gria_messages:
            if msg["role"] == "user":
                st.markdown(f"**You:** {msg['content']}")
            else:
                st.markdown(f"**Gria:** {msg['content']}")

    with st.form("gria_chat_form_shared", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            user_input = st.text_input("Your question:", placeholder=placeholder_text, label_visibility="collapsed")
        with col2:
            submit = st.form_submit_button("Send", use_container_width=True)

    if submit and user_input:
        st.session_state.gria_messages.append({"role": "user", "content": user_input})
        with st.spinner("Gria is thinking..."):
            try:
                response = chat_with_gria(user_input, county_name)
                reply = response.get("reply", "I couldn't process your request.")
                risk_score = response.get("risk_score")
                risk_level = response.get("risk_level")

                st.session_state.gria_messages.append({"role": "assistant", "content": reply})

                if risk_level:
                    st.caption(f"Risk: {risk_level} ({risk_score}%)")
            except Exception as e:
                st.error(f"Chat error: {e}")

        st.rerun()
