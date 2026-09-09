import os
import requests
import streamlit as st

BACKEND_URL = st.secrets.get("BACKEND_URL") or os.getenv(
    "BACKEND_URL",
    "https://agrishield-dnao.onrender.com"
)
st.set_page_config(
    page_title="AgriShield",
    page_icon="🌾",
    layout="centered"
)
st.title("🌾 AgriShield")
st.subheader("Agricultural Risk Intelligence System")
st.write(
    "Select a county and focus area to generate an agricultural risk prediction."
)
selected_county = st.selectbox(
    "Select County",
    [
        "Turkana",
        "Kajiado",
        "Uasin Gishu",
        "Nakuru",
        "Kilifi"
    ]
)
focus_area = st.radio(
    "Select Focus",
    ["crops", "livestock"],
    horizontal=True
)
if st.button("Generate Risk Prediction", type="primary"):
    payload = {
        "county_name": selected_county,
        "focus": focus_area
    }
    with st.spinner(
        "Fetching prediction... Render may take up to 30 seconds if the server is waking up."
    ):
        try:
            response = requests.post(
                f"{BACKEND_URL}/api/v1/predictions/crop-yield",
                json=payload,
                timeout=60
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    st.error("Backend returned an invalid JSON response.")
                    st.code(response.text)
                    st.stop()
                # Risk score
                risk_score = data.get("risk_score", "N/A")
                # Risk level
                risk_level = data.get(
                    "risk_level",
                    "UNKNOWN"
                )
                # Main driver
                main_driver = data.get(
                    "main_driver",
                    "N/A"
                )
                # Recommendation
                recommendation = data.get(
                    "recommendation",
                    "N/A"
                )
                st.success("Prediction generated successfully!")
                st.metric(
                    label="Risk Score",
                    value=risk_score
                )
                st.subheader(
                    f"Risk Level: {risk_level}"
                )
                st.write(
                    f"**Main Driver:** {main_driver}"
                )
                st.info(
                    f"**Recommendation:** {recommendation}"
                )
                # Optional: show raw response
                with st.expander("View prediction data"):
                    st.json(data)
            else:
                st.error(
                    f"Backend returned status code {response.status_code}"
                )
                # Try to display backend error
                try:
                    error_data = response.json()
                    st.json(error_data)
                except ValueError:
                    st.code(response.text)
        except requests.exceptions.Timeout:
            st.error(
                "The backend took too long to respond. "
                "The Render server may still be waking up."
            )
        except requests.exceptions.ConnectionError:
            st.error(
                "Could not connect to the AgriShield backend."
            )
            st.write(
                f"Backend URL: {BACKEND_URL}"
            )
        except Exception as e:
            st.error(
                f"Unexpected error: {e}"
            )
