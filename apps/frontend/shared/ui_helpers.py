"""Reusable UI helpers for the AgriShield frontend."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

RISK_COLORS = {
    "SAFE": "#2e7d32",
    "MODERATE": "#f9a825",
    "HIGH": "#ef6c00",
    "CRITICAL": "#d32f2f",
}


def risk_label_from_score(score: Any) -> str:
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        return "SAFE"
    if numeric < 25:
        return "SAFE"
    if numeric < 50:
        return "MODERATE"
    if numeric < 75:
        return "HIGH"
    return "CRITICAL"


def render_metric(title: str, value: Any, color: str = "#2e7d32") -> None:
    st.markdown(
        f"""
        <div style="padding: 0.9rem 1rem; border: 1px solid rgba(255,255,255,0.08); border-radius: 0.9rem; background: rgba(255,255,255,0.02);">
            <div style="color: #9aa5b1; font-size: 0.8rem;">{title}</div>
            <div style="color: {color}; font-weight: 700; font-size: 1.7rem; margin-top: 0.2rem;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def summary_badge(level: str | None) -> str:
    label = str(level or "SAFE").upper()
    color = RISK_COLORS.get(label, "#2e7d32")
    return f"<span style='background:{color}; color:white; padding:0.25rem 0.6rem; border-radius:999px; font-weight:700; font-size:0.8rem;'>{label}</span>"


def chart_or_empty(df: pd.DataFrame, key: str) -> None:
    if df.empty:
        st.info("No data available for this view.")
        return
    st.line_chart(df, x=df.columns[0], y=df.columns[1] if len(df.columns) > 1 else None, width="stretch")


def ensure_session_defaults() -> None:
    defaults = {
        "selected_county": "Bungoma",
        "selected_region": "Rift Valley",
        "report_type": "combined",
        "gria_history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
