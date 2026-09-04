import os
import requests
import streamlit as st

# Page Configuration
st.set_page_config(page_title="PDF Report Generator", page_icon="📄", layout="wide")

# Backend Configuration
BACKEND_URL = st.secrets.get("BACKEND_URL") or os.getenv("BACKEND_URL", "https://agrishield-dnao.onrender.com")

st.title("📄 Export Agricultural Risk Reports")
st.write("Generate, view, and download standardized PDF reports containing ML risk scores and Gria AI insights.")

# -----------------------------------------------------------------------------
# SECTION 1: CREATE NEW REPORT
# -----------------------------------------------------------------------------
st.subheader("1. Generate New County Report")

col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    selected_county = st.selectbox("Select Target County", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])

with col2:
    report_type = st.selectbox("Report Type", ["Crop Yield Risk", "Livestock Forage Risk", "Comprehensive Assessment"])

with col3:
    is_detailed = st.checkbox("Detailed View", value=True)

if st.button("Generate Report", type="primary"):
    with st.spinner("Compiling PDF report via FastAPI backend... (Cold starts may take ~30s)"):
        try:
            payload = {
                "county_name": selected_county,
                "report_type": report_type,
                "detailed": is_detailed
            }
            
            # Endpoint: POST /api/v1/reports/create
            response = requests.post(
                f"{BACKEND_URL}/api/v1/reports/create",
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                res_data = response.json()
                report_id = res_data.get("report_id") or res_data.get("id")
                st.success(f"✅ Report generated successfully! (ID: {report_id})")
            else:
                st.error(f"Failed to generate report. Backend returned status code {response.status_code}")
        
        except Exception as e:
            st.error(f"Could not connect to report generation endpoint: {e}")

st.divider()

# -----------------------------------------------------------------------------
# SECTION 2: VIEW & DOWNLOAD EXISTING REPORTS
# -----------------------------------------------------------------------------
st.subheader("2. Available Reports Library")

try:
    # Endpoint: GET /api/v1/reports/
    list_res = requests.get(f"{BACKEND_URL}/api/v1/reports/", timeout=10)
    
    if list_res.status_code == 200:
        reports_list = list_res.json()
        
        if reports_list:
            st.dataframe(reports_list, use_container_width=True)
            
            # Select specific report ID for download
            st.subheader("3. Download PDF Artifact")
            report_id_input = st.text_input("Enter Report ID to Download", placeholder="e.g., rpt_12345")
            
            if st.button("Download PDF"):
                if report_id_input:
                    with st.spinner("Fetching PDF document binary stream..."):
                        # Endpoint: GET /api/v1/reports/{report_id}
                        pdf_res = requests.get(f"{BACKEND_URL}/api/v1/reports/{report_id_input}", timeout=15)
                        
                        if pdf_res.status_code == 200:
                            st.download_button(
                                label="💾 Save PDF to Disk",
                                data=pdf_res.content,
                                file_name=f"AgriShield_Report_{selected_county}_{report_id_input}.pdf",
                                mime="application/pdf"
                            )
                        else:
                            st.error(f"Could not retrieve PDF file. Status: {pdf_res.status_code}")
                else:
                    st.warning("Please enter a valid Report ID.")
        else:
            st.info("No reports found in the library. Generate one using the form above.")
            
    else:
        st.warning(f"Could not fetch reports list (Status: {list_res.status_code}). Render service may be initializing.")

except Exception as e:
    st.info("Reports library endpoint currently initializing or unreachable.")
