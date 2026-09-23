"""Export tools for government data."""
import streamlit as st
from shared.api_client import get_batch_predictions, get_history
from shared.export_service import to_csv, to_excel
import io


def render_export_tools():
    """Render data export controls."""
    st.subheader("📤 Export Data")

    export_type = st.radio("Export Type", ["CSV", "Excel"], horizontal=True)
    data_choice = st.radio("Data to Export", [
        "Current Predictions",
        "Historical Trends",
        "All County Data",
    ])

    if st.button("Generate Export", type="primary"):
        try:
            if data_choice == "Current Predictions":
                batch = get_batch_predictions()
                counties = batch.get("counties", [])
                if export_type == "CSV":
                    data = to_csv(counties)
                    fname = "agrishield_predictions.csv"
                else:
                    data = to_excel(counties)
                    fname = "agrishield_predictions.xlsx"
            else:
                st.info("Select data source and click Generate.")
                return

            if counties:
                st.download_button(
                    label="💾 Download Export",
                    data=data,
                    file_name=fname,
                    mime="text/csv" if export_type == "CSV" else "application/vnd.openxmlformats",
                )
        except Exception as e:
            st.error(f"Export failed: {e}")
