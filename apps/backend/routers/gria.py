"""Gria AI chat and evidence analysis."""
from agents import gria_agent
from core import rate_limit
from core.auth import get_current_user
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from schemas.manual_prediction import ManualPredictionRequest
from schemas.pydantic_models import GriaChatRequest, GriaChatResponse
from seed_counties import normalize_county_name
from services.analysis_service import explain_evidence, historical_evidence, manual_evidence
from services.prediction_service import get_engine

router = APIRouter(prefix="/gria", tags=["gria"])


def enforce_ai_quota(request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Bound the paid, slow AI routes. Identity is the key, not the address, so callers
    behind one NAT do not share a budget once authenticated."""
    caller = user.get("id") or (request.client.host if request.client else "unknown")
    retry_after = rate_limit.check(f"gria:{caller}")
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many AI requests. Wait a moment and try again.",
            headers={"Retry-After": str(int(retry_after))},
        )
    return user


@router.post("/chat", response_model=GriaChatResponse)
def chat_with_gria(
    request: GriaChatRequest,
    user: dict = Depends(enforce_ai_quota),
):
    engine = get_engine()
    if engine.model is None:
        raise HTTPException(status_code=503, detail="The trained model is unavailable.")
    if not request.county_name or not request.month:
        raise HTTPException(status_code=422, detail="Choose a county and a historical month with available data.")
    county = normalize_county_name(request.county_name)
    history = engine.county_history.get(county)
    if history is None or request.month not in set(history["year_month"].astype(str)):
        raise HTTPException(status_code=422, detail="Choose a county and a historical month with available data.")
    try:
        response = gria_agent.chat(
            request.message,
            county_name=request.county_name,
            month=request.month,
            document_context=request.document_context,
            document_name=request.document_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GriaChatResponse(
        reply=response["reply"],
        mode=response.get("mode", "summary"),
        risk_score=response.get("risk_score"),
        risk_level=response.get("risk_level"),
        main_driver=response.get("main_driver"),
        plain_summary=response.get("plain_summary"),
    )


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    county_name: str | None = Field(default=None, max_length=100)
    month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    inputs: ManualPredictionRequest | None = None
    expected_model_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    expected_probability: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode='after')
    def check_source(self):
        if self.inputs is not None:
            if self.county_name is not None or self.month is not None or self.expected_model_sha256 is None or self.expected_probability is None:
                raise ValueError('Supply one verified user assessment or one historical county and month.')
        elif not self.county_name or not self.month or self.expected_model_sha256 is not None or self.expected_probability is not None:
            raise ValueError('Supply one verified user assessment or one historical county and month.')
        return self


@router.post('/analyze')
def analyze(request: AnalyzeRequest, user: dict = Depends(enforce_ai_quota)):
    if request.inputs is not None:
        evidence = manual_evidence(request.inputs, request.expected_model_sha256, request.expected_probability)
    else:
        evidence = historical_evidence(request.county_name, request.month)
    return {'evidence': evidence, 'analysis': explain_evidence(evidence)}
