"""
AgriShield Geospatial AI Early-Warning Dashboard (apps/frontend/streamlit_app.py).

Full-stack Streamlit workspace integrating:
1. All 47 Kenyan Counties Geospatial Choropleth Risk Map & National Risk Charts
2. Future Forecast Simulator powered by sliders for all 16 LightGBM Champion Model Features
3. Exact TreeSHAP Local & Global Explainability Charts + Plain-Language Translation
4. Multi-Metric Agro-Climatic Trend Charts (Rainfall, NDVI, Soil Moisture, Forage Dryness)
5. Gria Agentic AI: Plain-English Model Simplifier, Multi-Format Uploaded Data Converter &
   Baseline Comparator (CSV, XLSX, PDF, DOCX, Images), and Interactive Chat
"""
from pathlib import Path
import sys
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from shared.api_client import get_client
from shared.constants import KENYA_COUNTIES, KENYA_REGIONS
from shared.kenya_counties import COUNTY_COORDINATES
from shared.types import ExplainResult, FutureForecastResult, PredictionResult, UploadResult
from shared.ui_helpers import (
    load_custom_css,
    load_kenya_geojson,
    render_climate_diagnostics_chart,
    render_comparison_chart,
    render_global_importance_chart,
    render_map,
    render_metric_card,
    render_national_top_risk_chart,
    render_risk_tier_donut,
    render_shap_waterfall_chart,
    render_trend_chart,
    render_upload_comparison_chart,
    risk_color,
)

MONTH_NAMES = {
    1: "January (Dry Season)",
    2: "February (Peak Dry Stress)",
    3: "March (Long Rains Onset)",
    4: "April (Long Rains Peak)",
    5: "May (Long Rains Tail)",
    6: "June (Cool Dry Transition)",
    7: "July (Cool Dry Season)",
    8: "August (Pre-Short Rains Dry)",
    9: "September (Late Dry Stress)",
    10: "October (Short Rains Onset)",
    11: "November (Short Rains Peak)",
    12: "December (Post-Short Rains Greenup)",
}


st.set_page_config(
    page_title="AgriShield | Kenya Food Security & SHAP Early-Warning System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_custom_css()
client = get_client()

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "selected_county" not in st.session_state:
    st.session_state.selected_county = "Turkana"
if "selected_focus" not in st.session_state:
    st.session_state.selected_focus = "combined"
if "selected_month" not in st.session_state:
    st.session_state.selected_month = "2025-02"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": (
                "Jambo! I am **Gria**, your AgriShield AI advisor. I translate our **LightGBM Champion Model** "
                "and **TreeSHAP Explainability** into simple, everyday language, convert and compare your uploaded "
                "datasets against official county baselines, and help you plan crop & livestock actions across all **47 Kenyan counties**."
            ),
        }
    ]
if "uploaded_context" not in st.session_state:
    st.session_state.uploaded_context = None
if "uploaded_name" not in st.session_state:
    st.session_state.uploaded_name = None
if "last_upload_result" not in st.session_state:
    st.session_state.last_upload_result = None
if "last_forecast_result" not in st.session_state:
    st.session_state.last_forecast_result = None


# ---------------------------------------------------------------------------
# Cached Data Fetchers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
def fetch_available_months() -> List[str]:
    months = client.get_available_months()
    # Keep 2024-2025 holdout months at top for fast selection while allowing full 2015-2025
    recent = [m for m in months if m >= "2024-01"]
    return sorted(recent, reverse=True) if recent else ["2025-02", "2025-09", "2025-12"]


@st.cache_data(ttl=60, show_spinner=False)
def fetch_batch(month: Optional[str]):
    return client.get_batch_predictions(month=month)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_county_prediction(county_name: str, focus: str, month: Optional[str]) -> PredictionResult:
    return client.get_prediction(county_name, focus=focus, month=month)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_county_explain(county_name: str, month: Optional[str]) -> ExplainResult:
    return client.explain_county(county_name, month=month)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_county_history(county_name: str, months: int = 12):
    return client.get_history(county_name, months=months)


