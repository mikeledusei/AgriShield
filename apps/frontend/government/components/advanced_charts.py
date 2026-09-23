"""Advanced charts for government analytics."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def regional_comparison_chart(regions_data: dict):
    """Compare average risk across regions."""
    if not regions_data:
        st.info("No region data available.")
        return None

    df = pd.DataFrame([
        {"Region": k, "Average Risk": v.get("avg_risk", 0), "Counties": len(v.get("counties", []))}
        for k, v in regions_data.items()
    ])

    fig = px.bar(df, x="Region", y="Average Risk", color="Region",
                 title="Regional Risk Comparison",
                 color_discrete_sequence=px.colors.qualitative.Set2)
    fig.update_layout(template="plotly_white", height=450)
    st.plotly_chart(fig, use_container_width=True)
    return fig


def monthly_trend_chart(monthly_data: list):
    """Show monthly aggregation of risk scores."""
    if not monthly_data:
        st.info("No monthly data available.")
        return None

    df = pd.DataFrame(monthly_data)
    if "month" not in df.columns or "risk_score" not in df.columns:
        st.info("Invalid monthly data format.")
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["month"], y=df["risk_score"],
        mode="lines+markers", name="Monthly Avg Risk",
        line=dict(color="#2e7d32", width=2),
    ))
    fig.update_layout(title="Monthly Risk Trends",
                       xaxis_title="Month", yaxis_title="Avg Risk Score (%)",
                       template="plotly_white", height=400)
    st.plotly_chart(fig, use_container_width=True)
    return fig
