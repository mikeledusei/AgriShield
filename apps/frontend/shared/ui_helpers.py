"""
AgriShield UI Helpers (shared/ui_helpers.py).
Provides Kenya's 47-county GeoJSON choropleth map, TreeSHAP feature attribution charts,
global LightGBM feature importance charts, multi-metric agro-climatic charts,
national risk rankings, uploaded-data comparison charts, and KPI cards.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from shared.constants import RISK_LEVELS
from shared.kenya_counties import COUNTY_COORDINATES, normalize_county_name
from shared.types import (
    CompareResult,
    GlobalFeatureImportance,
    HistoryPoint,
    PredictionResult,
    ShapContribution,
    UploadResult,
)

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
GEOJSON_PATH = ASSETS_DIR / "kenya_counties.geojson"


def load_custom_css() -> None:
    """Inject AgriShield custom dark-mode styling."""
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #0b0e11;
            color: #e6edf3;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        [data-testid="stSidebar"] {
            background-color: #15191e !important;
            border-right: 1px solid #262c34 !important;
        }
        div[data-testid="stMetric"] {
            background-color: #15191e;
            border: 1px solid #262c34;
            border-radius: 10px;
            padding: 12px 16px;
        }
        .agri-card {
            background-color: #15191e;
            border: 1px solid #262c34;
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 12px;
        }
        .agri-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.04em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def risk_color(level: str) -> str:
    lvl = (level or "SAFE").upper()
    return RISK_LEVELS.get(lvl, RISK_LEVELS["SAFE"])["color"]


def risk_label_from_score(score: Any) -> str:
    try:
        val = float(score)
    except (TypeError, ValueError):
        return "SAFE"
    if val < 25:
        return "SAFE"
    if val < 50:
        return "MODERATE"
    if val < 75:
        return "HIGH"
    return "CRITICAL"


def format_model_label(model_used: Optional[str]) -> str:
    tag = (model_used or "lightgbm_v1").strip().lower()
    mapping = {
        "lightgbm_v1": "LightGBM Champion v1",
        "xgboost_v1": "XGBoost v1",
        "rule_based": "Rule-Based Fallback",
    }
    return mapping.get(tag, "LightGBM Champion v1")


def summary_badge(level: str) -> str:
    lvl = (level or "SAFE").upper()
    col = risk_color(lvl)
    return (
        f"<span role='status' class='agri-badge' "
        f"style='background:{col}22;color:{col};border:1px solid {col}55;'>{lvl}</span>"
    )


def format_markdown_to_html(text: str) -> str:
    import html as _html
    import re as _re

    escaped = _html.escape(text or "")
    escaped = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    lines = []
    for ln in escaped.splitlines():
        s = ln.strip()
        if s.startswith("- "):
            lines.append(f"• {s[2:]}")
        else:
            lines.append(ln)
    return "<br>".join(lines)


@st.cache_data(show_spinner=False)
def load_kenya_geojson() -> Optional[Dict[str, Any]]:
    """Load the 47-county Kenya GeoJSON and attach a normalized `county_canonical` property."""
    candidates = [
        GEOJSON_PATH,
        Path(__file__).resolve().parents[3]
        / "data_pipeline"
        / "data"
        / "geospatial"
        / "kenya_counties.geojson",
    ]
    for path in candidates:
        if path.exists():
            try:
                gj = json.loads(path.read_text(encoding="utf-8"))
                for feat in gj.get("features", []):
                    props = feat.setdefault("properties", {})
                    raw = (
                        props.get("COUNTY_NAM")
                        or props.get("COUNTY")
                        or props.get("ADM1_EN")
                        or props.get("name")
                        or ""
                    )
                    props["county_canonical"] = normalize_county_name(str(raw))
                return gj
            except Exception:
                continue
    return None


def render_metric_card(
    title: str,
    value: str,
    subtitle: str,
    badge_text: Optional[str] = None,
    badge_color: str = "#22c55e",
) -> None:
    badge_html = ""
    if badge_text:
        badge_html = (
            f'<span class="agri-badge" '
            f'style="background:{badge_color}22;color:{badge_color};border:1px solid {badge_color}55;">'
            f"{badge_text}</span>"
        )
    st.markdown(
        f"""
        <div class="agri-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="color:#9ca3af;font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;">{title}</span>
                {badge_html}
            </div>
            <div style="font-size:1.55rem;font-weight:700;color:#f3f4f6;margin-bottom:4px;">{value}</div>
            <div style="font-size:0.80rem;color:#9ca3af;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_map(
    counties: List[PredictionResult],
    selected_county: Optional[str] = None,
) -> go.Figure:
    """
    Build an interactive 47-county Kenya Risk Map (Choropleth + Centroid Marker Overlay)
    with rich agro-climatic & SHAP tooltips.
    """
    gj = load_kenya_geojson()
    selected_canon = normalize_county_name(selected_county) if selected_county else None

    rows = []
    for pred in counties:
        canon = normalize_county_name(pred.county_name)
        meta = COUNTY_COORDINATES.get(
            canon, {"lat": 0.0236, "lon": 37.9062, "region": pred.region}
        )
        feats = pred.features or {}
        rows.append({
            "county": canon,
            "region": pred.region or meta["region"],
            "risk_score": pred.risk_score,
            "risk_level": pred.risk_level,
            "main_driver": pred.main_driver,
            "rainfall_mm": feats.get("rainfall_mm", 0.0),
            "ndvi_lag1": feats.get("ndvi_lag1", 0.0),
            "forage_dryness_index": feats.get("forage_dryness_index", 0.0),
            "soil_moisture": feats.get("soil_moisture", 0.0),
            "lat": meta["lat"],
            "lon": meta["lon"],
            "color": risk_color(pred.risk_level),
            "is_selected": canon == selected_canon,
        })
    df = pd.DataFrame(rows)

    fig = go.Figure()
    ChoroplethTrace = getattr(go, "Choroplethmap", getattr(go, "Choroplethmapbox", None))
    ScatterTrace = getattr(go, "Scattermap", getattr(go, "Scattermapbox", None))
    use_map_layout = hasattr(go, "Choroplethmap")

    if gj is not None and not df.empty and ChoroplethTrace is not None:
        fig.add_trace(
            ChoroplethTrace(
                geojson=gj,
                locations=df["county"],
                z=df["risk_score"],
                featureidkey="properties.county_canonical",
                colorscale=[
                    [0.0, "#16a34a"],
                    [0.25, "#eab308"],
                    [0.50, "#f97316"],
                    [0.75, "#dc2626"],
                    [1.0, "#991b1b"],
                ],
                zmin=0,
                zmax=100,
                marker_opacity=0.68,
                marker_line_width=1.1,
                marker_line_color="#1f2937",
                colorbar=dict(
                    title=dict(text="Risk %", font=dict(color="#e5e7eb", size=11)),
                    tickfont=dict(color="#9ca3af", size=10),
                    thickness=12,
                    len=0.72,
                    x=0.98,
                ),
                customdata=df[
                    [
                        "region",
                        "risk_level",
                        "main_driver",
                        "rainfall_mm",
                        "ndvi_lag1",
                        "forage_dryness_index",
                        "soil_moisture",
                    ]
                ].values,
                hovertemplate=(
                    "<b>%{location} County</b> (%{customdata[0]})<br>"
                    "Risk Score: <b>%{z}%</b> (%{customdata[1]})<br>"
                    "Rainfall: %{customdata[3]:.1f} mm | NDVI: %{customdata[4]:.2f}<br>"
                    "Forage Dryness Index: %{customdata[5]:.2f} | Soil Moisture: %{customdata[6]:.2f}<br>"
                    "Top SHAP Driver: %{customdata[2]}<extra></extra>"
                ),
                name="County Risk",
            )
        )

    if not df.empty and ScatterTrace is not None:
        sizes = [17 if sel else 9 for sel in df["is_selected"]]
        fig.add_trace(
            ScatterTrace(
                lat=df["lat"],
                lon=df["lon"],
                mode="markers+text",
                marker=dict(
                    size=sizes,
                    color=df["color"],
                    opacity=0.95,
                ),
                text=[row["county"] if row["is_selected"] else "" for _, row in df.iterrows()],
                textposition="top center",
                textfont=dict(color="#ffffff", size=12),
                customdata=df[["county", "region", "risk_score", "risk_level", "main_driver"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                    "Risk Score: <b>%{customdata[2]}%</b> (%{customdata[3]})<br>"
                    "Driver: %{customdata[4]}<extra></extra>"
                ),
                showlegend=False,
            )
        )

    center_lat, center_lon, zoom = 0.25, 37.85, 5.2
    if selected_canon and selected_canon in COUNTY_COORDINATES:
        center_lat = float(COUNTY_COORDINATES[selected_canon]["lat"])
        center_lon = float(COUNTY_COORDINATES[selected_canon]["lon"])
        zoom = 6.0

    map_cfg = dict(
        style="carto-darkmatter",
        center=dict(lat=center_lat, lon=center_lon),
        zoom=zoom,
    )
    layout_kwargs = dict(
        margin=dict(l=0, r=0, t=0, b=0),
        height=470,
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
    )
    if use_map_layout:
        layout_kwargs["map"] = map_cfg
    else:
        layout_kwargs["mapbox"] = map_cfg
    fig.update_layout(**layout_kwargs)
    return fig


def render_national_top_risk_chart(
    counties: List[PredictionResult], top_n: int = 15
) -> go.Figure:
    """Horizontal bar chart ranking the Top-N highest-risk counties across Kenya."""
    ranked = sorted(counties, key=lambda c: c.risk_score, reverse=True)[:top_n]
    ranked = list(reversed(ranked))
    names = [c.county_name for c in ranked]
    scores = [c.risk_score for c in ranked]
    colors = [risk_color(c.risk_level) for c in ranked]
    drivers = [c.main_driver for c in ranked]

    fig = go.Figure(
        go.Bar(
            y=names,
            x=scores,
            orientation="h",
            marker_color=colors,
            text=[f"{s}% ({c.risk_level})" for s, c in zip(scores, ranked)],
            textposition="outside",
            customdata=drivers,
            hovertemplate="<b>%{y} County</b>: %{x}%<br>SHAP Driver: %{customdata}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(
            text=f"Top {top_n} Highest-Risk Counties in Kenya (Champion Model)",
            font=dict(size=13, color="#e5e7eb"),
        ),
        xaxis=dict(
            title="Predicted Risk Score (%)",
            range=[0, 112],
            gridcolor="#1f2937",
            color="#9ca3af",
        ),
        yaxis=dict(gridcolor="#1f2937", color="#e5e7eb"),
        height=390,
        margin=dict(l=10, r=35, t=40, b=25),
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
    )
    return fig


def render_risk_tier_donut(counties: List[PredictionResult]) -> go.Figure:
    """Donut chart showing the distribution of all 47 Kenyan counties across the 4 risk tiers."""
    tiers = ["CRITICAL", "HIGH", "MODERATE", "SAFE"]
    counts = [
        sum(1 for c in counties if c.risk_level == t)
        for t in tiers
    ]
    colors = [risk_color(t) for t in tiers]

    fig = go.Figure(
        go.Pie(
            labels=tiers,
            values=counts,
            hole=0.58,
            marker=dict(colors=colors, line=dict(color="#15191e", width=2)),
            textinfo="label+value",
            hovertemplate="<b>%{label}</b>: %{value} counties (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(
            text="National 47-County Risk Tier Distribution",
            font=dict(size=13, color="#e5e7eb"),
        ),
        height=390,
        margin=dict(l=10, r=10, t=40, b=20),
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
        legend=dict(font=dict(color="#e5e7eb", size=11), orientation="h", y=-0.05),
    )
    return fig


def render_shap_waterfall_chart(
    shap_items: List[ShapContribution],
    county_name: str,
    top_n: int = 12,
) -> go.Figure:
    """
    Diverging horizontal bar chart of local TreeSHAP feature contributions.
    Positive bars (red/orange) push drought risk UP; negative bars (green) push risk DOWN.
    """
    top_items = list(reversed(shap_items[:top_n]))
    labels = [f"{it.label} ({it.value:g})" for it in top_items]
    vals = [it.shap_value for it in top_items]
    colors = [
        "#ef4444" if v > 0.02 else "#22c55e" if v < -0.02 else "#64748b"
        for v in vals
    ]

    fig = go.Figure(
        go.Bar(
            y=labels,
            x=vals,
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.2f}" for v in vals],
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "TreeSHAP Impact (log-odds): <b>%{x:+.3f}</b><extra></extra>"
            ),
        )
    )
    fig.add_vline(x=0, line_width=1.2, line_color="#94a3b8")
    fig.update_layout(
        title=dict(
            text=f"Local TreeSHAP Feature Attribution — {county_name} (Red = Pushes Risk Up, Green = Reduces Risk)",
            font=dict(size=13, color="#e5e7eb"),
        ),
        xaxis=dict(
            title="SHAP Contribution to Drought Risk (log-odds)",
            gridcolor="#1f2937",
            color="#9ca3af",
            zeroline=True,
        ),
        yaxis=dict(gridcolor="#1f2937", color="#e5e7eb"),
        height=410,
        margin=dict(l=15, r=45, t=42, b=30),
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
    )
    return fig


