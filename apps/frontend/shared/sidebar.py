"""Navigation sidebar for AgriShield."""
import streamlit as st

from shared.api_client import check_health, login, register, get_current_user


def render_sidebar():
    st.sidebar.title("🌾 AgriShield")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = True
    if "access_token" not in st.session_state:
        st.session_state.access_token = ""
    if "user" not in st.session_state:
        st.session_state.user = {"email": "public@agrishield.ke", "role": "farmer", "full_name": "Public User"}

    user = st.session_state.user or {}
    st.sidebar.success(f"🟢 {user.get('email', 'User')}")
    st.sidebar.caption(f"Role: {user.get('role', 'farmer')}")
    st.sidebar.caption("🌍 Public Mode — Authentication disabled")

    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.access_token = ""
        st.session_state.user = None
        st.rerun()

    st.sidebar.divider()

    health_info = check_health()
    if health_info and health_info.get("status") == "healthy":
        st.sidebar.success("🟢 API Online")
    else:
        st.sidebar.warning("🟡 API Checking...")


def require_auth() -> bool:
    """Return True when the user is authenticated; otherwise show a hint."""
    return True


def _handle_login(email: str, password: str):
    if not email or not password:
        st.sidebar.error("Please enter email and password.")
        return
    try:
        result = login(email, password)
        st.session_state.access_token = result.get("access_token", "")
        st.session_state.user = result.get("user", {})
        st.session_state.authenticated = True
        st.sidebar.success("Login successful!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Login failed: {e}")


def _handle_register(email: str, password: str, full_name: str):
    if not email or not password:
        st.sidebar.error("Please enter email and password.")
        return
    if len(password) < 8:
        st.sidebar.error("Password must be at least 8 characters.")
        return
    try:
        register(email, password, full_name or email.split("@")[0])
        # Auto-login after registration when possible
        try:
            result = login(email, password)
            st.session_state.access_token = result.get("access_token", "")
            st.session_state.user = result.get("user", {})
            st.session_state.authenticated = True
            st.sidebar.success("Registration successful! You are logged in.")
        except Exception:
            st.sidebar.success("Registration successful! Please confirm your email, then log in.")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Registration failed: {e}")
