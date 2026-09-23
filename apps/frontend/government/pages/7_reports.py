"""Reports — government report management."""
import streamlit as st
import pandas as pd
from shared.api_client import create_report, list_reports, download_report_pdf
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Reports", page_icon="📑", layout="wide")
render_sidebar()

st.title("📑 Government Report Management")
st.write("Generate, manage, and download official agricultural risk reports.")

st.subheader("1. Generate New Report")
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    selected_county = st.selectbox("Select Target County",
        ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])
with col2:
    report_type = st.selectbox("Report Type",
        ["Crop Yield Risk", "Livestock Forage Risk", "Comprehensive Assessment"])
with col3:
    is_detailed = st.checkbox("Detailed View", value=True)

if st.button("Generate Report", type="primary"):
    with st.spinner("Compiling report..."):
        try:
            result = create_report(selected_county, report_type, is_detailed)
            report_id = result.get("id")
            st.success(f"✅ Report generated! (ID: {report_id})")
            st.session_state["last_report_id"] = report_id
        except Exception as e:
            st.error(f"Report generation failed: {e}")

st.divider()
st.subheader("2. Report Library")
filter_choice = st.selectbox("Filter by type", ["All", "Crop Yield Risk", "Livestock Forage Risk", "Comprehensive Assessment"])

try:
    reports_data = list_reports()
    reports_list = reports_data.get("reports", []) if reports_data else []

    if reports_list:
        if filter_choice != "All":
            type_map = {
                "Crop Yield Risk": "crop",
                "Livestock Forage Risk": "livestock",
                "Comprehensive Assessment": "comprehensive",
            }
            reports_list = [r for r in reports_list if r.get("report_type") == type_map.get(filter_choice)]

        st.dataframe(pd.DataFrame(reports_list), use_container_width=True)

        st.subheader("3. Download PDF")
        report_ids = [str(r.get("id")) for r in reports_list]
        selected_id = st.selectbox("Select Report ID", report_ids)

        if st.button("Prepare PDF Download"):
            if selected_id:
                with st.spinner("Fetching PDF..."):
                    try:
                        pdf_bytes = download_report_pdf(selected_id)
                        st.download_button(
                            label="💾 Save PDF",
                            data=pdf_bytes,
                            file_name=f"AgriShield_Report_{selected_id}.pdf",
                            mime="application/pdf",
                        )
                    except Exception as e:
                        st.error(f"Could not retrieve PDF: {e}")
    else:
        st.info("No reports found. Generate one above.")
except Exception as e:
    st.warning(f"Could not load reports: {e}")
