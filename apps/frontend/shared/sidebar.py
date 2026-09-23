"""Navigation sidebar for AgriShield."""
import streamlit as st

from shared.api_client import check_health


def render_sidebar():
    st.sidebar.title("🌾 AgriShield")

    # Public mode - no authentication needed
    st.sidebar.success("🟢 Public User")
    st.sidebar.caption("Role: farmer")
    st.sidebar.caption("🌍 Public Mode — No login required")

    if st.sidebar.button("Reset Session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.sidebar.divider()

    health_info = check_health()
    if health_info and health_info.get("status") == "healthy":
        st.sidebar.success("🟢 API Online")
    else:
        st.sidebar.warning("🟡 API Checking...")


def require_auth() -> bool:
    """Return True in public mode."""
    return True