def render_global_importance_chart(
    global_items: List[GlobalFeatureImportance],
) -> go.Figure:
    """Horizontal bar chart of all 16 LightGBM Champion Model global feature importances."""
    ordered = list(reversed(global_items))
    labels = [it.label for it in ordered]
    pcts = [it.importance_pct for it in ordered]
    splits = [it.importance for it in ordered]

    fig = go.Figure(
        go.Bar(
            y=labels,
            x=pcts,
            orientation="h",
            marker_color="#3b82f6",
            text=[f"{p:.1f}% ({int(s)} splits)" for p, s in zip(pcts, splits)],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Share of Model Decisions: %{x:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(
            text="Global LightGBM Champion Feature Importance (All 16 Engineered Features)",
            font=dict(size=13, color="#e5e7eb"),
        ),
        xaxis=dict(
            title="Share of Total Split Importance (%)",
            range=[0, max(pcts + [15.0]) * 1.28],
            gridcolor="#1f2937",
            color="#9ca3af",
        ),
        yaxis=dict(gridcolor="#1f2937", color="#e5e7eb"),
        height=430,
        margin=dict(l=15, r=65, t=42, b=30),
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
    )
    return fig


def render_trend_chart(trend: List[HistoryPoint], county_name: str) -> go.Figure:
    """Render 12-month historical risk score trajectory for a county."""
    dates = [pt.date for pt in trend]
    scores = [pt.risk_score for pt in trend]
    colors = [risk_color(pt.risk_level) for pt in trend]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=scores,
            mode="lines+markers",
            line=dict(color="#22c55e", width=2.6),
            marker=dict(size=9, color=colors, line=dict(width=1.5, color="#0b0e11")),
            fill="tozeroy",
            fillcolor="rgba(34, 197, 94, 0.10)",
            hovertemplate="<b>%{x}</b><br>Risk Score: <b>%{y}%</b><extra></extra>",
            name=county_name,
        )
    )

    for thresh, label, col in [
        (25, "Moderate (25%)", "#eab308"),
        (50, "High (50%)", "#f97316"),
        (75, "Critical (75%)", "#ef4444"),
    ]:
        fig.add_hline(
            y=thresh,
            line_dash="dot",
            line_color=col,
            opacity=0.45,
            annotation_text=label,
            annotation_position="top right",
            annotation_font=dict(size=10, color=col),
        )

    fig.update_layout(
        title=dict(
            text=f"{county_name} County — 12-Month Risk Trajectory",
            font=dict(size=13, color="#e5e7eb"),
        ),
        xaxis=dict(title="Month", gridcolor="#1f2937", color="#9ca3af"),
        yaxis=dict(title="Risk Score (%)", range=[0, 105], gridcolor="#1f2937", color="#9ca3af"),
        height=300,
        margin=dict(l=15, r=15, t=38, b=20),
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
        showlegend=False,
    )
    return fig


