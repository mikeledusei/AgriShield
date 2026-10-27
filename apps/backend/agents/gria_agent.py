"""
Gria Agentic AI powered by NVIDIA NIM (Kimi K3) and LangGraph, with a rich
SHAP-aware local intelligence synthesizer so Gria always delivers clear,
jargon-free explanations, uploaded-data comparisons, and farmer recommendations.
"""
from typing import Optional
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from core.config import settings
from agents.tools import get_current_county_risk, get_historical_trends, compare_two_counties
from services import logging_service, prediction_service

llm = None
if (
    settings.NVIDIA_API_KEY
    and settings.NVIDIA_API_KEY.strip()
    and settings.NVIDIA_API_KEY != "your-nvidia-api-key"
):
    try:
        llm = ChatNVIDIA(
            model=settings.NVIDIA_MODEL,
            api_key=settings.NVIDIA_API_KEY,
            temperature=0.2,
            max_tokens=4096,
            model_kwargs={"reasoning_effort": "high"},
        )
    except Exception as e:
        logging_service.error(f"Failed to initialize ChatNVIDIA: {e}")

SYSTEM_PROMPT = """You are Gria, the Agentic AI assistant for AgriShield.
Your mission is to protect Kenya's food security by helping farmers, students, extension officers, and policymakers understand agricultural and forage risks in simple, everyday language.

RULES:
1. You have access to tools to fetch real-time LightGBM Champion risk scores, TreeSHAP feature drivers, and historical trends for all 47 Kenyan counties. ALWAYS use the tools when a user asks about a county.
2. Translate technical terms (like NDVI, SHAP values, Forage Dryness Index, and Rainfall Anomaly) into simple farm language that anyone can understand.
3. When the user uploads data or asks about a scenario, compare the uploaded/simulated numbers directly against the county's baseline model output and give concrete crop and livestock recommendations.
4. Structure your answer clearly with bullet points: What the Model Predicts, Why (SHAP Drivers in Plain Words), and Actionable Steps for Farmers & Officers.
"""

tools = [get_current_county_risk, get_historical_trends, compare_two_counties]

agent_executor = None
if llm:
    try:
        agent_executor = create_react_agent(
            llm,
            tools,
            prompt=SystemMessage(content=SYSTEM_PROMPT),
        )
    except TypeError:
        agent_executor = create_react_agent(
            llm,
            tools,
            state_modifier=SystemMessage(content=SYSTEM_PROMPT),
        )
    except Exception as e:
        logging_service.error(f"Failed to create ReAct agent: {e}")


