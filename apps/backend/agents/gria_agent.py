"""
Gria Agentic AI powered by NVIDIA NIM (Kimi K3) and LangGraph.
Uses ReAct (Reasoning + Acting) to dynamically call tools based on user queries.
"""
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from core.config import settings
from agents.tools import get_current_county_risk, get_historical_trends, compare_two_counties
from services import logging_service, prediction_service

# 1. Initialize the NVIDIA NIM LLM (Kimi K3)
llm = None
if settings.NVIDIA_API_KEY:
    try:
        llm = ChatNVIDIA(
            model=settings.NVIDIA_MODEL,
            api_key=settings.NVIDIA_API_KEY,
            temperature=0.2,
            max_tokens=4096,
            # Kimi K3 specific reasoning parameter
            model_kwargs={"reasoning_effort": "high"} 
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
        # LangGraph 0.2+ accepts a SystemMessage directly for the prompt
        agent_executor = create_react_agent(
            llm, 
            tools, 
            prompt=SystemMessage(content=SYSTEM_PROMPT)
        )
    except TypeError:
        # Fallback for specific 0.2.x sub-versions that strictly required state_modifier
        agent_executor = create_react_agent(
            llm, 
            tools, 
            state_modifier=SystemMessage(content=SYSTEM_PROMPT)
        )
    except Exception as e:
        logging_service.error(f"Failed to create ReAct agent: {e}")

def chat(message: str, county_name: str = None) -> dict:
    if not settings.NVIDIA_API_KEY or not agent_executor:
        return {
            "reply": "Gria AI is currently offline. Please check your NVIDIA API configuration.",
            "risk_score": None,
            "risk_level": None,
        }

    # Pre-fetch risk context so frontend gauges get live values
    risk_score, risk_level = None, None
    if county_name:
        try:
            risk_score, risk_level = prediction_service.quick_risk(county_name)
        except Exception as e:
            logging_service.warning(f"Could not fetch quick risk for {county_name}: {e}")

    input_message = message
    if county_name:
        input_message = f"Context: The user is currently viewing the dashboard for {county_name}. \nUser question: {message}"

    try:
        # Invoke the LangGraph agent using explicit HumanMessage (prevents tuple-unpacking warnings)
        response = agent_executor.invoke({"messages": [HumanMessage(content=input_message)]})
        
        # Robustly extract the final AI response
        # We iterate backwards to ensure we grab the final AIMessage, not a ToolMessage
        ai_message = ""
        messages = response.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and isinstance(msg.content, str):
                ai_message = msg.content
                break
                
        if not ai_message:
            ai_message = "I have analyzed the data, but I couldn't generate a final summary. Please try rephrasing your question."

        return {
            "reply": ai_message,
            "risk_score": risk_score,
            "risk_level": risk_level,
        }
        
    except Exception as e:
        logging_service.error(f"Gria Agent Error: {e}")
        return {
            "reply": "I encountered an issue while fetching the data from the AgriShield database. Please try again in a moment.",
            "risk_score": risk_score,
            "risk_level": risk_level,
        }