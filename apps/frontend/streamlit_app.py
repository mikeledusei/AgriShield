"""AgriShield executive dashboard and predictive intelligence console."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

import altair as alt
import pandas as pd
import requests
import streamlit as st

try:
    import pydeck as pdk
except Exception:  # pragma: no cover
    pdk = None

from shared import api_client
from shared.kenya_counties import (
    KENYA_COUNTIES,
    REGIONS,
    get_county_coords,
    normalize_county_name,
)
from shared.ui_helpers import (
    RISK_COLORS,
    ensure_session_defaults,
    format_markdown_to_html,
    format_model_label,
    render_empty_state,
    render_error_state,
    render_metric,
    risk_label_from_score,
    summary_badge,
)

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
GEOJSON_PATH = ASSETS_DIR / "kenya_counties.geojson"

st.set_page_config(
    page_title="AgriShield · Kenya Agricultural Risk Intelligence",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Unified, WCAG 2.1 AA compliant stylesheet (no duplicate style blocks)
st.markdown(
    """
    <style>
        .stApp { max-width: 100%; overflow-x: hidden; }
        .block-container {
            padding-top: 1.1rem;
            padding-left: 1.4rem;
            padding-right: 1.4rem;
            max-width: 1600px;
        }
        .agri-kpi-card {
            padding: 1rem 1.15rem;
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 14px;
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.86), rgba(30, 41, 59, 0.72));
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.16);
            transition: transform 0.15s ease, border-color 0.15s ease;
        }
        .agri-kpi-card:hover {
            transform: translateY(-2px);
            border-color: rgba(45, 212, 191, 0.45);
        }
        .agri-kpi-title {
            color: #cbd5e1;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .agri-kpi-value {
            font-weight: 800;
            font-size: 1.65rem;
            margin-top: 0.25rem;
            line-height: 1.2;
        }
        .agri-driver-card {
            padding: 1.05rem 1.25rem;
            border-radius: 14px;
            background: rgba(15, 23, 42, 0.78);
            border: 1px solid rgba(148, 163, 184, 0.22);
            margin: 0.75rem 0 1rem 0;
        }
        .wa-shell {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 22px;
            overflow: hidden;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.25);
            margin-top: 0.5rem;
        }
        .wa-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            padding: 0.9rem 1.1rem;
            border-bottom: 1px solid rgba(148, 163, 184, 0.16);
        }
        .wa-header-left {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .wa-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #16a34a, #0d9488);
            color: #ffffff;
            font-size: 1.05rem;
            font-weight: 700;
        }
        .wa-contact {
            font-size: 1.02rem;
            font-weight: 700;
            color: #f8fafc;
        }
        .wa-status {
            font-size: 0.74rem;
            color: #86efac;
            letter-spacing: 0.03em;
        }
        .wa-messages {
            background-color: #0b1220;
            min-height: 400px;
            max-height: 600px;
            overflow-y: auto;
            padding: 1rem 0.95rem;
        }
        .wa-row {
            display: flex;
            margin: 0.55rem 0;
        }
        .wa-row.user { justify-content: flex-end; }
        .wa-row.ai, .wa-row.assistant { justify-content: flex-start; }
        .wa-bubble {
            max-width: 78%;
            padding: 0.8rem 0.95rem 0.55rem;
            border-radius: 18px;
            position: relative;
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.16);
        }
        .wa-row.user .wa-bubble {
            background: linear-gradient(135deg, #065f46, #0f766e);
            color: #f0fdfa;
            border-bottom-right-radius: 6px;
        }
        .wa-row.ai .wa-bubble, .wa-row.assistant .wa-bubble {
            background: rgba(30, 41, 59, 0.96);
            color: #f1f5f9;
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-bottom-left-radius: 6px;
        }
        .wa-message-body {
            line-height: 1.65;
            white-space: normal;
            word-wrap: break-word;
            font-size: 0.94rem;
        }
        .wa-message-body strong { color: #ffffff; }
        .wa-meta {
            display: flex;
            justify-content: flex-end;
            gap: 0.45rem;
            font-size: 0.68rem;
            color: #cbd5e1;
            margin-top: 0.4rem;
        }
        .wa-row.ai .wa-meta, .wa-row.assistant .wa-meta {
            justify-content: flex-start;
        }
        @media (max-width: 768px) {
            .block-container { padding-left: 0.6rem; padding-right: 0.6rem; }
            .wa-bubble { max-width: 92%; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_api_call(
    func: Callable[[], Any],
    error_message: str,
    show_error: bool = True,
    retry_key: str | None = None,
) -> Any | None:
    """Execute a backend API call with structured error display."""
    try:
        return func()
    except requests.exceptions.HTTPError as exc:
        detail = "Unexpected HTTP error returned by backend."
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        logger.warning("%s: %s", error_message, detail)
        if show_error:
            render_error_state(error_message, str(detail), retry_key=retry_key)
    except requests.exceptions.RequestException as exc:
        logger.warning("%s: Backend unavailable. %s", error_message, exc)
        if show_error:
            render_error_state(
                error_message,
                "Could not reach the AgriShield FastAPI backend. Ensure the server is running on BACKEND_URL.",
                retry_key=retry_key,
            )
    except Exception as exc:
        logger.warning("%s: %s", error_message, exc)
        if show_error:
            render_error_state(error_message, str(exc), retry_key=retry_key)
    return None


@st.cache_data(ttl=60, show_spinner=False)
def cached_health() -> dict[str, Any] | None:
    return api_client.health()


@st.cache_data(ttl=120, show_spinner=False)
def cached_counties() -> list[str]:
    counties = api_client.get_available_counties()
    if counties:
        normalized = {normalize_county_name(c) for c in counties if c}
        return sorted(normalized)
    return list(KENYA_COUNTIES)


@st.cache_data(ttl=60, show_spinner=False)
def cached_batch_predictions() -> dict[str, Any]:
    return api_client.get_batch_predictions()


@st.cache_data(ttl=300, show_spinner=False)
def load_kenya_geojson() -> dict[str, Any] | None:
    """Load the 47-county GeoJSON boundary polygons if available."""
    if not GEOJSON_PATH.exists() or GEOJSON_PATH.stat().st_size == 0:
        return None
    try:
        return json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not load kenya_counties.geojson: %s", exc)
        return None


def get_counties() -> list[str]:
    """Return strictly the 47 canonical Kenyan counties without duplicates."""
    try:
        return cached_counties()
    except Exception:
        return list(KENYA_COUNTIES)


def get_default_county() -> str:
    counties = get_counties()
    for candidate in ("Bungoma", "Nakuru", "Uasin Gishu", "Kajiado", "Turkana"):
        if candidate in counties:
            return candidate
    return counties[0] if counties else "Bungoma"


def risk_color(level: str) -> str:
    return RISK_COLORS.get(str(level).upper(), "#22c55e")


def render_sidebar() -> None:
    with st.sidebar:
        st.title("🌾 AgriShield")
        st.caption("Hierarchical AI Early Warning System · 47 Kenyan Counties")

        health_data = safe_api_call(cached_health, "Backend health check failed", show_error=False)
        if health_data and health_data.get("status") == "healthy":
            model_tag = format_model_label(health_data.get("model_name"))
            st.success(f"🟢 API Online · {model_tag}")
        else:
            st.warning("🟠 Backend Offline · Check BACKEND_URL")

        st.markdown("---")
        st.subheader("📍 Global Context")

        counties = get_counties()
        current_county = normalize_county_name(st.session_state.get("selected_county"))
        default_county = current_county if current_county in counties else get_default_county()
        county_index = counties.index(default_county) if default_county in counties else 0
        selected_county = st.selectbox(
            "County (All 47 Counties)",
            counties,
            index=county_index,
            help="Select any of Kenya's 47 counties for localized risk intelligence.",
        )
        st.session_state["selected_county"] = selected_county

        region_default = (
            st.session_state.get("selected_region")
            if st.session_state.get("selected_region") in REGIONS
            else "Rift Valley"
        )
        region_index = REGIONS.index(region_default)
        region = st.selectbox(
            "Region",
            REGIONS,
            index=region_index,
            help="Filter regional aggregation across Kenya's 8 administrative regions.",
        )
        st.session_state["selected_region"] = region

        focus_options = ["combined", "crops", "livestock"]
        current_focus = st.session_state.get("selected_focus", "combined")
        focus_idx = focus_options.index(current_focus) if current_focus in focus_options else 0
        selected_focus = st.selectbox(
            "Agricultural Focus",
            focus_options,
            index=focus_idx,
            help="Tailor advisory recommendations for crop yield, livestock forage, or combined resilience.",
        )
        st.session_state["selected_focus"] = selected_focus

        st.markdown("---")
        if st.button("🔄 Refresh Live Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


def apply_light_chart_theme(chart: alt.Chart) -> alt.Chart:
    return (
        chart.properties(background="#ffffff")
        .configure_title(color="#0f172a", fontSize=14, anchor="start")
        .configure_axis(
            labelColor="#334155",
            titleColor="#0f172a",
            gridColor="#e2e8f0",
            domainColor="#cbd5e1",
        )
        .configure_legend(labelColor="#334155", titleColor="#0f172a")
        .configure_view(strokeWidth=0)
    )


def render_light_bar_chart(
    data: pd.DataFrame,
    x_field: str,
    y_field: str,
    title: str | None = None,
    color: str = "#0d9488",
) -> None:
    if data.empty:
        render_empty_state("No Chart Data", "No records available to plot.", "📊")
        return
    chart = (
        alt.Chart(data)
        .mark_bar(color=color, cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X(f"{x_field}:N", sort="-y", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y(f"{y_field}:Q", title="Risk Score", axis=alt.Axis(grid=True)),
            tooltip=[x_field, y_field],
        )
    )
    if title:
        chart = chart.properties(title=title, height=320)
    st.altair_chart(apply_light_chart_theme(chart), use_container_width=True)


def render_light_line_chart(
    data: pd.DataFrame,
    x_field: str,
    y_field: str,
    title: str | None = None,
) -> None:
    if data.empty:
        render_empty_state("No Historical Trend", "No historical observations available yet.", "📈")
        return
    chart = (
        alt.Chart(data)
        .mark_line(color="#0284c7", point=alt.OverlayMarkDef(color="#0284c7", size=60), strokeWidth=3)
        .encode(
            x=alt.X(f"{x_field}:T", axis=alt.Axis(title="Month")),
            y=alt.Y(
                f"{y_field}:Q",
                scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(title="Risk Score (0–100)", grid=True),
            ),
            tooltip=[x_field, y_field],
        )
    )
    if title:
        chart = chart.properties(title=title, height=300)
    st.altair_chart(apply_light_chart_theme(chart), use_container_width=True)


def render_light_map(df_map: pd.DataFrame) -> None:
    """Render an interactive 47-county GeoJSON choropleth + centroid layer using PyDeck."""
    if df_map.empty:
        render_empty_state("Map Unavailable", "No county coordinates available to render.", "🗺️")
        return

    if pdk is not None:
        color_lookup = {
            "SAFE": [34, 197, 94, 175],
            "MODERATE": [250, 204, 21, 185],
            "HIGH": [249, 115, 22, 200],
            "CRITICAL": [239, 68, 68, 215],
        }
        data = df_map.copy()
        data["fill_color"] = (
            data["risk_level"]
            .map(color_lookup)
            .apply(lambda x: x if isinstance(x, list) else [34, 197, 94, 175])
        )

        layers: list[Any] = []
        geojson_obj = load_kenya_geojson()
        if geojson_obj and "features" in geojson_obj:
            score_by_county = {
                normalize_county_name(r["county"]): (int(r["risk_score"]), str(r["risk_level"]))
                for _, r in data.iterrows()
            }
            enriched_features = []
            for feat in geojson_obj.get("features", []):
                props = dict(feat.get("properties") or {})
                c_name = normalize_county_name(
                    props.get("county") or props.get("ADM1_EN") or props.get("name")
                )
                sc, lvl = score_by_county.get(c_name, (10, "SAFE"))
                props["county"] = c_name
                props["risk_score"] = sc
                props["risk_level"] = lvl
                props["fill_color"] = color_lookup.get(lvl, [34, 197, 94, 140])
                enriched_features.append({
                    "type": "Feature",
                    "geometry": feat.get("geometry"),
                    "properties": props,
                })
            layers.append(
                pdk.Layer(
                    "GeoJsonLayer",
                    data={"type": "FeatureCollection", "features": enriched_features},
                    opacity=0.65,
                    stroked=True,
                    filled=True,
                    get_fill_color="properties.fill_color",
                    get_line_color=[15, 23, 42, 200],
                    line_width_min_pixels=1,
                    pickable=True,
                )
            )

        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=data,
                get_position="[lon, lat]",
                get_radius=14000,
                get_fill_color="fill_color",
                get_line_color=[255, 255, 255, 240],
                line_width_min_pixels=1,
                pickable=True,
            )
        )

        deck = pdk.Deck(
            map_style="light",
            initial_view_state=pdk.ViewState(
                latitude=0.35,
                longitude=37.6,
                zoom=5.35,
                pitch=0,
            ),
            layers=layers,
            tooltip={"text": "{county}\nRisk Score: {risk_score}/100 ({risk_level})"},
        )
        st.pydeck_chart(deck, use_container_width=True)
        return

    st.map(df_map[["lat", "lon"]], size=5, use_container_width=True)


def build_gria_farm_summary(payload: dict[str, Any], county_name: str | None = None) -> str:
    if not payload:
        return "Gria AI could not generate a summary because no live risk data was returned from the backend."

    score = int(round(float(payload.get("risk_score", 0) or 0)))
    level = (payload.get("risk_level") or risk_label_from_score(score)).upper()
    driver = payload.get("main_driver") or "agro-climatic baseline conditions"
    recommendation = payload.get("recommendation") or "Monitor conditions closely and act early."
    target_name = county_name or payload.get("county_name") or "This county"
    return (
        f"**{target_name} County** is currently at **{level}** risk (**{score}/100**). "
        f"The primary indicator driving this assessment is **{driver}**. "
        f"**Recommended Action:** {recommendation}"
    )


def render_ai_insight_panel(title: str, body_text: str) -> None:
    formatted_body = format_markdown_to_html(body_text)
    st.markdown(
        f"""
        <div role="region" aria-label="{title}" style="padding: 1.05rem 1.25rem; border-radius: 16px; background: linear-gradient(135deg, rgba(15,118,110,0.18), rgba(30,41,59,0.88)); border: 1px solid rgba(45,212,191,0.35); margin-top: 0.5rem;">
            <div style="font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #99f6e4; margin-bottom: 0.45rem;">🤖 {title}</div>
            <div style="font-size: 0.98rem; line-height: 1.7; color: #f1f5f9;">{formatted_body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview() -> None:
    county = st.session_state.get("selected_county") or get_default_county()
    focus = st.session_state.get("selected_focus") or "combined"
    st.header(f"📊 County Risk Overview — {county}")

    with st.spinner(f"Running LightGBM Champion inference for {county}..."):
        prediction = safe_api_call(
            lambda: api_client.predict_county(county, focus=focus),
            f"Prediction failed for {county}",
            retry_key="retry_overview_pred",
        )
    if not prediction:
        return

    risk_score = int(round(float(prediction.get("risk_score", 0) or 0)))
    level = (prediction.get("risk_level") or risk_label_from_score(risk_score)).upper()
    obs_month = prediction.get("month") or "2025-12"
    model_label = format_model_label(prediction.get("model_used"))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric("Risk Score", f"{risk_score} / 100", color=risk_color(level), subtitle=f"Observation: {obs_month}")
    with c2:
        render_metric("Risk Level", level, color=risk_color(level), subtitle=f"Region: {prediction.get('region') or 'Kenya'}")
    with c3:
        render_metric("Agricultural Focus", (prediction.get("focus") or focus).capitalize(), color="#38bdf8", subtitle="Crop & Forage Profile")
    with c4:
        render_metric("Scoring Engine", model_label, color="#c084fc", subtitle="2015–2025 Trained Artifact")

    st.markdown(
        f"""
        <div class="agri-driver-card">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                <div><strong>Primary Agro-Climatic Driver:</strong> {prediction.get('main_driver', 'Not available')}</div>
                <div>{summary_badge(level)}</div>
            </div>
            <div style="margin-top:0.55rem; color:#e2e8f0;">
                <strong>Actionable Recommendation:</strong> {prediction.get('recommendation', 'No recommendation available.')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.spinner("Loading national 47-county risk matrix..."):
        batch = safe_api_call(
            cached_batch_predictions,
            "Batch predictions failed",
            retry_key="retry_overview_batch",
        )
    if batch:
        rows = batch.get("counties", [])
        if rows:
            df_map = pd.DataFrame([
                {
                    "county": normalize_county_name(item.get("county_name")),
                    "risk_score": float(item.get("risk_score", 0) or 0),
                    "risk_level": (
                        item.get("risk_level")
                        or risk_label_from_score(item.get("risk_score", 0))
                    ).upper(),
                    "lat": get_county_coords(item.get("county_name"))["lat"],
                    "lon": get_county_coords(item.get("county_name"))["lon"],
                }
                for item in rows
            ])

            st.subheader("🗺️ National 47-County Risk Map (GeoJSON Choropleth)")
            render_light_map(df_map)

            risk_counts = (
                df_map["risk_level"]
                .value_counts()
                .reindex(["SAFE", "MODERATE", "HIGH", "CRITICAL"], fill_value=0)
            )
            chart_df = pd.DataFrame({
                "risk_level": risk_counts.index,
                "count": risk_counts.values,
            })
            left, right = st.columns(2)
            with left:
                st.subheader("National Risk Distribution (47 Counties)")
                render_light_bar_chart(
                    chart_df,
                    "risk_level",
                    "count",
                    title="Counties by Risk Tier",
                )
            with right:
                st.subheader("Gria AI Executive Brief")
                render_ai_insight_panel(
                    "Farmer & County Officer Guidance",
                    build_gria_farm_summary(prediction, county),
                )

    history = safe_api_call(
        lambda: api_client.get_county_history(county, months=12),
        f"History failed for {county}",
        show_error=False,
    )
    if history and history.get("trend"):
        trend_df = pd.DataFrame(history["trend"])
        trend_df["date"] = pd.to_datetime(trend_df["date"])
        st.subheader(f"📈 12-Month Risk Trajectory — {county}")
        render_light_line_chart(
            trend_df[["date", "risk_score"]],
            "date",
            "risk_score",
            title=f"{county} Monthly Risk Score (Last 12 Months)",
        )


def render_compare() -> None:
    st.header("⚖️ Multi-County Risk Comparison")
    st.caption("Compare current drought and forage risk scores side-by-side across up to 10 Kenyan counties.")
    counties = get_counties()
    default_picks = [c for c in ("Turkana", "Kajiado", "Uasin Gishu", "Nakuru") if c in counties]
    selected = st.multiselect(
        "Select between 2 and 10 counties to compare",
        counties,
        default=default_picks[:3] if len(default_picks) >= 2 else counties[:3],
        max_selections=10,
    )
    if len(selected) < 2:
        st.info("Please select at least 2 counties above to run a side-by-side comparison.")
        return

    if st.button("⚖️ Compare Selected Counties", type="primary"):
        with st.spinner("Comparing counties with LightGBM Champion model..."):
            result = safe_api_call(
                lambda: api_client.compare_counties(selected),
                "County comparison failed",
                retry_key="retry_compare",
            )
        if result:
            st.session_state["last_compare_result"] = result

    result = st.session_state.get("last_compare_result")
    if result:
        ranked = result.get("counties", [])
        if ranked:
            highest = result.get("highest_risk")
            lowest = result.get("lowest_risk")
            if highest and lowest:
                c1, c2 = st.columns(2)
                with c1:
                    h_lvl = highest.get("risk_level", "SAFE")
                    render_metric(
                        f"Highest Risk · {highest.get('county_name')}",
                        f"{highest.get('risk_score')}/100 ({h_lvl})",
                        color=risk_color(h_lvl),
                        subtitle=f"Driver: {highest.get('main_driver', 'N/A')}",
                    )
                with c2:
                    l_lvl = lowest.get("risk_level", "SAFE")
                    render_metric(
                        f"Lowest Risk · {lowest.get('county_name')}",
                        f"{lowest.get('risk_score')}/100 ({l_lvl})",
                        color=risk_color(l_lvl),
                        subtitle=f"Driver: {lowest.get('main_driver', 'N/A')}",
                    )

            df = pd.DataFrame([
                {
                    "county": item.get("county_name"),
                    "region": item.get("region") or "Kenya",
                    "risk_score": int(round(float(item.get("risk_score", 0) or 0))),
                    "risk_level": (
                        item.get("risk_level")
                        or risk_label_from_score(item.get("risk_score", 0))
                    ).upper(),
                    "main_driver": item.get("main_driver") or "",
                }
                for item in ranked
            ])
            st.subheader("Ranked County Comparison")
            render_light_bar_chart(
                df.rename(columns={"risk_score": "score"}),
                "county",
                "score",
                title="County Risk Score Comparison",
            )
            st.dataframe(df, use_container_width=True)


def render_region() -> None:
    st.header("🌍 Regional Risk Aggregation")
    st.caption("Evaluate aggregated risk across Kenya's 8 regions and inspect every constituent county.")
    current_reg = st.session_state.get("selected_region", "Rift Valley")
    reg_idx = REGIONS.index(current_reg) if current_reg in REGIONS else 0
    region = st.selectbox("Select Administrative Region", REGIONS, index=reg_idx, key="region_tab_select")
    st.session_state["selected_region"] = region

    with st.spinner(f"Aggregating county predictions for {region}..."):
        result = safe_api_call(
            lambda: api_client.get_region_aggregation(region),
            f"Region summary failed for {region}",
            retry_key="retry_region",
        )
    if result:
        avg = float(result.get("average_risk", 0) or 0)
        level = (result.get("risk_level") or risk_label_from_score(avg)).upper()
        c_count = int(result.get("county_count", 0) or 0)
        c1, c2, c3 = st.columns(3)
        with c1:
            render_metric("Regional Average Risk", f"{avg:.1f} / 100", color=risk_color(level))
        with c2:
            render_metric("Regional Risk Tier", level, color=risk_color(level))
        with c3:
            render_metric("Counties in Region", str(c_count), color="#38bdf8")

        counties = result.get("counties", [])
        if counties:
            df = pd.DataFrame([
                {
                    "county": item.get("county_name"),
                    "risk_score": int(round(float(item.get("risk_score", 0) or 0))),
                    "risk_level": (
                        item.get("risk_level")
                        or risk_label_from_score(item.get("risk_score", 0))
                    ).upper(),
                    "main_driver": item.get("main_driver") or "",
                    "focus": item.get("focus") or "",
                }
                for item in counties
            ])
            render_light_bar_chart(
                df.rename(columns={"risk_score": "score"}),
                "county",
                "score",
                title=f"{region} Region — County Risk Scores",
            )
            st.dataframe(df, use_container_width=True)


def render_scenario() -> None:
    county = st.session_state.get("selected_county") or get_default_county()
    st.header(f"🎛️ Climate & Forage Shock Simulator — {county}")
    st.caption(
        "Simulate how perturbations in 30-Day Rainfall Anomaly, Temperature, and MODIS NDVI "
        "impact the LightGBM Champion risk score and Forage Dryness Index."
    )

    p1, p2, p3 = st.columns(3)
    with p1:
        if st.button("☀️ Severe Drought (-50% Rain, +3°C, -0.15 NDVI)", use_container_width=True):
            st.session_state["scen_rain"] = -50.0
            st.session_state["scen_temp"] = 3.0
            st.session_state["scen_ndvi"] = -0.15
    with p2:
        if st.button("🌤️ Moderate Deficit (-25% Rain, +1.5°C, -0.08 NDVI)", use_container_width=True):
            st.session_state["scen_rain"] = -25.0
            st.session_state["scen_temp"] = 1.5
            st.session_state["scen_ndvi"] = -0.08
    with p3:
        if st.button("🌧️ Favorable Rains (+30% Rain, -1.0°C, +0.10 NDVI)", use_container_width=True):
            st.session_state["scen_rain"] = 30.0
            st.session_state["scen_temp"] = -1.0
            st.session_state["scen_ndvi"] = 0.10

    s1, s2, s3 = st.columns(3)
    with s1:
        rainfall = st.slider(
            "Rainfall Change (%)",
            min_value=-100.0,
            max_value=100.0,
            value=float(st.session_state.get("scen_rain", -30.0)),
            step=5.0,
        )
    with s2:
        temp = st.slider(
            "Temperature Shift (°C)",
            min_value=-10.0,
            max_value=10.0,
            value=float(st.session_state.get("scen_temp", 2.0)),
            step=0.5,
        )
    with s3:
        ndvi = st.slider(
            "NDVI Vegetation Shock",
            min_value=-0.40,
            max_value=0.40,
            value=float(st.session_state.get("scen_ndvi", -0.10)),
            step=0.02,
        )

    if st.button("🚀 Run Scenario Simulation", type="primary"):
        with st.spinner(f"Simulating agro-climatic shock for {county}..."):
            result = safe_api_call(
                lambda: api_client.scenario_analysis(
                    county,
                    rainfall_change_pct=rainfall,
                    temp_change_c=temp,
                    ndvi_shock=ndvi,
                ),
                f"Scenario failed for {county}",
                retry_key="retry_scenario",
            )
        if result:
            original = result.get("original", {})
            scenario = result.get("scenario", {})
            original_score = int(round(float(original.get("risk_score", 0) or 0)))
            scenario_score = int(round(float(scenario.get("risk_score", 0) or 0)))
            o_lvl = (original.get("risk_level") or risk_label_from_score(original_score)).upper()
            s_lvl = (scenario.get("risk_level") or risk_label_from_score(scenario_score)).upper()
            delta = int(result.get("score_delta", scenario_score - original_score) or 0)
            delta_color = "#f87171" if delta > 0 else "#22c55e" if delta < 0 else "#38bdf8"

            c1, c2, c3 = st.columns(3)
            with c1:
                render_metric(
                    "Baseline Risk",
                    f"{original_score} / 100 ({o_lvl})",
                    color=risk_color(o_lvl),
                    subtitle=f"Driver: {original.get('main_driver', 'N/A')}",
                )
            with c2:
                render_metric(
                    "Simulated Risk",
                    f"{scenario_score} / 100 ({s_lvl})",
                    color=risk_color(s_lvl),
                    subtitle=f"Driver: {scenario.get('main_driver', 'N/A')}",
                )
            with c3:
                render_metric(
                    "Net Risk Shift (Delta)",
                    f"{delta:+d} pts",
                    color=delta_color,
                    subtitle=f"Engine: {format_model_label(scenario.get('model_used'))}",
                )

            st.markdown(f"**Simulation Narrative:** {result.get('narrative', 'No narrative generated.')}")
            render_ai_insight_panel(
                "Scenario Advisory & Contingency Plan",
                build_gria_farm_summary(scenario, county),
            )


def render_reports() -> None:
    county = st.session_state.get("selected_county") or get_default_county()
    st.header(f"📑 Executive PDF Reports — {county}")
    st.caption("Generate and download branded county drought early warning briefs for field officers and policymakers.")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        report_type = st.selectbox(
            "Report Focus Type",
            ["combined", "crops", "livestock"],
            index=0,
        )
    with col_b:
        detailed = st.checkbox("Include Methodology & Model Notes", value=True)

    if st.button("📄 Generate County PDF Report", type="primary"):
        with st.spinner(f"Compiling PDF report for {county}..."):
            result = safe_api_call(
                lambda: api_client.create_report(
                    county,
                    report_type=report_type,
                    detailed=detailed,
                ),
                "Report creation failed",
                retry_key="retry_report_create",
            )
        if result:
            st.session_state["last_report_id"] = result.get("id")
            st.session_state["last_report_county"] = county
            st.success(f"Report #{result.get('id')} created for {county}!")

    if st.session_state.get("last_report_id"):
        rep_id = st.session_state["last_report_id"]
        rep_county = st.session_state.get("last_report_county", county).replace(" ", "_")
        pdf_bytes = safe_api_call(
            lambda: api_client.download_report_pdf(rep_id),
            "Report PDF download failed",
            retry_key="retry_report_pdf",
        )
        if pdf_bytes is not None:
            st.download_button(
                f"⬇️ Download PDF Report (#{rep_id} · {county})",
                data=pdf_bytes,
                file_name=f"AgriShield_Report_{rep_county}_{rep_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    report_list = safe_api_call(
        lambda: api_client.list_reports(limit=10),
        "Failed to load recent reports",
        show_error=False,
    )
    if report_list:
        rows = report_list.get("reports", [])
        if rows:
            st.subheader("Recent Report History")
            report_df = pd.DataFrame([
                {
                    "ID": row.get("id"),
                    "County ID": row.get("county_id"),
                    "Focus Type": row.get("report_type"),
                    "Detailed": row.get("detailed"),
                    "Created At": row.get("created_at"),
                }
                for row in rows
            ])
            st.dataframe(report_df, use_container_width=True)
        else:
            render_empty_state(
                "No Reports Generated Yet",
                "Click 'Generate County PDF Report' above to create your first downloadable PDF brief.",
                "📑",
            )


def render_gria() -> None:
    county = st.session_state.get("selected_county") or get_default_county()
    st.header(f"🤖 Gria Agentic AI Advisor — {county}")
    st.caption(
        "Ask Gria about county drought risk, crop yield outlook, livestock forage dryness, "
        "or upload a field report (CSV, Excel, PDF, Word, or crop/pasture photo) for instant analysis."
    )

    if "gria_history" not in st.session_state:
        st.session_state["gria_history"] = []

    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button(f"🌾 Summarize {county} risk", use_container_width=True):
            prediction = safe_api_call(
                lambda: api_client.predict_county(county, focus="combined"),
                f"Prediction failed for {county}",
            )
            if prediction:
                summary = build_gria_farm_summary(prediction, county)
                st.session_state["gria_history"].append(
                    {"role": "assistant", "content": summary, "time": "just now"}
                )
                st.rerun()
    with q2:
        if st.button("🐄 Livestock forage guidance", use_container_width=True):
            payload = safe_api_call(
                lambda: api_client.chat_with_gria(
                    f"What is the livestock forage risk and recommended action for {county}?",
                    county_name=county,
                ),
                "Gria request failed",
            )
            if payload:
                st.session_state["gria_history"].append(
                    {"role": "user", "content": f"What is the livestock forage risk for {county}?", "time": "just now"}
                )
                st.session_state["gria_history"].append(
                    {"role": "assistant", "content": payload.get("reply", ""), "time": "just now"}
                )
                st.rerun()
    with q3:
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state["gria_history"] = []
            st.rerun()

    wa_messages = []
    if st.session_state.get("gria_history"):
        for item in st.session_state["gria_history"]:
            sender = item.get("role", "assistant")
            bubble = format_markdown_to_html(item.get("content", ""))
            time_str = item.get("time") or "now"
            status_tag = "You ✓✓" if sender == "user" else "Gria AI"
            wa_messages.append(
                f'<div class="wa-row {sender}"><div class="wa-bubble">'
                f'<div class="wa-message-body">{bubble}</div>'
                f'<div class="wa-meta"><span>{status_tag}</span><span>{time_str}</span></div>'
                f"</div></div>"
            )
    else:
        wa_messages.append(
            '<div class="wa-row assistant"><div class="wa-bubble">'
            f'<div class="wa-message-body">Hello! I am <strong>Gria AI</strong>, your agricultural intelligence advisor for <strong>{county} County</strong>. '
            'Use the quick actions above, type a question below, or attach a field spreadsheet/PDF/image for analysis.</div>'
            '<div class="wa-meta"><span>Gria AI</span><span>ready</span></div>'
            "</div></div>"
        )

    st.markdown(
        f"""
        <div class="wa-shell" role="log" aria-label="Gria AI conversation history">
            <div class="wa-header">
                <div class="wa-header-left">
                    <div class="wa-avatar" aria-hidden="true">🤖</div>
                    <div>
                        <div class="wa-contact">Gria Agentic AI</div>
                        <div class="wa-status">{county} County • LightGBM Champion v1 Connected</div>
                    </div>
                </div>
            </div>
            <div class="wa-messages">{''.join(wa_messages)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("gria_chat_form", clear_on_submit=True):
        col_attach, col_msg, col_send = st.columns([2.2, 6.3, 1.5])
        with col_attach:
            uploaded_file = st.file_uploader(
                "Attach field file",
                type=["csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"],
                key="gria_upload",
                label_visibility="collapsed",
            )
        with col_msg:
            prompt = st.text_area(
                "Message to Gria AI",
                height=82,
                label_visibility="collapsed",
                placeholder=f"Ask Gria about {county} rainfall anomalies, NDVI pasture health, or mitigation steps...",
                key="gria_prompt",
            )
        with col_send:
            submitted = st.form_submit_button("Send ➤", use_container_width=True, type="primary")

        if uploaded_file is not None:
            st.caption(f"📎 Attached file ready: {uploaded_file.name}")

    if submitted:
        final_prompt = (prompt or "").strip()
        uploaded = st.session_state.get("gria_upload")
        document_context = None
        document_name = None

        if uploaded is not None:
            document_name = uploaded.name
            with st.spinner(f"Analyzing uploaded file '{uploaded.name}'..."):
                upload_result = safe_api_call(
                    lambda: api_client.upload_and_analyze(uploaded.getvalue(), uploaded.name),
                    "Upload analysis failed",
                )
            if upload_result:
                attached_summary = upload_result.get("gria_summary") or "Uploaded file reviewed successfully."
                extracted = upload_result.get("extracted_data") or {}
                document_context = (
                    f"{attached_summary} | Extracted indicators: {json.dumps(extracted)} | "
                    f"Computed risk: {upload_result.get('risk_score')}% ({upload_result.get('risk_level')})"
                )
                if not final_prompt:
                    final_prompt = f"Please explain the agricultural risk findings from my uploaded file ({uploaded.name})."

        if final_prompt:
            st.session_state["gria_history"].append(
                {"role": "user", "content": final_prompt, "time": "just now"}
            )
            with st.spinner("Gria AI is synthesizing county risk intelligence..."):
                payload = safe_api_call(
                    lambda: api_client.chat_with_gria(
                        final_prompt,
                        county,
                        document_context=document_context,
                        document_name=document_name,
                    ),
                    "Gria request failed",
                )
            if payload:
                reply = payload.get("reply", "No response received.")
                st.session_state["gria_history"].append(
                    {"role": "assistant", "content": reply, "time": "just now"}
                )
                st.rerun()


def main() -> None:
    ensure_session_defaults()
    render_sidebar()

    st.title("🌾 AgriShield Intelligence Console")
    st.caption(
        "Hierarchical AI Early Warning System for Crop Yield & Livestock Forage Risk Across All 47 Kenyan Counties (2015–2025)"
    )

    tabs = st.tabs([
        "📊 Overview",
        "⚖️ Compare Counties",
        "🌍 Regional View",
        "🎛️ Scenario Simulator",
        "📑 PDF Reports",
        "🤖 Gria AI Advisor",
    ])

    with tabs[0]:
        render_overview()
    with tabs[1]:
        render_compare()
    with tabs[2]:
        render_region()
    with tabs[3]:
        render_scenario()
    with tabs[4]:
        render_reports()
    with tabs[5]:
        render_gria()


if __name__ == "__main__":
    main()
