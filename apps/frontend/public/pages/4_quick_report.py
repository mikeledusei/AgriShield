"""Quick Report — generate a fast county risk report for public users."""
import streamlit as st

from shared.api_client import predict, create_report, download_report_pdf
from shared.gauges import risk_gauge
from shared.sidebar import render_sidebar

st.set_page_config(page_title="Quick Report", page_icon="📋", layout="wide")
render_sidebar()

st.title("📋 Quick Report")
st.write("Get a quick risk assessment for any Kenyan county. Generate and download a PDF report instantly.")

county = st.selectbox("Select County", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])
report_type = st.selectbox("Report Type", ["Crop Yield Risk", "Livestock Forage Risk", "Comprehensive Assessment"])
detailed = st.checkbox("Detailed View", value=True)

st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Risk Preview")
    try:
        data = predict(county)
        risk_gauge(data.get("risk_score"), data.get("risk_level"), title="Current Risk")
        st.write(f"**Main Driver:** {data.get('main_driver', 'N/A')}")
        st.write(f"**Recommendation:** {data.get('recommendation', 'N/A')}")
    except Exception as e:
        st.error(f"Failed to load prediction: {e}")

with col2:
    st.subheader("Generate Report")
    if st.button("Generate Quick Report", type="primary"):
        with st.spinner("Generating report..."):
            try:
                result = create_report(county, report_type, detailed)
                report_id = result.get("id")
                st.success(f"✅ Report generated! (ID: {report_id})")

                if st.button("📥 Download PDF", type="primary"):
                    with st.spinner("Preparing PDF..."):
                        try:
                            pdf_bytes = download_report_pdf(report_id)
                            st.download_button(
                                label="💾 Save PDF",
                                data=pdf_bytes,
                                file_name=f"AgriShield_Report_{report_id}.pdf",
                                mime="application/pdf",
                            )
                        except Exception as e:
                            st.error(f"Download failed: {e}")
            except Exception as e:
                st.error(f"Report generation failed: {e}")
