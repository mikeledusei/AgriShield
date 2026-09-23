"""File uploader component with analysis."""
import streamlit as st

from shared.api_client import upload_and_analyze

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"}


def render_uploader(title: str = "Upload File for Analysis"):
    """Render a file uploader with analysis."""
    st.subheader(title)

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=sorted(ALLOWED_EXTENSIONS),
        help="Supported: CSV, Excel, PDF, Word, PNG, JPG",
    )

    if uploaded_file is not None:
        file_name = uploaded_file.name
        file_ext = file_name.rsplit(".", 1)[-1].lower()

        file_bytes = uploaded_file.read()

        st.write(f"**File:** {file_name} ({file_ext.upper()})")
        st.write(f"**Size:** {len(file_bytes):,} bytes")

        if st.button("Analyze File", type="primary"):
            with st.spinner("Analyzing file..."):
                try:
                    result = upload_and_analyze(file_bytes, file_name)
                    st.success("✅ Analysis complete!")
                    _display_analysis_result(result)
                except Exception as e:
                    st.error(f"Analysis failed: {e}")


def _display_analysis_result(result: dict):
    """Display analysis results."""
    st.divider()

    extracted = result.get("extracted_data")
    if extracted:
        st.markdown("**Extracted Features:**")
        for key, value in extracted.items():
            if key == "county_name":
                st.write(f"  📍 County: **{value}**")
            elif isinstance(value, float):
                st.write(f"  📊 {key}: {value:.4f}")
            else:
                st.write(f"  📊 {key}: {value}")

    if "risk_score" in result:
        st.write(f"**Risk Score:** {result['risk_score']}%")
        st.write(f"**Risk Level:** {result['risk_level']}")

    if "gria_summary" in result:
        st.info(f"**Gria Summary:** {result['gria_summary']}")

    st.session_state["last_upload_result"] = result
