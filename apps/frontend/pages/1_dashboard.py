import os
import requests
import streamlit as st

BACKEND_URL = st.secrets.get("BACKEND_URL") or os.getenv(
    "BACKEND_URL", "https://agrishield-dnao.onrender.com"
)

st.title("🌾 AgriShield: Agricultural Risk Intelligence")

selected_county = st.selectbox(
    "Select County", ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi"]
)
focus_area = st.radio("Select Focus", ["crops", "livestock"])

if st.button("Generate Risk Prediction"):
    with st.spinner(
        "Fetching prediction from Render... (Note: Cold start may take ~30s)"
    ):
        try:
            payload = {"county_name": selected_county, "focus": focus_area}

            # Updated to include /api/v1/
            response = requests.post(
                f"{BACKEND_URL}/api/v1/predictions/crop-yield", json=payload
            )

            if response.status_code == 200:
                data = response.json()

                # Render backend fields
                st.metric(
                    label="Risk Score", value=data.get("risk_score", "N/A")
                )
                st.subheader(
                    f"Risk Level: {data.get('risk_level', 'UNKNOWN')}"
                )
                st.write(f"**Main Driver:** {data.get('main_driver', 'N/A')}")
                st.info(
                    f"**Recommendation:** {data.get('recommendation', 'N/A')}"
                )
            else:
                st.error(
                    f"Backend returned status code {response.status_code}"
                )

        except Exception as e:
            st.error(f"Cannot connect to backend server: {e}")
