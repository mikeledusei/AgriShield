"""Upload Photo — satellite/field photo upload for NDVI estimation."""
import streamlit as st

from shared.sidebar import render_sidebar
from shared.api_client import upload_and_analyze
from shared.gauges import risk_gauge

st.set_page_config(page_title="Upload Photo", page_icon="📷", layout="wide")
render_sidebar()

st.title("📷 Upload Photo for Analysis")
st.write("Upload a satellite or field photo to estimate vegetation health (NDVI) and get risk assessment.")

st.divider()

uploaded_file = st.file_uploader(
    "Choose an image",
    type=["png", "jpg", "jpeg"],
    help="Supported: PNG, JPG, JPEG",
)

if uploaded_file is not None:
    file_name = uploaded_file.name
    file_bytes = uploaded_file.read()

    st.write(f"**File:** {file_name}")
    st.write(f"**Size:** {len(file_bytes):,} bytes")
    st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)

    if st.button("Analyze Photo", type="primary"):
        with st.spinner("Analyzing your photo..."):
            try:
                result = upload_and_analyze(file_bytes, file_name)
                st.success("✅ Analysis complete!")

                if "risk_score" in result:
                    risk_gauge(result.get("risk_score"), result.get("risk_level"), title="Estimated Risk")

                if "gria_summary" in result:
                    st.info(f"**Gria Summary:** {result['gria_summary']}")

                extracted = result.get("extracted_data", {})
                if extracted:
                    st.markdown("**Extracted Features:**")
                    for key, value in extracted.items():
                        if isinstance(value, float):
                            st.write(f"  📊 {key}: {value:.4f}")
                        else:
                            st.write(f"  📊 {key}: {value}")
            except Exception as e:
                st.error(f"Analysis failed: {e}")

st.divider()
st.markdown("""
### 📸 Photo Guidelines
- Use high-resolution satellite imagery or drone photos
- Ensure the area of interest is clearly visible
- Images with more vegetation cover provide better NDVI estimates
- For best results, capture during daylight with minimal cloud cover
""")
