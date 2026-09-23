"""Chart components for AgriShield."""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import streamlit as st
from typing import Optional


def risk_distribution_chart(predictions: list, show: bool = True):
    """Show a bar chart of risk distribution."""
    if not predictions:
        if show:
            st.info("No prediction data available.")
        return None

    df = pd.DataFrame(predictions)
    if "risk_level" not in df.columns:
        if show:
            st.info("No risk level data available.")
        return None

    level_counts = df["risk_level"].value_counts().reset_index()
    level_counts.columns = ["Risk Level", "Count"]
    level_order = ["SAFE", "MODERATE", "HIGH", "CRITICAL"]
    level_counts["Risk Level"] = pd.Categorical(level_counts["Risk Level"], categories=level_order, ordered=True)
    level_counts = level_counts.sort_values("Risk Level")

    fig = px.bar(
        level_counts, x="Risk Level", y="Count",
        color="Risk Level",
        color_discrete_map={
            "SAFE": "#2e7d32",
            "MODERATE": "#fbc02d",
            "HIGH": "#f57c00",
            "CRITICAL": "#d32f2f",
        },
        title="Risk Distribution by Level",
    )
    fig.update_layout(template="plotly_white", height=400)
    if show:
        st.plotly_chart(fig, use_container_width=True)
    return fig


def risk_score_trend_chart(trend_data: list, county_name: str = "", show: bool = True):
    """Show a line chart of risk scores over time."""
    if not trend_data:
        if show:
            st.info("No trend data available.")
        return None

    df = pd.DataFrame(trend_data)
    if "date" not in df.columns or "risk_score" not in df.columns:
        if show:
            st.info("No trend data available.")
        return None

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    title = f"Risk Score Trend" + (f" — {county_name}" if county_name else "")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["risk_score"],
        mode="lines+markers", name="Risk Score",
        line=dict(color="#2e7d32", width=2),
    ))
    fig.add_hrect(y0=75, y1=100, fillcolor="rgba(211,45,45,0.1)", line_width=0, name="Critical")
    fig.add_hrect(y0=50, y1=75, fillcolor="rgba(245,124,0,0.1)", line_width=0, name="High")
    fig.add_hrect(y0=25, y1=50, fillcolor="rgba(251,192,45,0.1)", line_width=0, name="Moderate")
    fig.add_hrect(y0=0, y1=25, fillcolor="rgba(46,125,50,0.1)", line_width=0, name="Safe")
    fig.update_layout(
        title=title, xaxis_title="Date", yaxis_title="Risk Score (%)",
        template="plotly_white", height=400,
    )
    if show:
        st.plotly_chart(fig, use_container_width=True)
    return fig


def county_comparison_chart(predictions: list, show: bool = True):
    """Compare risk scores across counties."""
    if not predictions:
        if show:
            st.info("No comparison data available.")
        return None

    df = pd.DataFrame(predictions)
    if "risk_score" not in df.columns:
        if show:
            st.info("No comparison data available.")
        return None

    df = df.sort_values("risk_score", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df.get("county_name", df.get("name", df.index)),
        x=df["risk_score"],
        orientation="h",
        marker_color=[
            "#d32f2f" if s >= 75 else "#f57c00" if s >= 50 else "#fbc02d" if s >= 25 else "#2e7d32"
            for s in df["risk_score"]
        ],
    ))
    fig.update_layout(
        title="County Risk Comparison",
        xaxis_title="Risk Score (%)", yaxis_title="County",
        template="plotly_white", height=400,
    )
    if show:
        st.plotly_chart(fig, use_container_width=True)
    return fig
