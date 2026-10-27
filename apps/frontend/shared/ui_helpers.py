"""Reusable, WCAG 2.1 AA accessible UI components and helpers for the AgriShield frontend."""

from __future__ import annotations

import html
import re
from typing import Any

import pandas as pd
import streamlit as st

# High-contrast semantic risk colors (WCAG 2.1 AA compliant on dark & light surfaces)
RISK_COLORS = {
    "SAFE": "#22c55e",
    "MODERATE": "#facc15",
    "HIGH": "#fb923c",
    "CRITICAL": "#f87171",
}

RISK_BADGE_BG = {
    "SAFE": "#166534",
    "MODERATE": "#854d0e",
    "HIGH": "#9a3412",
    "CRITICAL": "#991b1b",
}

MODEL_LABELS = {
    "lightgbm_v1": "LightGBM Champion v1",
    "xgboost_v1": "XGBoost v1",
    "rule_based": "Rule-Based Fallback",
}


def risk_label_from_score(score: Any) -> str:
    """Map numeric risk score [0, 100] to canonical risk level."""
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


def format_model_label(model_used: str | None) -> str:
    """Convert backend model_used identifier to a human-readable badge label."""
    if not model_used:
        return "LightGBM Champion v1"
    return MODEL_LABELS.get(str(model_used).strip(), str(model_used))


def summary_badge(level: str | None) -> str:
    """Return an accessible HTML badge for a risk level."""
    label = str(level or "SAFE").upper()
    bg = RISK_BADGE_BG.get(label, "#166534")
    return (
        f"<span role='status' aria-label='Risk level {html.escape(label)}' "
        f"style='background:{bg}; color:#ffffff; padding:0.25rem 0.65rem; "
        f"border-radius:999px; font-weight:700; font-size:0.78rem; letter-spacing:0.04em;'>"
        f"{html.escape(label)}</span>"
    )


def render_metric(
    title: str,
    value: Any,
    color: str = "#22c55e",
    subtitle: str | None = None,
) -> None:
    """Render an accessible, responsive KPI metric card."""
    safe_title = html.escape(str(title))
    safe_val = html.escape(str(value))
    sub_html = (
        f"<div style='color:#cbd5e1; font-size:0.76rem; margin-top:0.25rem;'>{html.escape(subtitle)}</div>"
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div class="agri-kpi-card" role="region" aria-label="{safe_title}">
            <div class="agri-kpi-title">{safe_title}</div>
            <div class="agri-kpi-value" style="color: {color};">{safe_val}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_error_state(title: str, detail: str, retry_key: str | None = None) -> None:
    """Render a clear, accessible error banner with optional retry button."""
    safe_title = html.escape(title)
    safe_detail = html.escape(detail)
    st.markdown(
        f"""
        <div role="alert" style="padding:1rem 1.2rem; border-radius:14px; background:rgba(153,27,27,0.18); border:1px solid rgba(248,113,113,0.45); margin:0.6rem 0;">
            <div style="font-weight:700; color:#fecaca; font-size:0.95rem;">⚠️ {safe_title}</div>
            <div style="color:#fee2e2; font-size:0.86rem; margin-top:0.25rem;">{safe_detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if retry_key and st.button("🔄 Retry Connection", key=retry_key):
        st.cache_data.clear()
        st.rerun()


def render_empty_state(title: str, message: str, icon: str = "🌾") -> None:
    """Render a consistent empty-state card."""
    st.markdown(
        f"""
        <div role="status" style="padding:1.4rem; border-radius:16px; background:rgba(15,23,42,0.55); border:1px dashed rgba(148,163,184,0.3); text-align:center; margin:0.6rem 0;">
            <div style="font-size:1.8rem; margin-bottom:0.3rem;" aria-hidden="true">{html.escape(icon)}</div>
            <div style="font-weight:700; color:#f1f5f9; font-size:1rem;">{html.escape(title)}</div>
            <div style="color:#cbd5e1; font-size:0.88rem; margin-top:0.25rem;">{html.escape(message)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_markdown_to_html(content: str) -> str:
    """Safely convert Markdown bold and bullet lines into HTML for Gria chat bubbles."""
    escaped = html.escape(str(content or ""))
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    lines = escaped.splitlines()
    out_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            out_lines.append(f"• {stripped[2:]}")
        else:
            out_lines.append(line)
    return "<br>".join(out_lines)


def chart_or_empty(df: pd.DataFrame, key: str) -> None:
    """Render a line chart or a clean empty state if DataFrame is empty."""
    if df.empty:
        render_empty_state("No Chart Data", "No time-series records are available for this selection.", "📉")
        return
    st.line_chart(
        df,
        x=df.columns[0],
        y=df.columns[1] if len(df.columns) > 1 else None,
        use_container_width=True,
    )


def ensure_session_defaults() -> None:
    """Initialize required Streamlit session state keys."""
    defaults = {
        "selected_county": "Bungoma",
        "selected_region": "Rift Valley",
        "selected_focus": "combined",
        "report_type": "combined",
        "gria_history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
