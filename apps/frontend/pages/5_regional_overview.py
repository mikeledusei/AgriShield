import streamlit as st
import requests

BACKEND_URL =import os
BACKEND_URL = st.secrets.get("BACKEND_URL") or os.getenv("BACKEND_URL", "https://agrishield-dnao.onrender.com") 
st.set_page_config(page_title="PDF Report Generator", page_icon="📄")

st.title("📄 Export Agricultural Risk Reports")
st.write("Generate and download standardized PDF reports containing ML risk scores and Gria AI insights.")

county = st.selectbox("Select County for Report", ["Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"])

if st.button("Generate PDF Report"):
    with st.spinner("Compiling PDF report..."):
        try:
            # Request PDF report from FastAPI backend
            response = requests.get(f"{BACKEND_URL}/reports/download/{county}")
            
            if response.status_code == 200:
                st.download_button(
                    label="📥 Download PDF Document",
                    data=response.content,
                    file_name=f"AgriShield_Report_{county}.pdf",
                    mime="application/pdf"
                )
                st.success("Report generated successfully!")
            else:
                st.error("Could not generate report from backend.")
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")
