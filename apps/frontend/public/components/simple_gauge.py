"""Simple gauge — compact risk indicator for public pages."""
import streamlit as st
from typing import Optional


def simple_gauge(risk_score: Optional[float] = None, risk_level: Optional[str] = None,
                  title: str = "Risk Level", size: str = "medium"):
    """Display a simple gauge with score and level."""
    if risk_score is None:
        st.warning(f"{title}: No data")
        return

    size_map = {"small": 0.6, "medium": 0.8, "large": 1.0}
    width = size_map.get(size, 0.8)

    col1, col2 = st.columns([1, 2])
    with col1:
        if risk_score >= 75:
            color = "#d32f2f"
            emoji = "🔴"
        elif risk_score >= 50:
            color = "#f57c00"
            emoji = "🟠"
        elif risk_score >= 25:
            color = "#fbc02d"
            emoji = "🟡"
        else:
            color = "#2e7d32"
            emoji = "🟢"

        st.markdown(f"## {emoji} **{risk_level or 'UNKNOWN'}**")

    with col2:
        st.markdown(f"**Risk Score: {risk_score}%**")
        st.progress(min(max(risk_score / 100, 0.0), 1.0))
