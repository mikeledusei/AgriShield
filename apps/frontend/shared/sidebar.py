"""Navigation sidebar for AgriShield — clean, concise, organized."""
import streamlit as st
from typing import Literal

from shared.api_client import check_health, get_available_counties


AppMode = Literal["main", "public", "government"]

PAGE_GROUPS = {
    "main": [
        ("📊 Dashboard", "pages/1_dashboard.py"),
        ("🗺️ Map View", "pages/3_map_view.py"),
        ("⚖️ Compare", "pages/4_compare.py"),
        ("📄 Regional Overview", "pages/5_regional_overview.py"),
        ("📤 Upload Data", "pages/2_upload_data.py"),
        ("📈 Trends", "pages/6_trends.py"),
        ("🎛️ Scenarios", "pages/7_scenario_planning.py"),
        ("📑 Reports", "pages/8_reports.py"),
        ("ℹ️ About", "pages/9_about.py"),
    ],
    "public": [
        ("🏠 Home", "pages/1_home.py"),
        ("🏘️ My County", "pages/2_my_county.py"),
        ("🤖 Ask Gria", "pages/3_ask_gria.py"),
        ("📋 Quick Report", "pages/4_quick_report.py"),
        ("🌱 Farming Tips", "pages/5_farming_tips.py"),
        ("📷 Upload Photo", "pages/6_upload_photo.py"),
    ],
    "government": [
        ("🏛️ Overview", "pages/1_overview.py"),
        ("🗺️ Map All Counties", "pages/2_map_all_counties.py"),
        ("📈 Trends", "pages/3_trends.py"),
        ("⚖️ Comparison", "pages/4_comparison.py"),
        ("🌍 Regional", "pages/5_regional.py"),
        ("🎛️ Scenarios", "pages/6_scenarios.py"),
        ("📑 Reports", "pages/7_reports.py"),
        ("📤 Upload Data", "pages/8_upload_data.py"),
        ("⚙️ Settings", "pages/9_settings.py"),
    ],
}


def _get_current_app() -> AppMode:
    return st.session_state.get("app_type", "main")


def _render_header():
    """App title and mode indicator."""
    app = _get_current_app()
    
    # Title + mode badge
    col1, col2 = st.sidebar.columns([3, 2])
    with col1:
        st.markdown("# 🌾 AgriShield")
    with col2:
        badges = {"main": "🏠 Main", "public": "🟢 Public", "government": "🔵 Gov"}
        st.markdown(f"**{badges.get(app, app)}**")
    
    st.sidebar.caption("Agricultural Risk Intelligence")
    st.sidebar.divider()


def _render_navigation(app: AppMode):
    """Navigation menu — clean button list."""
    pages = PAGE_GROUPS.get(app, [])
    current_page = st.query_params.get("page", [None])[0]
    
    for label, page_path in pages:
        page_name = page_path.split("/")[-1].replace(".py", "")
        is_active = current_page == page_name
        
        if st.sidebar.button(
            label,
            key=f"nav_{page_name}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.query_params["page"] = page_name
            st.switch_page(page_path)


def _render_county_selector():
    """County context selector — only when useful."""
    app = _get_current_app()
    if app not in ("public", "government"):
        return
    
    try:
        counties = get_available_counties()
    except Exception:
        from shared.constants import PUBLIC_COUNTIES
        counties = PUBLIC_COUNTIES
    
    if not counties:
        return
    
    current = st.session_state.get("quick_county", counties[0])
    selected = st.sidebar.selectbox(
        "County Context",
        counties,
        index=counties.index(current) if current in counties else 0,
        key="quick_county_select",
        label_visibility="collapsed",
    )
    if selected != current:
        st.session_state["quick_county"] = selected
        st.rerun()


def _render_collapsible_sections():
    """Collapsible sections for less-frequent controls."""
    app = _get_current_app()
    
    # System Status — collapsible
    with st.sidebar.expander("🖥️ System Status", expanded=False):
        with st.spinner("Checking..."):
            health = check_health()
        if health and health.get("status") == "healthy":
            st.success("🟢 API Online")
            for svc, status in health.get("services", {}).items():
                icon = "🟢" if "not configured" not in str(status).lower() and status != "offline" else "🟡"
                st.caption(f"{icon} **{svc.capitalize()}:** {status}")
        else:
            st.warning("🟡 API Checking...")
            st.caption("Render free tier: 30–60s cold start")
    
    # User / Role — collapsible
    with st.sidebar.expander("👤 User", expanded=False):
        if app == "public":
            st.caption("**Role:** Farmer")
            st.caption("**Access:** Public — No login required")
        elif app == "government":
            st.caption("**Role:** Government Official")
            st.caption("**Department:** Ministry of Agriculture")
            st.caption("**Access:** Administrative tools enabled")
        else:
            st.caption("**Role:** Analyst / Admin")
            st.caption("**Access:** Full platform access")
    
    # Session controls — collapsible
    with st.sidebar.expander("⚙️ Session", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("🗑️ Reset", use_container_width=True):
                for k in list(st.session_state.keys()):
                    if k not in ("app_type", "app_mode"):
                        del st.session_state[k]
                st.rerun()


def render_sidebar():
    """Main sidebar renderer — clean and scannable."""
    if "app_type" not in st.session_state:
        st.session_state["app_type"] = "main"
    
    # Sidebar CSS — minimal
    st.sidebar.markdown(
        """
        <style>
        [data-testid="stSidebar"] button[kind="secondary"] {
            background: transparent; border: 1px solid rgba(250,250,250,0.1);
            text-align: left; justify-content: flex-start; padding: 0.5rem 0.75rem;
        }
        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            background: rgba(250,250,250,0.05); border-color: rgba(250,250,250,0.2);
        }
        [data-testid="stSidebar"] button[kind="primary"] {
            background: rgba(46,125,50,0.2); border: 1px solid #2e7d32;
            text-align: left; justify-content: flex-start;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    _render_header()
    _render_navigation(_get_current_app())
    st.sidebar.divider()
    _render_county_selector()
    st.sidebar.divider()
    _render_collapsible_sections()


def require_auth() -> bool:
    return True


def get_current_mode() -> AppMode:
    return _get_current_app()


def get_quick_county() -> str:
    return st.session_state.get("quick_county", "Turkana")