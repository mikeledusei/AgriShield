"""
Gria Agentic AI powered by NVIDIA NIM (Kimi K3) and LangGraph.
Uses ReAct (Reasoning + Acting) to dynamically call tools based on user queries.
"""
from __future__ import annotations

try:
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    from langgraph.prebuilt import create_react_agent
except Exception:  # pragma: no cover - optional dependency path
    ChatNVIDIA = None
    SystemMessage = None
    HumanMessage = None
    AIMessage = None
    create_react_agent = None

from core.config import settings
from agents.tools import get_current_county_risk, get_historical_trends, compare_two_counties
from services import logging_service, prediction_service

# 1. Initialize the NVIDIA NIM LLM (Kimi K3)
llm = None
if settings.NVIDIA_API_KEY and ChatNVIDIA is not None:
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
Your mission is to protect Kenya's food security by helping farmers and government officials understand agricultural risks.

RULES:
1. You have access to tools to fetch real-time risk data and historical trends for Kenyan counties. ALWAYS use the tools when a user asks about a specific county.
2. Think step-by-step. Analyze the data returned by the tools before formulating your final answer.
3. Be concise, practical, and use plain language suitable for non-technical users.
4. If a risk level is HIGH or CRITICAL, emphasize the need for immediate action and provide the recommendation.
5. If a risk level is SAFE, reassure the user but advise them to keep monitoring.
"""

tools = [get_current_county_risk, get_historical_trends, compare_two_counties]

agent_executor = None
if llm and create_react_agent is not None:
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


def _fallback_reply(message: str, county_name: str = None, document_context: str = None, document_name: str = None) -> str:
    county_label = county_name or "the county you selected"
    if document_context:
        doc_name = document_name or "uploaded document"
        return (
            f"I reviewed {doc_name} and here is the practical summary for {county_label}:\n\n"
            f"- The document highlights conditions that matter for farm planning.\n"
            f"- Key point: {document_context[:400]}\n\n"
            f"- Action: focus on early irrigation, soil moisture monitoring, and a field check within the next 7 days.\n"
            f"- Farmer takeaway: act early, keep records, and monitor rainfall and pasture stress closely."
        )
    if county_name:
        return (
            f"For {county_name}, the main message is simple: act early and monitor the field closely. "
            "Use the risk indicators on the dashboard to decide whether to irrigate, adjust planting, or prepare for stress."
        )
    return (
        "I reviewed the information and the guidance is straightforward: keep a close eye on rainfall, soil moisture, "
        "and pasture conditions, then act early if stress levels rise."
    )


def chat(message: str, county_name: str = None, document_context: str = None, document_name: str = None) -> dict:
    risk_score, risk_level = None, None
    if county_name:
        try:
            risk_score, risk_level = prediction_service.quick_risk(county_name)
        except Exception as e:
            logging_service.warning(f"Could not fetch quick risk for {county_name}: {e}")

    if not settings.NVIDIA_API_KEY or not agent_executor or ChatNVIDIA is None:
        return {
            "reply": _fallback_reply(message, county_name, document_context, document_name),
            "risk_score": risk_score,
            "risk_level": risk_level,
        }

    input_message = message
    if county_name:
        input_message = f"Context: The user is currently viewing the dashboard for {county_name}. \nUser question: {message}"
    if document_context:
        input_message += f"\nDocument context ({document_name or 'uploaded file'}): {document_context}"

    try:
        response = agent_executor.invoke({"messages": [HumanMessage(content=input_message)]})

        ai_message = ""
        messages = response.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and isinstance(msg.content, str):
                ai_message = msg.content
                break

        if not ai_message:
            ai_message = _fallback_reply(message, county_name, document_context, document_name)

        return {
            "reply": ai_message,
            "risk_score": risk_score,
            "risk_level": risk_level,
        }

    except Exception as e:
        logging_service.error(f"Gria Agent Error: {e}")
        return {
            "reply": _fallback_reply(message, county_name, document_context, document_name),
            "risk_score": risk_score,
            "risk_level": risk_level,
        }