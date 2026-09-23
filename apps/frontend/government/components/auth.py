"""Government authentication component (temporarily disabled)."""
import streamlit as st


def render_gov_auth():
    """Render government auth — temporarily in public mode."""
    st.subheader("🔐 Government Access")
    st.info("🌍 Public Mode — All government portals accessible without login.")
    st.write("**Role:** Government Official (auto-authenticated)")
    st.write("**Department:** National Agriculture")


def require_gov_auth() -> bool:
    """Always return True in public mode."""
    return True
