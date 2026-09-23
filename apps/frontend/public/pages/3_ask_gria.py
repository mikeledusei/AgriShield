"""Ask Gria — public chat interface for Gria AI assistant."""
import streamlit as st

from shared.api_client import chat_with_gria
from shared.gauges import risk_gauge
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Ask Gria", page_icon="🤖", layout="wide")
render_sidebar()

st.title("🤖 Ask Gria")
st.write("Ask any question about agricultural risks in plain English. Gria will use real-time data to answer.")

county = st.selectbox("Select County for Context", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])

st.divider()

if "gria_messages" not in st.session_state:
    st.session_state.gria_messages = []

chat_container = st.container()
with chat_container:
    for msg in st.session_state.gria_messages:
        if msg["role"] == "user":
            st.markdown(f"**You:** {msg['content']}")
        else:
            st.markdown(f"**Gria:** {msg['content']}")

with st.form("gria_chat_public", clear_on_submit=True):
    col1, col2 = st.columns([4, 1])
    with col1:
        user_input = st.text_input("Your question:", placeholder="What is the current risk for this county?", label_visibility="collapsed")
    with col2:
        submit = st.form_submit_button("Send", use_container_width=True)

if submit and user_input:
    st.session_state.gria_messages.append({"role": "user", "content": user_input})
    with st.spinner("Gria is thinking..."):
        try:
            response = chat_with_gria(user_input, county)
            reply = response.get("reply", "I couldn't process your request.")
            risk_score = response.get("risk_score")
            risk_level = response.get("risk_level")

            st.session_state.gria_messages.append({"role": "assistant", "content": reply})

            if risk_level:
                st.caption(f"Risk: {risk_level} ({risk_score}%)")
        except Exception as e:
            st.error(f"Chat error: {e}")

    st.rerun()

st.divider()
st.subheader("Quick Prompts")
prompts = [
    f"Give me a detailed risk report for {county}",
    "What are the main risk drivers?",
    "What should farmers do to prepare?",
    "How does this compare to last year?",
]
cols = st.columns(len(prompts))
for i, prompt in enumerate(prompts):
    if cols[i].button(prompt, key=f"pub_prompt_{i}", use_container_width=True):
        if "gria_messages" not in st.session_state:
            st.session_state.gria_messages = []
        st.session_state.gria_messages.append({"role": "user", "content": prompt})
        with st.spinner("Gria is thinking..."):
            try:
                response = chat_with_gria(prompt, county)
                reply = response.get("reply", "I couldn't process your request.")
                st.session_state.gria_messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                st.error(f"Chat error: {e}")
        st.rerun()
