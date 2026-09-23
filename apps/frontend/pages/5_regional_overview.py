"""Export Agricultural Risk Reports - report generation page."""
import streamlit as st

from shared.api_client import create_report, list_reports, download_report_pdf, predict
from shared.sidebar import render_sidebar
from shared.gauges import risk_gauge

st.set_page_config(page_title="Regional Overview & Reports", page_icon="📄", layout="wide")

render_sidebar()

st.title("📄 Export Agricultural Risk Reports")
st.write("Generate, view, and download standardized PDF reports containing ML risk scores and Gria AI insights.")

st.subheader("1. Generate New County Report")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    selected_county = st.selectbox(
        "Select Target County",
        ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"],
    )
with col2:
    report_type = st.selectbox(
        "Report Type",
        ["Crop Yield Risk", "Livestock Forage Risk", "Comprehensive Assessment"],
    )
with col3:
    is_detailed = st.checkbox("Detailed View", value=True)

if st.button("Generate Report", type="primary"):
    with st.spinner("Compiling report via FastAPI backend..."):
        try:
            result = create_report(selected_county, report_type, is_detailed)
            report_id = result.get("id")
            st.success(f"✅ Report generated successfully! (ID: {report_id})")
            st.session_state["last_report_id"] = report_id
        except Exception as e:
            st.error(f"Report generation failed: {e}")

st.divider()

st.subheader("2. Current Risk Preview")
try:
    data = predict(selected_county)
    risk_gauge(data.get("risk_score"), data.get("risk_level"), title="Current Risk Score")
except Exception:
    st.caption("Backend may be initializing. Try again shortly.")

st.divider()

st.subheader("3. Available Reports Library")
try:
    list_res = list_reports()
    reports_list = list_res.get("reports", []) if list_res else []

    if reports_list:
        import pandas as pd
        df = pd.DataFrame(reports_list)
        st.dataframe(df, use_container_width=True)

        st.subheader("4. Download PDF")
        report_ids = [str(r.get("id")) for r in reports_list]
        selected_id = st.selectbox("Select Report ID", report_ids)

        if st.button("Prepare PDF Download"):
            if selected_id:
                with st.spinner("Fetching PDF document..."):
                    try:
                        pdf_bytes = download_report_pdf(selected_id)
                        st.download_button(
                            label="💾 Save PDF to Disk",
                            data=pdf_bytes,
                            file_name=f"AgriShield_Report_{selected_id}.pdf",
                            mime="application/pdf",
                        )
                    except Exception as e:
                        st.error(f"Could not retrieve PDF file: {e}")
    else:
        st.info("No reports found in the library. Generate one using the form above.")
except Exception:
    st.info("Reports library endpoint currently initializing or unreachable.")
