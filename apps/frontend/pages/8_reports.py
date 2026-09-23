"""Report management page."""
import streamlit as st

from components.api_client import create_report, list_reports, download_report_pdf
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Report Manager", page_icon="📑", layout="wide")

render_sidebar()

st.title("📑 Report Manager")
st.write("Manage and download agricultural risk reports.")

st.subheader("1. Generate New Report")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    selected_county = st.selectbox("Select County", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])
with col2:
    report_type = st.selectbox("Report Type", ["Crop Yield Risk", "Livestock Forage Risk", "Comprehensive Assessment"])
with col3:
    is_detailed = st.checkbox("Detailed", value=True)

if st.button("Generate Report", type="primary"):
    with st.spinner("Generating report..."):
        try:
            result = create_report(selected_county, report_type, is_detailed)
            report_id = result.get("id")
            st.success(f"✅ Report generated! ID: {report_id}")
        except Exception as e:
            st.error(f"Report generation failed: {e}")

st.divider()

st.subheader("2. Report Library")

report_type_map = {
    "All": None,
    "Crop Yield Risk": "Crop Yield Risk",
    "Livestock Forage Risk": "Livestock Forage Risk",
    "Comprehensive Assessment": "Comprehensive Assessment",
}
filter_choice = st.selectbox("Filter by type", list(report_type_map.keys()))

if st.button("Refresh Reports", use_container_width=True):
    st.session_state["refresh_reports"] = True

try:
    reports_data = list_reports(report_type=report_type_map[filter_choice])
    reports = reports_data.get("reports", [])
except Exception:
    reports = []
    st.warning("Could not load reports. Backend may be initializing.")

if reports:
    import pandas as pd
    st.dataframe(pd.DataFrame(reports), use_container_width=True)

    st.divider()
    st.subheader("3. Download Report PDF")
    report_ids = [str(r.get("id")) for r in reports]
    selected_id = st.selectbox("Select Report ID", report_ids)

    if selected_id and st.button("Download PDF", type="primary"):
        with st.spinner("Fetching PDF..."):
            try:
                pdf_bytes = download_report_pdf(selected_id)
                st.download_button(
                    label="💾 Save PDF to Disk",
                    data=pdf_bytes,
                    file_name=f"AgriShield_Report_{selected_id}.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                st.error(f"Download failed: {e}")
else:
    st.info("No reports yet. Generate one above.")

st.divider()
st.caption("Reports include ML risk scores, Gria AI insights, and actionable recommendations.")
