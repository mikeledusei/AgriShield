"""Quick Actions — dashboard widget for public portal."""
import streamlit as st


def render_quick_actions():
    """Display quick action buttons for public users."""
    st.subheader("⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🌾 Check County Risk", use_container_width=True):
            st.switch_page("public/pages/2_my_county.py")
    with col2:
        if st.button("🤖 Ask Gria", use_container_width=True):
            st.switch_page("public/pages/3_ask_gria.py")
    with col3:
        if st.button("📋 Quick Report", use_container_width=True):
            st.switch_page("public/pages/4_quick_report.py")

    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("🌱 Farming Tips", use_container_width=True):
            st.switch_page("public/pages/5_farming_tips.py")
    with col5:
        if st.button("📷 Upload Photo", use_container_width=True):
            st.switch_page("public/pages/6_upload_photo.py")
    with col6:
        if st.button("🏠 Home", use_container_width=True):
            st.switch_page("public/pages/1_home.py")
