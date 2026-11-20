"""Pydantic models for the API surface that is actually served.

Prediction input/output contracts live in ``schemas/manual_prediction.py``; this
module holds the Gria and health envelopes.
"""

from pydantic import BaseModel, Field


# ---------- Gria ----------
class GriaChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    county_name: str | None = None
    month: str | None = None
    document_context: str | None = Field(default=None, max_length=4000)
    document_name: str | None = Field(default=None, max_length=255)


class GriaChatResponse(BaseModel):
    reply: str
    mode: str = "summary"
    risk_score: float | None = None
    risk_level: str | None = None
    main_driver: str | None = None
    plain_summary: str | None = None


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
