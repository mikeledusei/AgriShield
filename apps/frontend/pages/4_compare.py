"""Compare counties side by side."""
import streamlit as st

from components.api_client import compare_counties
from shared.sidebar import render_sidebar
from components.charts import county_comparison_chart
from components.gauges import risk_gauge, metric_row

st.set_page_config(page_title="Compare Counties", page_icon="⚖️", layout="wide")

render_sidebar()
st.title("⚖️ County Comparison")
st.write("Compare risk levels across multiple Kenyan counties.")

county_options = ["Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi",
                  "Meru", "Kisumu", "Kitui", "Machakos", "Makueni"]

selected = st.multiselect(
    "Select counties to compare (2–10)",
    county_options,
    default=["Turkana", "Nakuru"],
    max_selections=10,
)

if st.button("Compare Counties", type="primary", use_container_width=True):
    if len(selected) < 2:
        st.warning("Please select at least 2 counties.")
    else:
        with st.spinner("Comparing counties..."):
            try:
                result = compare_counties(selected)
                counties = result.get("counties", [])

                st.subheader("Comparison Results")
                highest = result.get("highest_risk", {})
                lowest = result.get("lowest_risk", {})
                metric_row({
                    "Highest Risk": f"{highest.get('county_name', 'N/A')} ({highest.get('risk_score', 0)}%)",
                    "Lowest Risk": f"{lowest.get('county_name', 'N/A')} ({lowest.get('risk_score', 0)}%)",
                    "Counties Compared": len(counties),
                })

                st.divider()
                county_comparison_chart(counties)

                st.divider()
                st.subheader("County Details")
                for c in counties:
                    with st.expander(f"📍 {c.get('county_name', 'Unknown')} — {c.get('risk_level', 'N/A')}"):
                        risk_gauge(c.get("risk_score"), c.get("risk_level"), title="Risk Score")
                        st.write(f"**Driver:** {c.get('main_driver', 'N/A')}")
                        st.write(f"**Recommendation:** {c.get('recommendation', 'N/A')}")
                        st.caption(f"Model: {c.get('model_used', 'N/A')} | Month: {c.get('month', 'N/A')}")
            except Exception as e:
                st.error(f"Comparison failed: {e}")