# ---------------------------------------------------------------------------
# Sidebar: County, Observation Period, Focus & National Risk Summary
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🛡️ AgriShield Kenya")
    st.caption(
        "Geospatial Drought & Forage Early-Warning System (2015–2025 Pipeline + LightGBM Champion + TreeSHAP)"
    )

    health = client.check_health()
    mode_badge = "FastAPI Live" if client.last_mode == "api" else "Embedded LightGBM + SHAP"
    mode_color = "#22c55e" if client.last_mode == "api" else "#3b82f6"
    st.markdown(
        f'<div style="margin-bottom:12px;">'
        f'<span class="agri-badge" style="background:{mode_color}22;color:{mode_color};border:1px solid {mode_color}55;">'
        f"⚡ {mode_badge}</span></div>",
        unsafe_allow_html=True,
    )

    selected_county = st.selectbox(
        "Select Kenyan County (All 47 Counties)",
        options=KENYA_COUNTIES,
        index=KENYA_COUNTIES.index(st.session_state.selected_county)
        if st.session_state.selected_county in KENYA_COUNTIES
        else 0,
    )
    st.session_state.selected_county = selected_county

    available_months = fetch_available_months()
    default_m_idx = (
        available_months.index(st.session_state.selected_month)
        if st.session_state.selected_month in available_months
        else (available_months.index("2025-02") if "2025-02" in available_months else 0)
    )
    selected_month = st.selectbox(
        "Observation Period (Year-Month)",
        options=available_months,
        index=default_m_idx,
        help="Select any historical/holdout month. '2025-02' represents the peak dry-season benchmark across Kenya's 47 counties; '2025-12' reflects post-Short Rains greenup.",
    )
    st.session_state.selected_month = selected_month

    focus_options = ["combined", "crops", "livestock"]
    selected_focus = st.selectbox(
        "Agricultural Focus",
        options=focus_options,
        index=focus_options.index(st.session_state.selected_focus),
        format_func=lambda x: x.capitalize(),
    )
    st.session_state.selected_focus = selected_focus

    county_meta = COUNTY_COORDINATES.get(selected_county, {})
    st.markdown(
        f"**Region:** `{county_meta.get('region', 'Kenya')}`  \n"
        f"**Centroid:** `{county_meta.get('lat', 0.0):.2f}°, {county_meta.get('lon', 0.0):.2f}°`"
    )

    st.divider()
    batch_data = fetch_batch(selected_month)
    crit_count = sum(1 for c in batch_data.counties if c.risk_level == "CRITICAL")
    high_count = sum(1 for c in batch_data.counties if c.risk_level == "HIGH")
    mod_count = sum(1 for c in batch_data.counties if c.risk_level == "MODERATE")
    safe_count = sum(1 for c in batch_data.counties if c.risk_level == "SAFE")
    nat_mean = (
        round(sum(c.risk_score for c in batch_data.counties) / len(batch_data.counties), 1)
        if batch_data.counties
        else 0.0
    )

    st.markdown(f"### 🇰🇪 National Snapshot (`{selected_month}`)")
    st.caption(f"National Mean Risk Score: **{nat_mean}%** across **{batch_data.county_count} counties**")
    s_col1, s_col2 = st.columns(2)
    s_col1.metric("Critical Tier", crit_count)
    s_col2.metric("High Tier", high_count)
    s_col3, s_col4 = st.columns(2)
    s_col3.metric("Moderate Tier", mod_count)
    s_col4.metric("Safe Tier", safe_count)


# ---------------------------------------------------------------------------
# Fetch Active County Prediction, TreeSHAP Explanation & 12-Month History
# ---------------------------------------------------------------------------
active_pred = fetch_county_prediction(selected_county, selected_focus, selected_month)
explain_data = fetch_county_explain(selected_county, selected_month)
history_data = fetch_county_history(selected_county, months=12)

# ---------------------------------------------------------------------------
# Main Layout: Center Workspace (Left/Center) + Gria AI Dock (Right)
# ---------------------------------------------------------------------------
workspace_col, gria_col = st.columns([2.25, 1.05], gap="medium")

