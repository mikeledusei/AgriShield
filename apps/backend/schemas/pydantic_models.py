"""Pydantic models for the API surface that is actually served.

Prediction input/output contracts live in ``schemas/manual_prediction.py``; this
module holds the Gria and health envelopes.
"""

from pydantic import BaseModel, Field


# ---------- Gria ----------
class GriaChatHistoryItem(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class GriaChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    county_name: str | None = None
    month: str | None = None
    document_context: str | None = Field(default=None, max_length=4000)
    document_name: str | None = Field(default=None, max_length=255)
    history: list[GriaChatHistoryItem] | None = Field(default=None, max_length=24, description="Prior WhatsApp-style turns — last 12 pairs kept, no evidence injected here")


class GriaChatResponse(BaseModel):
    reply: str
    mode: str = "summary"
    risk_score: float | None = None
    risk_level: str | None = None
    main_driver: str | None = None
    plain_summary: str | None = None

class GriaChatSaveRequest(BaseModel):
    county_name: str | None = None
    month: str | None = None
    messages: list[GriaChatHistoryItem] = Field(min_length=1, max_length=100)

class GriaChatSaveResponse(BaseModel):
    id: str
    created_at: str
    retention_days: int


# ---------- Health ----------
class HealthResponse(BaseModel):
    status: str
    services: dict[str, str]
    version: str = "1.0.0"
    model_loaded: bool = False
    model_name: str = "unavailable"
    gria_available: bool = False
    database_connected: bool = False
    problems: list[str] = Field(default_factory=list)
