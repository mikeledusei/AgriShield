"""PDF report generation helper."""
import streamlit as st
from shared.api_client import create_report, download_report_pdf


def render_pdf_report(county_name: str = None, report_type: str = "combined"):
    """Render a PDF report generation and download UI."""
    if not county_name:
        st.warning("No county selected for report generation.")
        return None

    st.subheader("📄 PDF Report")

    type_map = {
        "Crop Yield Risk": "crop",
        "Livestock Forage Risk": "livestock",
        "Comprehensive Assessment": "comprehensive",
    }
    rt = type_map.get(report_type, report_type)

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_report_type = st.selectbox("Report Type",
            ["Crop Yield Risk", "Livestock Forage Risk", "Comprehensive Assessment"])
    with col2:
        detailed = st.checkbox("Detailed", value=True)

    if st.button("Generate PDF Report", type="primary"):
        with st.spinner("Generating report..."):
            try:
                result = create_report(county_name, selected_report_type, detailed)
                report_id = result.get("id")
                st.success(f"✅ Report generated! (ID: {report_id})")

                with st.spinner("Downloading PDF..."):
                    pdf_bytes = download_report_pdf(report_id)
                    st.download_button(
                        label="💾 Download PDF",
                        data=pdf_bytes,
                        file_name=f"AgriShield_Report_{report_id}.pdf",
                        mime="application/pdf",
                    )
            except Exception as e:
                st.error(f"Report generation failed: {e}")
        return result
    return None
