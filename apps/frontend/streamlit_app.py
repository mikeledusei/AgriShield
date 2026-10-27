"""AgriShield premium dashboard and monitoring console."""

from __future__ import annotations

import logging
from typing import Any

import altair as alt
import pandas as pd
import requests
import streamlit as st

try:
    import pydeck as pdk
except Exception:  # pragma: no cover
    pdk = None

from shared import api_client
from shared.kenya_counties import COUNTY_LOCATIONS, KENYA_COUNTIES
from shared.ui_helpers import ensure_session_defaults, render_metric, risk_label_from_score

logger = logging.getLogger(__name__)

st.set_page_config(page_title="AgriShield", page_icon="🌾", layout="wide")

st.markdown(
    """
    <style>
        .stApp { max-width: 100%; overflow-x: hidden; }
        .block-container {
            padding-top: 1.0rem;
            padding-left: 1.2rem;
            padding-right: 1.2rem;
            max-width: 1600px;
        }
        div[data-testid="stMetricValue"] { font-size: 1.7rem; }
        .metric-card { background: rgba(15,23,42,0.72); border: 1px solid rgba(148,163,184,0.22); border-radius: 14px; padding: 0.8rem 1rem; }
        .wa-shell {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
            border: 1px solid rgba(148,163,184,0.18);
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 18px 40px rgba(15,23,42,0.25);
        }
        .wa-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            padding: 0.9rem 1rem;
            border-bottom: 1px solid rgba(148,163,184,0.14);
        }
        .wa-header-left {
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .wa-avatar {
            width: 42px;
            height: 42px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #22c55e, #16a34a);
            color: white;
            font-size: 1.1rem;
            font-weight: 700;
        }
        .wa-contact {
            font-size: 1.05rem;
            font-weight: 700;
            color: #f8fafc;
        }
        .wa-status {
            font-size: 0.72rem;
            color: #86efac;
            letter-spacing: 0.03em;
        }
        .wa-header-actions {
            display: flex;
            gap: 0.5rem;
            color: #dbeafe;
            font-size: 1.2rem;
        }
        .wa-messages {
            background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60"><path d="M0 60V0h60v60" fill="none"/><path d="M0 0h60v60" fill="none" stroke="rgba(148,163,184,0.08)" stroke-width="1"/></svg>');
            min-height: 520px;
            max-height: 720px;
            overflow-y: auto;
            padding: 1rem 0.9rem;
            background-color: #0b1220;
        }
        .wa-row {
            display: flex;
            margin: 0.5rem 0;
        }
        .wa-row.user { justify-content: flex-end; }
        .wa-row.ai { justify-content: flex-start; }
        .wa-bubble {
            max-width: 76%;
            padding: 0.72rem 0.9rem 0.5rem 0.9rem;
            border-radius: 18px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
            position: relative;
            box-shadow: 0 6px 16px rgba(15,23,42,0.16);
        }
        .wa-row.user .wa-bubble {
            background: linear-gradient(135deg, #065f46, #0f766e);
            color: #ecfeff;
            border-bottom-right-radius: 6px;
        }
        .wa-row.ai .wa-bubble {
            background: rgba(30,41,59,0.95);
            color: #e2e8f0;
            border: 1px solid rgba(148,163,184,0.18);
            border-bottom-left-radius: 6px;
        }
        .wa-meta {
            display: flex;
            justify-content: flex-end;
            gap: 0.35rem;
            font-size: 0.66rem;
            margin-top: 0.35rem;
            opacity: 0.8;
        }
        .wa-row.ai .wa-meta { justify-content: flex-start; }
        .wa-compose {
            background: #111827;
            border-top: 1px solid rgba(148,163,184,0.15);
            padding: 0.75rem 0.8rem 0.9rem 0.8rem;
        }
        .wa-input-wrap {
            display: flex;
            align-items: flex-end;
            gap: 0.7rem;
        }
        .wa-attach {
            width: 46px;
            height: 46px;
            border-radius: 50%;
            border: 1px solid rgba(148,163,184,0.16);
            background: rgba(15,23,42,0.9);
            color: #cbd5e1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.3rem;
            cursor: pointer;
            margin-bottom: 0.1rem;
        }
        .wa-input {
            flex: 1;
        }
        .wa-send {
            min-width: 120px;
            height: 46px;
            border-radius: 24px;
            border: none;
            background: linear-gradient(135deg, #0f766e, #14b8a6);
            color: white;
            font-weight: 700;
        }
        .wa-attachment {
            margin-top: 0.6rem;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(15,118,110,0.12);
            border: 1px solid rgba(45,212,191,0.2);
            color: #ccfbf1;
            border-radius: 999px;
            padding: 0.35rem 0.7rem;
            font-size: 0.76rem;
        }
        @media (max-width: 768px) {
            .block-container { padding-left: 0.4rem; padding-right: 0.4rem; }
            .wa-bubble { max-width: 88%; }
            .wa-input-wrap { gap: 0.35rem; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

REGIONS = ["Coast", "Eastern", "Central", "Rift Valley", "Western", "North Eastern", "Nyanza"]


def get_default_county() -> str:
    counties = get_counties()
    default_candidates = ["Bungoma", "Nakuru", "Kisumu", "Meru", "Mombasa"]
    for candidate in default_candidates:
        if candidate in counties:
            return candidate
    return counties[0] if counties else "Bungoma"


def safe_api_call(func, error_message: str) -> Any | None:
    try:
        return func()
    except requests.exceptions.HTTPError as exc:
        detail = "Unknown API error"
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        logger.warning("%s: %s", error_message, detail)
    except requests.exceptions.RequestException as exc:
        logger.warning("%s: Backend unavailable. %s", error_message, exc)
    except Exception as exc:
        logger.warning("%s: %s", error_message, exc)
    return None


def get_counties() -> list[str]:
    base = sorted(set(KENYA_COUNTIES))
    try:
        counties = api_client.get_available_counties()
        if counties:
            merged = sorted(set(base) | set(counties))
            return merged
    except Exception:
        pass
    return base


def render_sidebar() -> None:
    with st.sidebar:
        st.title("🌾 AgriShield")
        st.caption("Kenya agricultural intelligence")

        try:
            api_client.health()
        except Exception:
            pass

        st.markdown("---")

        counties = get_counties()
        default_county = st.session_state.get("selected_county") if st.session_state.get("selected_county") in counties else get_default_county()
        county_index = counties.index(default_county) if default_county in counties else 0
        selected_county = st.selectbox("County", counties, index=county_index)
        st.session_state["selected_county"] = selected_county

        region_default = st.session_state.get("selected_region") if st.session_state.get("selected_region") in REGIONS else "Rift Valley"
        region_index = REGIONS.index(region_default) if region_default in REGIONS else REGIONS.index("Rift Valley")
        region = st.selectbox("Region", REGIONS, index=region_index)
        st.session_state["selected_region"] = region

        st.markdown("---")


def risk_color(level: str) -> str:
    palette = {"SAFE": "#2e7d32", "MODERATE": "#f9a825", "HIGH": "#ef6c00", "CRITICAL": "#d32f2f"}
    return palette.get(str(level).upper(), "#2e7d32")


def apply_light_chart_theme(chart: alt.Chart) -> alt.Chart:
    return (
        chart.properties(background="#ffffff")
        .configure_title(color="#0f172a", fontSize=14, anchor="start")
        .configure_axis(labelColor="#334155", titleColor="#0f172a", gridColor="#e2e8f0", domainColor="#cbd5e1")
        .configure_legend(labelColor="#334155", titleColor="#0f172a")
        .configure_view(strokeWidth=0)
    )


def render_light_bar_chart(data: pd.DataFrame, x_field: str, y_field: str, title: str | None = None, color: str = "#14b8a6") -> None:
    if data.empty:
        return
    chart = alt.Chart(data).mark_bar(color=color, cornerRadius=6).encode(
        x=alt.X(f"{x_field}:N", sort="-y", axis=alt.Axis(labelAngle=0, title="")),
        y=alt.Y(f"{y_field}:Q", title="", axis=alt.Axis(grid=True)),
    )
    if title:
        chart = chart.properties(title=title)
    st.altair_chart(apply_light_chart_theme(chart), use_container_width=True)


def render_light_line_chart(data: pd.DataFrame, x_field: str, y_field: str, title: str | None = None) -> None:
    if data.empty:
        return
    chart = alt.Chart(data).mark_line(color="#2563eb", point=True, strokeWidth=3).encode(
        x=alt.X(f"{x_field}:T", axis=alt.Axis(title="")),
        y=alt.Y(f"{y_field}:Q", axis=alt.Axis(title="", grid=True)),
    )
    if title:
        chart = chart.properties(title=title)
    st.altair_chart(apply_light_chart_theme(chart), use_container_width=True)


def render_light_map(df_map: pd.DataFrame) -> None:
    if pdk is not None and not df_map.empty:
        color_lookup = {
            "SAFE": [34, 197, 94, 180],
            "MODERATE": [250, 204, 21, 190],
            "HIGH": [249, 115, 22, 200],
            "CRITICAL": [239, 68, 68, 220],
        }
        data = df_map.copy()
        data["fill_color"] = data["risk_level"].map(color_lookup).apply(lambda x: x if isinstance(x, list) else [34, 197, 94, 180])
        deck = pdk.Deck(
            map_style="light",
            initial_view_state=pdk.ViewState(latitude=0.5, longitude=37.8, zoom=5.3, pitch=0),
            layers=[
                pdk.Layer(
                    "ScatterplotLayer",
                    data=data,
                    get_position="[lon, lat]",
                    get_radius=18000,
                    get_fill_color="fill_color",
                    get_line_color=[255, 255, 255, 255],
                    line_width_min_pixels=1,
                    pickable=True,
                )
            ],
            tooltip={"text": "{county}\nRisk score: {risk_score}"},
        )
        st.pydeck_chart(deck, use_container_width=True)
        return
    st.map(df_map[["lat", "lon"]], size=5, use_container_width=True)


def build_gria_farm_summary(payload: dict[str, Any], county_name: str | None = None) -> str:
    if not payload:
        return "Gria AI could not generate a summary because no live risk data was returned from the backend."

    score = float(payload.get("risk_score", 0) or 0)
    level = (payload.get("risk_level") or risk_label_from_score(score)).upper()
    driver = payload.get("main_driver") or "weather stress and field conditions"
    recommendation = payload.get("recommendation") or "Monitor conditions closely and act early."
    if county_name:
        return (
            f"{county_name} is currently at {level.lower()} risk. "
            f"The main issue is {driver.lower()}, which means farmers should focus on {recommendation.lower()}. "
            f"At a risk score of {score}/100, the practical advice is to protect crops or pasture early, watch rainfall and soil moisture closely, and respond before stress becomes severe."
        )
    return (
        f"This area is currently at {level.lower()} risk. "
        f"The main issue is {driver.lower()} and the best next step is to {recommendation.lower()}. "
        f"With a score of {score}/100, farmers should act early and monitor changing conditions closely."
    )


def render_ai_insight_panel(title: str, body_text: str) -> None:
    st.markdown(
        f"""
        <div style="padding: 1rem 1.2rem; border-radius: 16px; background: linear-gradient(135deg, rgba(15,118,110,0.15), rgba(30,41,59,0.82)); border: 1px solid rgba(45,212,191,0.3); margin-top: 0.5rem;">
            <div style="font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: #99f6e4; margin-bottom: 0.5rem;">{title}</div>
            <div style="font-size: 1rem; line-height: 1.7; color: #e2e8f0;">{body_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview() -> None:
    st.header("📊 Farm overview")
    county = st.session_state.get("selected_county") or get_default_county()
    prediction = safe_api_call(lambda: api_client.predict_county(county, focus="combined"), f"Prediction failed for {county}")
    if not prediction:
        return

    risk_score = float(prediction.get("risk_score", 0) or 0)
    level = (prediction.get("risk_level") or risk_label_from_score(risk_score)).upper()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric("Risk score", f"{int(risk_score)} / 100", color=risk_color(level))
    with c2:
        render_metric("Risk level", level, color=risk_color(level))
    with c3:
        render_metric("Focus", prediction.get("focus") or "combined", color="#60a5fa")
    with c4:
        render_metric("Model", prediction.get("model_used") or "XGBoost", color="#a78bfa")

    st.markdown(f"**Primary driver:** {prediction.get('main_driver', 'Not available')}")
    st.markdown(f"**Recommendation:** {prediction.get('recommendation', 'No recommendation available.')}")

    batch = safe_api_call(lambda: api_client.get_batch_predictions(), "Batch predictions failed")
    if batch:
        rows = batch.get("counties", [])
        if rows:
            df_map = pd.DataFrame([
                {
                    "county": item.get("county_name"),
                    "risk_score": float(item.get("risk_score", 0) or 0),
                    "risk_level": (item.get("risk_level") or risk_label_from_score(item.get("risk_score", 0))).upper(),
                    "lat": COUNTY_LOCATIONS.get(item.get("county_name"), {}).get("lat", -1.286),
                    "lon": COUNTY_LOCATIONS.get(item.get("county_name"), {}).get("lon", 36.817),
                }
                for item in rows
            ])

            st.subheader("National risk map")
            render_light_map(df_map)

            risk_counts = df_map["risk_level"].value_counts().reindex(["SAFE", "MODERATE", "HIGH", "CRITICAL"], fill_value=0)
            chart_df = pd.DataFrame({"risk_level": risk_counts.index, "count": risk_counts.values})
            left, right = st.columns(2)
            with left:
                st.subheader("Risk breakdown")
                render_light_bar_chart(chart_df, "risk_level", "count", title="Risk breakdown")
            with right:
                st.subheader("Gria AI insight")
                render_ai_insight_panel("Farmer-friendly summary", build_gria_farm_summary(prediction, county))

    history = safe_api_call(lambda: api_client.get_county_history(county, months=12), f"History failed for {county}")
    if history and history.get("trend"):
        trend_df = pd.DataFrame(history["trend"])
        trend_df["date"] = pd.to_datetime(trend_df["date"])
        st.subheader("Recent risk trend")
        render_light_line_chart(trend_df[["date", "risk_score"]], "date", "risk_score", title="Recent risk trend")


def render_compare() -> None:
    st.header("⚖️ County comparison")
    counties = get_counties()
    selected = st.multiselect("Select up to 5 counties", counties, default=counties[: min(3, len(counties))], max_selections=5)
    if len(selected) >= 2 and st.button("Compare current risk"):
        result = safe_api_call(lambda: api_client.compare_counties(selected), "Comparison failed")
        if result:
            ranked = result.get("counties", [])
            if ranked:
                df = pd.DataFrame([
                    {
                        "county": item.get("county_name"),
                        "risk_score": float(item.get("risk_score", 0) or 0),
                        "risk_level": (item.get("risk_level") or risk_label_from_score(item.get("risk_score", 0))).upper(),
                    }
                    for item in ranked
                ])
                st.dataframe(df, width="stretch")
                render_light_bar_chart(df.rename(columns={"risk_score": "score"}), "county", "score", title="County comparison")

                highest = result.get("highest_risk")
                lowest = result.get("lowest_risk")
                if highest and lowest:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"### Highest risk\n**{highest.get('county_name')}**\n{highest.get('risk_score')}/100")
                    with c2:
                        st.markdown(f"### Lowest risk\n**{lowest.get('county_name')}**\n{lowest.get('risk_score')}/100")


def render_region() -> None:
    st.header("🌍 Regional overview")
    region = st.selectbox("Region", REGIONS, index=REGIONS.index(st.session_state.get("selected_region", "Rift Valley")))
    if st.button("Load regional summary"):
        result = safe_api_call(lambda: api_client.get_region_aggregation(region), f"Region summary failed for {region}")
        if result:
            avg = float(result.get("average_risk", 0) or 0)
            level = (result.get("risk_level") or risk_label_from_score(avg)).upper()
            c1, c2 = st.columns(2)
            with c1:
                render_metric("Average risk", f"{avg:.1f} / 100", color=risk_color(level))
            with c2:
                render_metric("Risk level", level, color=risk_color(level))

            counties = result.get("counties", [])
            if counties:
                df = pd.DataFrame([
                    {
                        "county": item.get("county_name"),
                        "risk_score": float(item.get("risk_score", 0) or 0),
                        "risk_level": (item.get("risk_level") or risk_label_from_score(item.get("risk_score", 0))).upper(),
                    }
                    for item in counties
                ])
                st.dataframe(df, width="stretch")
                render_light_bar_chart(df.rename(columns={"risk_score": "score"}), "county", "score", title="Regional risk")


def render_scenario() -> None:
    st.header("🎛️ Scenario planning")
    county = st.session_state.get("selected_county") or get_default_county()
    rainfall = st.number_input("Rainfall change (%)", value=0.0, min_value=-100.0, max_value=100.0, step=1.0)
    temp = st.number_input("Temperature change (°C)", value=0.0, min_value=-10.0, max_value=10.0, step=0.5)
    ndvi = st.number_input("NDVI shock", value=0.0, min_value=-1.0, max_value=1.0, step=0.05)

    if st.button("Run scenario analysis"):
        result = safe_api_call(lambda: api_client.scenario_analysis(county, rainfall_change_pct=rainfall, temp_change_c=temp, ndvi_shock=ndvi), f"Scenario failed for {county}")
        if result:
            original = result.get("original", {})
            scenario = result.get("scenario", {})
            original_score = float(original.get("risk_score", 0) or 0)
            scenario_score = float(scenario.get("risk_score", 0) or 0)
            delta = int(result.get("score_delta", 0) or 0)
            c1, c2, c3 = st.columns(3)
            with c1:
                render_metric("Current risk", f"{int(original_score)} / 100", color="#4caf50")
            with c2:
                render_metric("Projected risk", f"{int(scenario_score)} / 100", color="#ff9800")
            with c3:
                render_metric("Delta", f"{delta:+d}", color="#64b5f6")
            st.markdown(f"**Narrative:** {result.get('narrative', 'No narrative generated.')}")
            render_ai_insight_panel("Farmer guidance", build_gria_farm_summary(scenario, county))


def render_reports() -> None:
    st.header("📑 Reports")
    county = st.session_state.get("selected_county") or get_default_county()
    report_type = st.selectbox("Report type", ["combined", "crop", "livestock"], index=0)
    detailed = st.checkbox("Detailed report")

    if st.button("Generate report"):
        result = safe_api_call(lambda: api_client.create_report(county, report_type=report_type, detailed=detailed), "Report creation failed")
        if result:
            st.session_state["last_report_id"] = result.get("id")

    if st.session_state.get("last_report_id"):
        pdf_bytes = safe_api_call(lambda: api_client.download_report_pdf(st.session_state["last_report_id"]), "Report download failed")
        if pdf_bytes is not None:
            st.download_button("Download report PDF", data=pdf_bytes, file_name=f"agrishield_report_{st.session_state['last_report_id']}.pdf", mime="application/pdf")

    report_list = safe_api_call(lambda: api_client.list_reports(limit=10), "Failed to load reports")
    if report_list:
        rows = report_list.get("reports", [])
        if rows:
            st.subheader("Recent report history")
            report_df = pd.DataFrame([
                {"id": row.get("id"), "report_type": row.get("report_type"), "detailed": row.get("detailed"), "created_at": row.get("created_at")}
                for row in rows
            ])
            st.dataframe(report_df, width="stretch")


def render_gria() -> None:
    county = st.session_state.get("selected_county") or get_default_county()
    if "gria_history" not in st.session_state:
        st.session_state["gria_history"] = []

    def format_response_html(content: str) -> str:
        cleaned = str(content or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        cleaned = cleaned.replace("\n\n", "<br><br>")
        cleaned = cleaned.replace("\n", "<br>")
        cleaned = cleaned.replace("**", "")
        return cleaned

    wa_messages = []
    if st.session_state.get("gria_history"):
        for item in st.session_state["gria_history"]:
            sender = item["role"]
            bubble = format_response_html(item["content"])
            time = item.get("time") or "now"
            status = "✓✓" if sender == "user" else "AI"
            wa_messages.append(
                f'<div class="wa-row {sender}"><div class="wa-bubble"><div class="wa-message-body">{bubble}</div><div class="wa-meta"><span>{status}</span><span>{time}</span></div></div></div>'
            )
    else:
        wa_messages.append(
            '<div class="wa-row ai"><div class="wa-bubble"><div class="wa-message-body">Gria AI will explain the dashboard results in simple farmer language here.</div><div class="wa-meta"><span>AI</span><span>now</span></div></div></div>'
        )

    summary_btn = st.button("Generate summary", key="gria_summary_btn")
    if summary_btn:
        prediction = safe_api_call(lambda: api_client.predict_county(county, focus="combined"), f"Prediction failed for {county}")
        if prediction:
            summary = build_gria_farm_summary(prediction, county)
            st.session_state["gria_history"].append({"role": "assistant", "content": summary, "time": "now"})
            st.rerun()

    st.markdown(
        """
        <style>
            .wa-shell {
                background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
                border: 1px solid rgba(148,163,184,0.18);
                border-radius: 22px;
                overflow: hidden;
                box-shadow: 0 18px 40px rgba(15,23,42,0.25);
                margin-top: 0.5rem;
            }
            .wa-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
                padding: 0.9rem 1rem;
                border-bottom: 1px solid rgba(148,163,184,0.14);
            }
            .wa-header-left {
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }
            .wa-avatar {
                width: 38px;
                height: 38px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, #22c55e, #16a34a);
                color: white;
                font-size: 1rem;
                font-weight: 700;
            }
            .wa-contact {
                font-size: 1.02rem;
                font-weight: 700;
                color: #f8fafc;
            }
            .wa-status {
                font-size: 0.7rem;
                color: #86efac;
                letter-spacing: 0.03em;
            }
            .wa-actions {
                color: #dbeafe;
                font-size: 1.1rem;
                padding-right: 0.25rem;
            }
            .wa-messages {
                background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60"><path d="M0 60V0h60v60" fill="none"/><path d="M0 0h60v60" fill="none" stroke="rgba(148,163,184,0.06)" stroke-width="1"/></svg>');
                background-color: #0b1220;
                min-height: 440px;
                max-height: 640px;
                overflow-y: auto;
                padding: 1rem 0.85rem;
            }
            .wa-row {
                display: flex;
                margin: 0.55rem 0;
            }
            .wa-row.user { justify-content: flex-end; }
            .wa-row.ai { justify-content: flex-start; }
            .wa-bubble {
                max-width: 78%;
                padding: 0.8rem 0.9rem 0.55rem;
                border-radius: 18px;
                position: relative;
                box-shadow: 0 6px 16px rgba(15,23,42,0.16);
            }
            .wa-row.user .wa-bubble {
                background: linear-gradient(135deg, #065f46, #0f766e);
                color: #ecfeff;
                border-bottom-right-radius: 6px;
            }
            .wa-row.ai .wa-bubble {
                background: rgba(30,41,59,0.96);
                color: #e2e8f0;
                border: 1px solid rgba(148,163,184,0.18);
                border-bottom-left-radius: 6px;
            }
            .wa-message-body {
                line-height: 1.7;
                white-space: normal;
                word-wrap: break-word;
            }
            .wa-message-body strong { color: #f8fafc; }
            .wa-message-body ul, .wa-message-body ol {
                margin: 0.4rem 0 0 1rem;
                padding: 0;
            }
            .wa-message-body li { margin: 0.25rem 0; }
            .wa-meta {
                display: flex;
                justify-content: flex-end;
                gap: 0.5rem;
                font-size: 0.65rem;
                opacity: 0.82;
                margin-top: 0.4rem;
            }
            .wa-row.ai .wa-meta { justify-content: flex-start; }
            .wa-composer {
                background: #111827;
                border-top: 1px solid rgba(148,163,184,0.15);
                padding: 0.8rem 0.75rem 0.9rem;
            }
            .wa-composer .stForm {
                display: block;
            }
            @media (max-width: 768px) {
                .wa-bubble { max-width: 92%; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'''
        <div class="wa-shell">
            <div class="wa-header">
                <div class="wa-header-left">
                    <div class="wa-avatar">🤖</div>
                    <div>
                        <div class="wa-contact">Gria AI</div>
                        <div class="wa-status">{county} • online</div>
                    </div>
                </div>
                <div class="wa-actions">⋯</div>
            </div>
            <div class="wa-messages">{''.join(wa_messages)}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    with st.form("gria_chat_form", clear_on_submit=True):
        col_attach, col_msg, col_send = st.columns([1.2, 7, 1.5])
        with col_attach:
            uploaded_file = st.file_uploader(
                "Attach",
                type=["csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"],
                key="gria_upload",
                label_visibility="collapsed",
            )
        with col_msg:
            prompt = st.text_area(
                "Message",
                height=82,
                label_visibility="collapsed",
                placeholder="Ask Gria in simple farm language...",
                key="gria_prompt",
            )
        with col_send:
            submitted = st.form_submit_button("Send", use_container_width=True)

        if uploaded_file is not None:
            st.caption(f"Attachment: {uploaded_file.name}")

    if submitted:
        final_prompt = (prompt or "").strip()
        uploaded = st.session_state.get("gria_upload")
        document_context = None
        document_name = None

        if uploaded is not None:
            document_name = uploaded.name
            upload_result = safe_api_call(lambda: api_client.upload_and_analyze(uploaded.getvalue(), uploaded.name), "Upload analysis failed")
            if upload_result:
                attached_summary = upload_result.get("gria_summary") or upload_result.get("summary") or "Uploaded file reviewed successfully."
                document_context = (
                    upload_result.get("document_report")
                    or upload_result.get("document_text")
                    or upload_result.get("gria_summary")
                    or str(upload_result)
                )
                if not final_prompt:
                    final_prompt = f"Please explain this uploaded file for a farmer in simple terms: {uploaded.name}"
                final_prompt = f"{final_prompt}\n\nUploaded file details: {attached_summary}\n\nDocument context: {document_context}"
            elif not final_prompt:
                pass

        if final_prompt:
            st.session_state["gria_history"].append({"role": "user", "content": final_prompt, "time": "now"})
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
                st.session_state["gria_history"].append({"role": "assistant", "content": reply, "time": "now"})
                st.rerun()
            else:
                st.session_state["gria_history"].append({"role": "assistant", "content": "I could not generate a response right now. Please try again.", "time": "now"})
                st.rerun()


def main() -> None:
    ensure_session_defaults()
    render_sidebar()

    st.title("🌾 AgriShield")
    st.caption("Predictive intelligence for crops, forage and agricultural resilience across Kenya")

    tabs = st.tabs(["Overview", "Compare", "Region", "Scenario", "Reports", "Gria AI"])

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