def render_climate_diagnostics_chart(
    trend: List[HistoryPoint], county_name: str
) -> go.Figure:
    """Dual-axis agro-climatic chart: Monthly Rainfall (mm) bars + NDVI, Soil Moisture & Forage Dryness lines."""
    dates = [pt.date for pt in trend]
    rain = [pt.rainfall_mm for pt in trend]
    ndvi = [pt.ndvi_lag1 for pt in trend]
    soil = [pt.soil_moisture for pt in trend]
    fdi = [pt.forage_dryness_index for pt in trend]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=dates,
            y=rain,
            name="Rainfall (mm)",
            marker_color="rgba(59, 130, 246, 0.48)",
            hovertemplate="<b>%{x}</b><br>Rainfall: %{y:.1f} mm<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=ndvi,
            name="NDVI Greenness",
            mode="lines+markers",
            line=dict(color="#22c55e", width=2.4),
            hovertemplate="<b>%{x}</b><br>NDVI: %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=soil,
            name="Soil Moisture (m³/m³)",
            mode="lines+markers",
            line=dict(color="#38bdf8", width=2.0, dash="dot"),
            hovertemplate="<b>%{x}</b><br>Soil Moisture: %{y:.2f} m³/m³<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=fdi,
            name="Forage Dryness Index",
            mode="lines+markers",
            line=dict(color="#f97316", width=2.2),
            hovertemplate="<b>%{x}</b><br>Forage Dryness Index: %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title=dict(
            text=f"{county_name} — 12-Month Rainfall, NDVI Greenness, Soil Moisture & Forage Dryness",
            font=dict(size=13, color="#e5e7eb"),
        ),
        height=320,
        margin=dict(l=15, r=15, t=40, b=20),
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
        legend=dict(orientation="h", y=-0.18, font=dict(color="#e5e7eb", size=10)),
    )
    fig.update_yaxes(
        title_text="Monthly Rainfall (mm)",
        gridcolor="#1f2937",
        color="#9ca3af",
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Index (NDVI / Soil / FDI)",
        gridcolor="#1f2937",
        color="#9ca3af",
        secondary_y=True,
    )
    return fig