with workspace_col:
    st.markdown(
        f"## 📍 {active_pred.county_name} County — Agro-Climatic Risk & Explainable AI (`{selected_month}`)"
    )

    # Top KPI Row
    feats = active_pred.features or {}
    ndvi_val = feats.get("ndvi_lag1", 0.50)
    rain_mm = feats.get("rainfall_mm", 65.0)
    rain_anom = feats.get("rainfall_anomaly", 0.0)
    soil_m = feats.get("soil_moisture", 0.25)
    fdi_val = feats.get("forage_dryness_index", 0.20)
    temp_val = feats.get("temp_mean_c", 24.0)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_metric_card(
            title="Champion Model Risk",
            value=f"{active_pred.risk_score}%",
            subtitle=f"Scorer: {active_pred.model_used} ({selected_month})",
            badge_text=active_pred.risk_level,
            badge_color=risk_color(active_pred.risk_level),
        )
    with k2:
        render_metric_card(
            title="#1 TreeSHAP Risk Driver",
            value=active_pred.main_driver.split("(")[0].strip()[:22],
            subtitle=active_pred.main_driver,
            badge_text="SHAP",
            badge_color="#f97316",
        )
    with k3:
        render_metric_card(
            title="Forage Dryness & NDVI",
            value=f"FDI {fdi_val:.2f} | NDVI {ndvi_val:.2f}",
            subtitle=f"NDVI Anomaly: {feats.get('ndvi_anomaly', 0.0):+.3f} vs mean",
            badge_text="Pasture",
            badge_color="#22c55e" if fdi_val < 0.35 else "#eab308",
        )
    with k4:
        render_metric_card(
            title="Rainfall & Soil Moisture",
            value=f"{rain_mm:.1f} mm",
            subtitle=f"Rain Anom: {rain_anom:+.1f} mm | Soil: {soil_m:.2f} m³/m³ | {temp_val:.1f}°C",
            badge_text="CHIRPS/ERA5",
            badge_color="#38bdf8",
        )

    # -----------------------------------------------------------------------
    # Section 1: National 47-County Geospatial Risk Map & Country Overview Charts
    # -----------------------------------------------------------------------
    st.markdown(f"### 🗺️ Kenya 47-County Risk Map & National Charts (`{selected_month}`)")
    map_tab, nat_charts_tab = st.tabs([
        "🗺️ Interactive 47-County Choropleth Map",
        "📊 National Top-15 Risk Ranking & Tier Distribution",
    ])
    with map_tab:
        map_fig = render_map(batch_data.counties, selected_county=selected_county)
        st.plotly_chart(map_fig, use_container_width=True, config={"displayModeBar": False})
    with nat_charts_tab:
        nc1, nc2 = st.columns([1.35, 1.0])
        with nc1:
            st.plotly_chart(
                render_national_top_risk_chart(batch_data.counties, top_n=15),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        with nc2:
            st.plotly_chart(
                render_risk_tier_donut(batch_data.counties),
                use_container_width=True,
                config={"displayModeBar": False},
            )

    # -----------------------------------------------------------------------
    # Section 2: Core Analytical Tabs (Future Sliders, SHAP, Trends, Comparison)
    # -----------------------------------------------------------------------
    tab_forecast, tab_shap, tab_trends, tab_compare = st.tabs([
        "🔮 Future Forecast (Champion Model Sliders)",
        "🧠 SHAP Explainability (Why the Model Predicts This)",
        "📈 County Climate Charts & Stress Test",
        "⚖️ Multi-County & Regional Comparison",
    ])

    # ---- TAB 1: FUTURE FORECAST (CHAMPION MODEL FEATURE SLIDERS) ----
    with tab_forecast:
        st.markdown(
            f"#### 🔮 Predict the Future for **{selected_county}** Using LightGBM Champion Model Feature Sliders"
        )
        st.caption(
            "All sliders below are initialized to the selected county's real baseline values from the 16-feature "
            "LightGBM Champion Model (`lightgbm_agrishield_v1.joblib`). Adjust any combination of climate, vegetation, "
            "and household indicators to forecast future drought and forage risk."
        )

        default_target_m = (
            int(selected_month.split("-")[1])
            if "-" in str(selected_month)
            else 2
        )

        fc_top1, fc_top2 = st.columns([1.3, 1.0])
        with fc_top1:
            target_month_num = st.slider(
                "Target Future Month (1 = Jan ... 12 = Dec; updates month_sin & month_cos)",
                min_value=1,
                max_value=12,
                value=default_target_m,
                step=1,
                key=f"fc_month_{selected_county}",
            )
            st.caption(f"Selected Target Season: **{MONTH_NAMES.get(target_month_num, '')}**")
        with fc_top2:
            auto_derive = st.checkbox(
                "Auto-recalculate linked indices (Forage Dryness, Rain & NDVI Anomalies) from raw sliders",
                value=False,
                help="When unchecked, you have direct manual control over every single one of the 16 Champion Model features including Forage Dryness Index and Anomalies. When checked, Forage Dryness and Anomalies auto-update from Rainfall, Soil Moisture, Temperature, and NDVI.",
                key=f"fc_auto_{selected_county}",
            )

        st.markdown("##### 🌧️ 1. Top Moisture, Rainfall & Temperature Features")
        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            s_rainfall_mm = st.slider(
                "Monthly Rainfall — `rainfall_mm` (mm)",
                min_value=0.0,
                max_value=450.0,
                value=float(round(feats.get("rainfall_mm", 65.0), 1)),
                step=2.0,
                key=f"s_rain_{selected_county}_{selected_month}",
            )
            s_rain_3m = st.slider(
                "3-Month Cumulative Rain — `rain_3m_sum` (mm)",
                min_value=0.0,
                max_value=1000.0,
                value=float(round(feats.get("rain_3m_sum", 220.0), 1)),
                step=5.0,
                key=f"s_rain3m_{selected_county}_{selected_month}",
            )
        with r_col2:
            s_rain_anom = st.slider(
                "30-Day Rainfall Anomaly — `rainfall_anomaly` (mm)",
                min_value=-200.0,
                max_value=200.0,
                value=float(round(feats.get("rainfall_anomaly", -10.0), 1)),
                step=2.0,
                key=f"s_rain_anom_{selected_county}_{selected_month}",
            )
            s_soil_m = st.slider(
                "Root-Zone Soil Moisture — `soil_moisture` (m³/m³)",
                min_value=0.03,
                max_value=0.47,
                value=float(round(feats.get("soil_moisture", 0.25), 3)),
                step=0.01,
                key=f"s_soil_{selected_county}_{selected_month}",
            )
        with r_col3:
            s_temp_c = st.slider(
                "Land Surface Temperature — `temp_mean_c` (°C)",
                min_value=10.0,
                max_value=38.5,
                value=float(round(feats.get("temp_mean_c", 24.0), 1)),
                step=0.5,
                key=f"s_temp_{selected_county}_{selected_month}",
            )
            s_fdi = st.slider(
                "Forage Dryness Index (#1 Model Feature) — `forage_dryness_index`",
                min_value=0.00,
                max_value=1.80,
                value=float(round(feats.get("forage_dryness_index", 0.20), 2)),
                step=0.02,
                key=f"s_fdi_{selected_county}_{selected_month}",
            )

        st.markdown("##### 🌿 2. Pasture & Vegetation Greenness (MODIS NDVI) Features")
        v_col1, v_col2, v_col3 = st.columns(3)
        with v_col1:
            s_ndvi_anom = st.slider(
                "NDVI Vegetation Anomaly — `ndvi_anomaly`",
                min_value=-0.25,
                max_value=0.25,
                value=float(round(feats.get("ndvi_anomaly", 0.0), 3)),
                step=0.01,
                key=f"s_ndvi_anom_{selected_county}_{selected_month}",
            )
            s_ndvi_lag1 = st.slider(
                "Previous Month Greenness — `ndvi_lag1`",
                min_value=0.15,
                max_value=0.82,
                value=float(round(feats.get("ndvi_lag1", 0.50), 2)),
                step=0.01,
                key=f"s_ndvi_l1_{selected_county}_{selected_month}",
            )
        with v_col2:
            s_ndvi_lag3 = st.slider(
                "Greenness 3 Months Ago — `ndvi_lag3`",
                min_value=0.15,
                max_value=0.82,
                value=float(round(feats.get("ndvi_lag3", 0.52), 2)),
                step=0.01,
                key=f"s_ndvi_l3_{selected_county}_{selected_month}",
            )
            s_ndvi_r3_mean = st.slider(
                "3-Month Rolling NDVI Mean — `ndvi_roll3_mean`",
                min_value=0.15,
                max_value=0.82,
                value=float(round(feats.get("ndvi_roll3_mean", 0.51), 2)),
                step=0.01,
                key=f"s_ndvi_rm_{selected_county}_{selected_month}",
            )
        with v_col3:
            s_ndvi_r3_std = st.slider(
                "3-Month NDVI Volatility — `ndvi_roll3_std`",
                min_value=0.00,
                max_value=0.20,
                value=float(round(feats.get("ndvi_roll3_std", 0.04), 3)),
                step=0.005,
                key=f"s_ndvi_rs_{selected_county}_{selected_month}",
            )

        with st.expander("🏡 3. Structural County Exposure Sliders (KNBS Census Features)", expanded=False):
            h_col1, h_col2, h_col3 = st.columns(3)
            with h_col1:
                s_farming = st.slider(
                    "Farming Household Ratio — `farming_ratio`",
                    min_value=0.02,
                    max_value=0.85,
                    value=float(round(feats.get("farming_ratio", 0.55), 2)),
                    step=0.01,
                    key=f"s_farm_{selected_county}_{selected_month}",
                )
            with h_col2:
                s_livestock = st.slider(
                    "Livestock Household Share — `livestock_share`",
                    min_value=0.35,
                    max_value=0.88,
                    value=float(round(feats.get("livestock_share", 0.50), 2)),
                    step=0.01,
                    key=f"s_live_{selected_county}_{selected_month}",
                )
            with h_col3:
                s_irrig = st.slider(
                    "Irrigation Coverage Ratio — `irrigation_ratio`",
                    min_value=0.01,
                    max_value=0.30,
                    value=float(round(feats.get("irrigation_ratio", 0.05), 3)),
                    step=0.005,
                    key=f"s_irrig_{selected_county}_{selected_month}",
                )

        # Run live future forecast with the slider values
        slider_overrides: Dict[str, Optional[float]] = {
            "rainfall_mm": s_rainfall_mm,
            "rain_3m_sum": s_rain_3m,
            "rainfall_anomaly": None if auto_derive else s_rain_anom,
            "temp_mean_c": s_temp_c,
            "soil_moisture": s_soil_m,
            "ndvi_lag1": s_ndvi_lag1,
            "ndvi_lag3": s_ndvi_lag3,
            "ndvi_roll3_mean": s_ndvi_r3_mean,
            "ndvi_roll3_std": s_ndvi_r3_std,
            "ndvi_anomaly": None if auto_derive else s_ndvi_anom,
            "forage_dryness_index": None if auto_derive else s_fdi,
            "farming_ratio": s_farming,
            "livestock_share": s_livestock,
            "irrigation_ratio": s_irrig,
        }

        fc_result: FutureForecastResult = client.forecast_future(
            county_name=selected_county,
            target_month=target_month_num,
            focus=selected_focus,
            auto_derive_indices=auto_derive,
            overrides=slider_overrides,
        )
        st.session_state.last_forecast_result = fc_result

        st.markdown("##### 📊 Future Forecast Result vs. County Baseline")
        res_c1, res_c2, res_c3 = st.columns(3)
        res_c1.metric(
            f"Current Baseline ({active_pred.month})",
            f"{active_pred.risk_score}% ({active_pred.risk_level})",
        )
        res_c2.metric(
            f"Projected Future Risk (2026-{target_month_num:02d})",
            f"{fc_result.forecast.risk_score}% ({fc_result.forecast.risk_level})",
            delta=f"{fc_result.score_delta - (fc_result.baseline.risk_score - active_pred.risk_score):+d}% vs. {active_pred.month}",
            delta_color="inverse",
        )
        res_c3.metric(
            "Top Projected SHAP Driver",
            fc_result.forecast.main_driver.split("(")[0].strip()[:24],
        )

        st.info(fc_result.gria_plain_analysis)

        if fc_result.forecast.shap_contributions:
            st.plotly_chart(
                render_shap_waterfall_chart(
                    fc_result.forecast.shap_contributions,
                    f"{selected_county} — Projected 2026-{target_month_num:02d} Forecast",
                    top_n=10,
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )

    # ---- TAB 2: SHAP EXPLAINABILITY (LOCAL WATERFALL + GLOBAL IMPORTANCE) ----
    with tab_shap:
        st.markdown(
            f"#### 🧠 TreeSHAP Explainability for **{selected_county}** (`{selected_month}`)"
        )
        st.markdown(explain_data.plain_explanation)

        if explain_data.local_shap:
            st.plotly_chart(
                render_shap_waterfall_chart(
                    explain_data.local_shap,
                    f"{selected_county} ({selected_month})",
                    top_n=14,
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )

        if explain_data.global_importance:
            st.plotly_chart(
                render_global_importance_chart(explain_data.global_importance),
                use_container_width=True,
                config={"displayModeBar": False},
            )

        with st.expander("📋 View Full 16-Feature Values & Exact TreeSHAP Contributions Table", expanded=False):
            shap_df = pd.DataFrame([
                {
                    "Feature Code": s.feature,
                    "Human-Readable Feature": s.label,
                    "County Value": s.value,
                    "TreeSHAP Impact (log-odds)": s.shap_value,
                    "Direction": (
                        "🔺 Increases Drought Risk"
                        if s.impact_direction == "increases_risk"
                        else "🟢 Reduces Drought Risk"
                        if s.impact_direction == "reduces_risk"
                        else "⚪ Neutral"
                    ),
                }
                for s in explain_data.local_shap
            ])
            st.dataframe(shap_df, use_container_width=True, hide_index=True)

    # ---- TAB 3: COUNTY CLIMATE CHARTS & QUICK STRESS TEST ----
    with tab_trends:
        st.markdown(
            f"#### 📈 12-Month Risk & Agro-Climatic Charts for **{selected_county}**"
        )
        trend_fig = render_trend_chart(history_data.trend, selected_county)
        st.plotly_chart(trend_fig, use_container_width=True, config={"displayModeBar": False})

        clim_fig = render_climate_diagnostics_chart(history_data.trend, selected_county)
        st.plotly_chart(clim_fig, use_container_width=True, config={"displayModeBar": False})

        st.divider()
        st.markdown("##### ⚡ Quick Percentage Shock Stress-Test")
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            rain_shock = st.slider("Rainfall Shock (%)", -80, 100, -35, step=5)
        with sc2:
            temp_shock = st.slider("Temperature Shift (°C)", -3.0, 6.0, 2.0, step=0.5)
        with sc3:
            ndvi_shock = st.slider("NDVI Pasture Shift", -0.35, 0.30, -0.12, step=0.02)

        sim_res = client.run_scenario(
            selected_county,
            rainfall_change_pct=float(rain_shock),
            temp_change_c=float(temp_shock),
            ndvi_shock=float(ndvi_shock),
            month=selected_month,
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Baseline Risk", f"{sim_res.original.risk_score}% ({sim_res.original.risk_level})")
        m2.metric(
            "Shocked Risk",
            f"{sim_res.scenario.risk_score}% ({sim_res.scenario.risk_level})",
            delta=f"{sim_res.score_delta:+d}%",
            delta_color="inverse",
        )
        m3.metric("Top Driver Under Shock", sim_res.scenario.main_driver.split("(")[0].strip()[:24])
        st.caption(sim_res.narrative)

    # ---- TAB 4: MULTI-COUNTY & REGIONAL COMPARISON ----
    with tab_compare:
        default_peers = [selected_county] + [
            c for c in ["Turkana", "Marsabit", "Garissa", "Machakos", "Nakuru", "Uasin Gishu"]
            if c != selected_county
        ][:4]
        compare_selection = st.multiselect(
            "Select Counties to Compare Side-by-Side (2–10)",
            options=KENYA_COUNTIES,
            default=default_peers,
            max_selections=10,
        )
        if len(compare_selection) >= 2:
            comp_res = client.compare_counties(compare_selection, month=selected_month)
            st.plotly_chart(
                render_comparison_chart(comp_res),
                use_container_width=True,
                config={"displayModeBar": False},
            )
            st.caption(
                f"Highest risk: **{comp_res.highest_risk.county_name}** ({comp_res.highest_risk.risk_score}% — {comp_res.highest_risk.main_driver}) | "
                f"Lowest risk: **{comp_res.lowest_risk.county_name}** ({comp_res.lowest_risk.risk_score}%)"
            )

        st.divider()
        default_reg = county_meta.get("region", KENYA_REGIONS[0])
        selected_region = st.selectbox(
            "Regional Aggregation (8 Kenyan Administrative Regions)",
            options=KENYA_REGIONS,
            index=KENYA_REGIONS.index(default_reg) if default_reg in KENYA_REGIONS else 0,
        )
        reg_res = client.get_region_summary(selected_region, month=selected_month)
        r1, r2, r3 = st.columns(3)
        r1.metric("Region", reg_res.region_name)
        r2.metric("Counties in Region", reg_res.county_count)
        r3.metric("Regional Mean Risk", f"{reg_res.average_risk:.1f}% ({reg_res.risk_level})")

        reg_df = pd.DataFrame([
            {
                "County": c.county_name,
                "Risk Score (%)": c.risk_score,
                "Risk Tier": c.risk_level,
                "Primary TreeSHAP Driver": c.main_driver,
            }
            for c in sorted(reg_res.counties, key=lambda x: x.risk_score, reverse=True)
        ])
        st.dataframe(reg_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Right Column: Gria Agentic AI Hub (Simplify, Upload & Compare, Interactive Chat)
# ---------------------------------------------------------------------------
with gria_col:
    st.markdown("## 🤖 Gria Agentic AI Hub")
    st.caption(
        "1. Simplifies LightGBM & SHAP outputs into everyday language • "
        "2. Reads, converts & compares uploaded files against the model baseline • "
        "3. Interactive County AI Chat"
    )

    # ---- 1. GRIA PLAIN-LANGUAGE MODEL SIMPLIFIER ----
    with st.expander("📖 1. Gria's Plain-English Explanation of Current Output", expanded=True):
        st.markdown(
            active_pred.plain_summary
            or explain_data.plain_explanation
        )

    # ---- 2. UPLOAD, CONVERT & COMPARE YOUR DATA AGAINST THE MODEL ----
    with st.expander("📂 2. Upload, Convert & Compare Your Data vs. Model", expanded=True):
        st.caption(
            "Upload **CSV, Excel (.xlsx), PDF, Word (.docx), or Satellite/Canopy Images**. "
            "Gria automatically extracts & converts your data into the **16-feature Champion Model schema**, "
            "scores it with LightGBM + TreeSHAP, compares it against the county's official baseline, "
            "and draws actionable recommendations."
        )

        # Provide a 1-click sample CSV template pre-filled with the active county's fields so users can test immediately
        sample_csv = (
            "county,month,rainfall_mm,rain_3m_sum,rainfall_anomaly,temp_mean_c,soil_moisture,ndvi_lag1,forage_dryness_index\n"
            f"{selected_county},2,{max(5.0, round(rain_mm * 0.45, 1))},{max(20.0, round(feats.get('rain_3m_sum', 120.0) * 0.5, 1))},"
            f"-42.5,{round(temp_val + 2.5, 1)},{max(0.06, round(soil_m - 0.08, 3))},{max(0.18, round(ndvi_val - 0.11, 3))},{round(fdi_val + 0.35, 2)}\n"
        )
        st.download_button(
            label=f"⬇️ Download Sample {selected_county} Field CSV Template",
            data=sample_csv.encode("utf-8"),
            file_name=f"{selected_county.lower().replace(' ', '_')}_field_observation.csv",
            mime="text/csv",
            use_container_width=True,
        )

        uploaded_file = st.file_uploader(
            "Drop Field CSV, Excel, PDF, DOCX, or Image",
            type=["csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"],
            key="gria_uploader",
        )
        if uploaded_file is not None:
            up_res: UploadResult = client.upload_file(
                uploaded_file.name,
                uploaded_file.getvalue(),
                mime_type=uploaded_file.type or "application/octet-stream",
            )
            st.session_state.last_upload_result = up_res
            st.session_state.uploaded_name = up_res.file_name
            st.session_state.uploaded_context = (
                f"{up_res.comparison_narrative or up_res.gria_summary} "
                f"Suggestions: {' | '.join(up_res.suggestions)}"
            )

            u1, u2 = st.columns(2)
            base_s = (
                up_res.baseline_risk_score
                if up_res.baseline_risk_score is not None
                else float(active_pred.risk_score)
            )
            delta_s = (
                up_res.score_delta_vs_baseline
                if up_res.score_delta_vs_baseline is not None
                else (up_res.risk_score - base_s)
            )
            u1.metric(
                "Uploaded Data Risk",
                f"{up_res.risk_score:.0f}% ({up_res.risk_level})",
                delta=f"{delta_s:+.0f}% vs. Baseline",
                delta_color="inverse",
            )
            u2.metric(
                "Official County Baseline",
                f"{base_s:.0f}% ({up_res.baseline_risk_level or active_pred.risk_level})",
            )

            st.plotly_chart(
                render_upload_comparison_chart(up_res, active_pred),
                use_container_width=True,
                config={"displayModeBar": False},
            )

            st.markdown("**🔍 Gria's Data Conversion & Comparison Summary:**")
            st.markdown(up_res.comparison_narrative or up_res.gria_summary)

            if up_res.suggestions:
                st.markdown("**💡 Gria's Recommendations & Action Items from Your File:**")
                for item in up_res.suggestions:
                    st.markdown(f"- {item}")

            if up_res.converted_features:
                with st.expander("🔢 View Converted 16-Feature Champion Vector"):
                    conv_df = pd.DataFrame([
                        {
                            "Feature": k,
                            "Uploaded (Converted)": round(float(v), 4),
                            "County Baseline": round(float((active_pred.features or {}).get(k, 0.0)), 4),
                        }
                        for k, v in up_res.converted_features.items()
                    ])
                    st.dataframe(conv_df, use_container_width=True, hide_index=True)

    # ---- 3. INTERACTIVE CHAT WITH GRIA ----
    st.markdown("#### 💬 3. Chat & Interact with Gria AI")
    st.caption("Click a quick question below or type any question about counties, SHAP drivers, or your uploaded file:")

    q_col1, q_col2 = st.columns(2)
    quick_prompt: Optional[str] = None
    with q_col1:
        if st.button("🗣️ Simplify County Prediction", use_container_width=True):
            quick_prompt = (
                f"Please explain {selected_county} County's prediction ({active_pred.risk_score}% {active_pred.risk_level}) "
                f"and its top SHAP drivers in simple everyday language for local farmers."
            )
    with q_col2:
        if st.button("📊 Compare Uploaded vs Model", use_container_width=True):
            if st.session_state.last_upload_result is not None:
                quick_prompt = (
                    f"Compare my uploaded file ({st.session_state.uploaded_name}) against {selected_county}'s "
                    f"official model output and give me your top crop and livestock recommendations."
                )
            else:
                quick_prompt = (
                    f"What are the most important actions crop and livestock farmers in {selected_county} "
                    f"should take right now based on the model's SHAP drivers?"
                )

    chat_box = st.container(height=360)
    with chat_box:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    typed_prompt = st.chat_input(f"Ask Gria about {selected_county}, SHAP drivers, or your uploaded data...")
    user_prompt = quick_prompt or typed_prompt

    if user_prompt:
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with chat_box:
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Gria is analyzing LightGBM + TreeSHAP telemetry..."):
                    gria_reply = client.chat_with_gria(
                        message=user_prompt,
                        county_name=selected_county,
                        month=selected_month,
                        document_context=st.session_state.uploaded_context,
                        document_name=st.session_state.uploaded_name,
                    )
                    st.markdown(gria_reply.reply)
        st.session_state.chat_history.append(
            {"role": "assistant", "content": gria_reply.reply}
        )
