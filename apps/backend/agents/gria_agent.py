"""
Gria Agentic AI powered by NVIDIA NIM (Kimi K3) and LangGraph.
Uses ReAct (Reasoning + Acting) to dynamically call tools based on user queries.
"""
from typing import Optional
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from core.config import settings
from agents.tools import get_current_county_risk, get_historical_trends, compare_two_counties
from services import logging_service, prediction_service

# 1. Initialize the NVIDIA NIM LLM (Kimi K3) when valid credentials exist
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

# 2. Define Gria's Persona and Instructions
SYSTEM_PROMPT = """You are Gria, the Agentic AI assistant for AgriShield.
Your mission is to protect Kenya's food security by helping farmers and government officials understand agricultural risks.

RULES:
1. You have access to tools to fetch real-time risk data and historical trends for Kenyan counties. ALWAYS use the tools when a user asks about a specific county.
2. Think step-by-step. Analyze the data returned by the tools before formulating your final answer.
3. Be concise, practical, and use plain language suitable for non-technical users.
4. If a risk level is HIGH or CRITICAL, emphasize the need for immediate action and provide the recommendation.
5. If a risk level is SAFE, reassure the user but advise them to keep monitoring.
"""

# 3. Bind the tools to the LLM and create the ReAct Agent
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


def _local_advisory_fallback(
    message: str,
    county_name: Optional[str],
    risk_score: Optional[int],
    risk_level: Optional[str],
    document_name: Optional[str] = None,
) -> str:
    """Provide a deterministic, data-backed advisory when NVIDIA NIM API key is not configured."""
    if county_name:
        try:
            pred = prediction_service.get_engine().predict(None, county_name, persist=False)
            doc_note = f" (incorporating uploaded document '{document_name}')" if document_name else ""
            return (
                f"**Gria Advisory for {pred['county_name']} County{doc_note}:**\n"
                f"- **Current Risk Status:** {pred['risk_level']} ({pred['risk_score']}%)\n"
                f"- **Primary Agro-Climatic Driver:** {pred['main_driver']}\n"
                f"- **Model Engine:** {pred['model_used']} (period: {pred['month']})\n"
                f"- **Recommended Action:** {pred['recommendation']}"
            )
        except Exception:
            pass
    return (
        "Gria AI is operating in local advisory mode. Select a Kenyan county to receive "
        "LightGBM Champion risk scores, primary drivers, and actionable drought recommendations."
    )


def chat(
    message: str,
    county_name: Optional[str] = None,
    document_context: Optional[str] = None,
    document_name: Optional[str] = None,
) -> dict:
    # Pre-fetch risk context so frontend gauges get live values
    risk_score, risk_level = None, None
    if county_name:
        try:
            risk_score, risk_level = prediction_service.quick_risk(county_name)
        except Exception as e:
            logging_service.warning(f"Could not fetch quick risk for {county_name}: {e}")

    if not agent_executor:
        return {
            "reply": _local_advisory_fallback(
                message, county_name, risk_score, risk_level, document_name
            ),
            "risk_score": risk_score,
            "risk_level": risk_level,
        }

    context_parts = []
    if county_name:
        context_parts.append(f"The user is currently viewing the dashboard for {county_name}.")
    if document_name and document_context:
        context_parts.append(f"Uploaded document ({document_name}): {document_context[:2000]}")
    context_prefix = "\n".join(context_parts)
    input_message = f"Context:\n{context_prefix}\n\nUser question: {message}" if context_prefix else message

    try:
        response = agent_executor.invoke({"messages": [HumanMessage(content=input_message)]})

        ai_message = ""
        messages = response.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and isinstance(msg.content, str):
                ai_message = msg.content
                break

        if not ai_message:
            ai_message = _local_advisory_fallback(
                message, county_name, risk_score, risk_level, document_name
            )

        return {
            "reply": ai_message,
            "risk_score": risk_score,
            "risk_level": risk_level,
        }

    except Exception as e:
        logging_service.error(f"Gria Agent Error: {e}")
        return {
            "reply": _local_advisory_fallback(
                message, county_name, risk_score, risk_level, document_name
            ),
            "risk_score": risk_score,
            "risk_level": risk_level,
        }
