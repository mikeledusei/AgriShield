"""Reusable gauge/risk indicator components."""
import streamlit as st
from typing import Optional


def risk_gauge(risk_score: Optional[float] = None, risk_level: Optional[str] = None,
               title: str = "Risk Score", size: str = "large"):
    """Display a risk gauge with score and level."""
    if risk_score is None:
        st.warning(f"{title}: No data available")
        return

    if size == "large":
        label = ":red[●]" if risk_score >= 75 else ":orange[●]" if risk_score >= 50 else ":green[●]"
    else:
        label = ""

    st.markdown(f"**{title}:** {label} **{risk_score}%** ({risk_level or 'N/A'})")

    if risk_score is not None:
        st.progress(min(max(risk_score / 100, 0.0), 1.0))


def risk_badge(risk_level: str, show_text: bool = True) -> str:
    """Display a colored badge for risk level."""
    colors = {
        "SAFE": "🟢",
        "MODERATE": "🟠",
        "HIGH": "🔴",
        "CRITICAL": "🔴",
        "UNKNOWN": "⚪",
    }
    icon = colors.get(risk_level.upper(), "⚪")
    if show_text:
        return f"{icon} **{risk_level}**"
    return icon


def metric_row(metrics: dict):
    """Display metrics in a row."""
    cols = st.columns(len(metrics))
    for i, (label, value) in enumerate(metrics.items()):
        cols[i].metric(label=label, value=value)


def status_card(title: str, status: str, details: str = ""):
    """Display a status card."""
    if "critical" in status.lower() or "error" in status.lower():
        st.error(f"**{title}:** {status}")
    elif "warning" in status.lower() or "high" in status.lower():
        st.warning(f"**{title}:** {status}")
    elif "ok" in status.lower() or "safe" in status.lower() or "success" in status.lower():
        st.success(f"**{title}:** {status}")
    else:
        st.info(f"**{title}:** {status}")
    if details:
        st.caption(details)