def render_comparison_chart(compare_res: CompareResult) -> go.Figure:
    """Horizontal bar chart comparing selected counties by risk score."""
    names = [c.county_name for c in compare_res.counties]
    scores = [c.risk_score for c in compare_res.counties]
    colors = [risk_color(c.risk_level) for c in compare_res.counties]

    fig = go.Figure(
        go.Bar(
            x=scores,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{s}% ({c.risk_level})" for s, c in zip(scores, compare_res.counties)],
            textposition="auto",
        )
    )
    fig.update_layout(
        title=dict(
            text="Multi-County Risk Comparison",
            font=dict(size=13, color="#e5e7eb"),
        ),
        xaxis=dict(title="Risk Score (%)", range=[0, 105], gridcolor="#1f2937", color="#9ca3af"),
        yaxis=dict(autorange="reversed", gridcolor="#1f2937", color="#e5e7eb"),
        height=260,
        margin=dict(l=10, r=15, t=35, b=20),
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
    )
    return fig


def render_upload_comparison_chart(
    upload_res: UploadResult,
    baseline_pred: PredictionResult,
) -> go.Figure:
    """Bar chart comparing the Uploaded File's Risk Score vs. the Official County Baseline."""
    labels = [
        f"Official Baseline ({baseline_pred.county_name})",
        f"Uploaded Data ({upload_res.file_name})",
    ]
    base_score = (
        float(upload_res.baseline_risk_score)
        if upload_res.baseline_risk_score is not None
        else float(baseline_pred.risk_score)
    )
    up_score = float(upload_res.risk_score)
    colors = [
        risk_color(upload_res.baseline_risk_level or baseline_pred.risk_level),
        risk_color(upload_res.risk_level),
    ]

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=[base_score, up_score],
            marker_color=colors,
            text=[
                f"{base_score:.0f}% ({upload_res.baseline_risk_level or baseline_pred.risk_level})",
                f"{up_score:.0f}% ({upload_res.risk_level})",
            ],
            textposition="auto",
        )
    )
    fig.update_layout(
        title=dict(
            text="Uploaded Data vs. Official LightGBM County Baseline",
            font=dict(size=12, color="#e5e7eb"),
        ),
        yaxis=dict(title="Risk Score (%)", range=[0, 108], gridcolor="#1f2937", color="#9ca3af"),
        xaxis=dict(color="#e5e7eb"),
        height=230,
        margin=dict(l=10, r=10, t=35, b=15),
        paper_bgcolor="#15191e",
        plot_bgcolor="#15191e",
    )
    return fig