def _synthesize_smart_advisory(
    message: str,
    county_name: Optional[str],
    month: Optional[str] = None,
    document_context: Optional[str] = None,
    document_name: Optional[str] = None,
) -> dict:
    """
    Generate a rich, plain-language Gria response grounded in the county's live
    LightGBM Champion Model output, TreeSHAP drivers, and any uploaded document context.
    """
    engine = prediction_service.get_engine()
    target_county = county_name or "Turkana"
    try:
        pred = engine.predict(None, target_county, persist=False, month=month)
    except Exception:
        pred = engine.predict(None, "Turkana", persist=False, month=month)

    c_name = pred["county_name"]
    score = int(pred["risk_score"])
    level = pred["risk_level"]
    obs_month = pred.get("month") or "2025-02"
    feats = pred.get("features") or {}
    shap_items = pred.get("shap_contributions") or []

    rain_mm = feats.get("rainfall_mm", 0.0)
    rain_anom = feats.get("rainfall_anomaly", 0.0)
    soil_m = feats.get("soil_moisture", 0.0)
    temp_c = feats.get("temp_mean_c", 0.0)
    ndvi_l1 = feats.get("ndvi_lag1", 0.0)
    fdi = feats.get("forage_dryness_index", 0.0)

    top_pos = [
        it for it in shap_items if it["shap_value"] > 0.02 and it["feature"] not in ("month_sin", "month_cos")
    ][:3]
    top_neg = [
        it for it in shap_items if it["shap_value"] < -0.02 and it["feature"] not in ("month_sin", "month_cos")
    ][:2]

    lines = [
        f"**Gria AI Plain-Language Analysis for {c_name} County ({obs_month})**",
        f"- **1. What the Champion Model Predicts:** **{c_name}** has a drought & forage risk score of **{score}/100 ({level})** using the **LightGBM Champion Model**.",
        f"- **2. Key Agro-Climatic Readings in Plain Words:**",
        f"  - **Rainfall:** `{rain_mm:.1f} mm` (`{rain_anom:+.1f} mm` vs. normal seasonal average)",
        f"  - **Pasture & Crop Greenness (NDVI):** `{ndvi_l1:.2f}` (Forage Dryness Index: `{fdi:.2f}`)",
        f"  - **Root-Zone Soil Moisture & Heat:** `{soil_m:.2f} m³/m³` soil moisture at `{temp_c:.1f} °C` land surface temperature",
    ]

    if top_pos:
        driver_str = "; ".join(
            f"**{d['label']}** (`{d['value']:g}`, SHAP impact `{d['shap_value']:+.2f}`)"
            for d in top_pos
        )
        lines.append(f"- **3. Why the Model Gave This Score (SHAP Explainability):** The main factors pushing risk upward are {driver_str}.")
    elif top_neg:
        driver_str = "; ".join(
            f"**{d['label']}** (`{d['value']:g}`, SHAP impact `{d['shap_value']:+.2f}`)"
            for d in top_neg
        )
        lines.append(f"- **3. Why the Model Gave This Score (SHAP Explainability):** Risk is kept low thanks to {driver_str}.")

    if document_name and document_context:
        lines.append(
            f"- **4. Uploaded File Comparison (`{document_name}`):** {document_context}"
        )

    lines.extend([
        f"- **5. Practical Recommendations for Farmers & Officers:**",
        f"  - **Crop Farmers:** {'Prioritize early-maturing drought-tolerant seeds, conservation tillage, and moisture mulching.' if score >= 25 else 'Conditions support normal planting and routine weeding/top-dressing.'}",
        f"  - **Livestock Keepers:** {'Activate fodder conservation, hay baling, and strategic water-point routing as forage dryness rises.' if fdi >= 0.35 or score >= 25 else 'Pasture regeneration is adequate; maintain rotational grazing.'}",
        f"  - **County Extension Action:** {pred.get('recommendation', '')}",
    ])

    return {
        "reply": "\n".join(lines),
        "risk_score": float(score),
        "risk_level": level,
        "main_driver": pred.get("main_driver"),
        "plain_summary": pred.get("plain_summary"),
    }


def chat(
    message: str,
    county_name: Optional[str] = None,
    month: Optional[str] = None,
    document_context: Optional[str] = None,
    document_name: Optional[str] = None,
) -> dict:
    fallback = _synthesize_smart_advisory(
        message=message,
        county_name=county_name,
        month=month,
        document_context=document_context,
        document_name=document_name,
    )

    if not agent_executor:
        return fallback

    context_parts = []
    if county_name:
        context_parts.append(
            f"Active county: {county_name} (Period: {month or '2025-02'}, "
            f"LightGBM Score: {fallback['risk_score']}/100 {fallback['risk_level']}, "
            f"Main SHAP driver: {fallback.get('main_driver')})."
        )
    if document_name and document_context:
        context_parts.append(f"Uploaded file ({document_name}) analysis: {document_context[:2500]}")
    context_prefix = "\n".join(context_parts)
    input_message = (
        f"Context:\n{context_prefix}\n\nUser question: {message}"
        if context_prefix
        else message
    )

    try:
        response = agent_executor.invoke({"messages": [HumanMessage(content=input_message)]})
        ai_message = ""
        messages = response.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and isinstance(msg.content, str):
                ai_message = msg.content
                break

        if not ai_message:
            return fallback

        return {
            "reply": ai_message,
            "risk_score": fallback["risk_score"],
            "risk_level": fallback["risk_level"],
            "main_driver": fallback.get("main_driver"),
            "plain_summary": fallback.get("plain_summary"),
        }
    except Exception as e:
        logging_service.error(f"Gria Agent Error: {e}")
        return fallback
