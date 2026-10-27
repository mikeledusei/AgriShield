"""Gria AI chat endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from database import crud
from schemas.pydantic_models import GriaChatRequest, GriaChatResponse
from agents import gria_agent

router = APIRouter(prefix="/gria", tags=["gria"])


@router.post("/chat", response_model=GriaChatResponse)
def chat_with_gria(request: GriaChatRequest, db: Session = Depends(get_db)):
    response = gria_agent.chat(
        request.message,
        request.county_name,
        document_context=request.document_context,
        document_name=request.document_name,
    )
    crud.save_chat_message(
        db,
        county_name=request.county_name or "General",
        user_message=request.message,
        gria_reply=response["reply"],
        risk_score=response.get("risk_score"),
    )
    return GriaChatResponse(
        reply=response["reply"],
        risk_score=response.get("risk_score"),
        risk_level=response.get("risk_level")
    )
