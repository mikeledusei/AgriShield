"""Gria AI chat and evidence analysis — now with WhatsApp-like persistent history."""
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from agents import gria_agent
from core import rate_limit
from core.auth import get_current_user
from core.database import get_db
from database.models import HistoryRecord
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from schemas.manual_prediction import ManualPredictionRequest
from schemas.pydantic_models import GriaChatRequest, GriaChatResponse, GriaChatSaveRequest, GriaChatSaveResponse
from seed_counties import normalize_county_name
from services.analysis_service import explain_evidence, historical_evidence, manual_evidence
from services.prediction_service import get_engine
from sqlalchemy.orm import Session

router = APIRouter(prefix="/gria", tags=["gria"])
GRIA_CHAT_DAYS = 90


def enforce_ai_quota(request: Request, user: dict = Depends(get_current_user)) -> dict:
    caller = user.get("id") or (request.client.host if request.client else "unknown")
    retry_after = rate_limit.check(f"gria:{caller}")
    if retry_after is not None:
        raise HTTPException(status_code=429, detail="Too many AI requests. Wait a moment and try again.", headers={"Retry-After": str(int(retry_after))})
    return user


@router.post("/chat", response_model=GriaChatResponse)
def chat_with_gria(request: GriaChatRequest, user: dict = Depends(enforce_ai_quota)):
    engine = get_engine()
    if engine.model is None:
        raise HTTPException(status_code=503, detail="The trained model is unavailable.")
    if not request.county_name or not request.month:
        raise HTTPException(status_code=422, detail="Choose a county and a historical month with available data.")
    county = normalize_county_name(request.county_name)
    history = engine.county_history.get(county)
    if history is None or request.month not in set(history["year_month"].astype(str)):
        raise HTTPException(status_code=422, detail="Choose a county and a historical month with available data.")
    # Validate history shape (max 24 turns already in schema) and trim server-side too
    history_payload = None
    if request.history:
        history_payload = [{"role": h.role, "content": h.content} for h in request.history[-20:]]
    try:
        response = gria_agent.chat(
            request.message,
            county_name=request.county_name,
            month=request.month,
            document_context=request.document_context,
            document_name=request.document_name,
            history=history_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GriaChatResponse(reply=response["reply"], mode=response.get("mode", "summary"), risk_score=response.get("risk_score"), risk_level=response.get("risk_level"), main_driver=response.get("main_driver"), plain_summary=response.get("plain_summary"))


# --- Opt-in persistent chat history (reuses assessment_history table, type=gria_chat) ---
def _key_digest(key: str | None) -> str:
    import re
    if not key or not re.fullmatch(r"[A-Za-z0-9_-]{43}", key):
        raise HTTPException(status_code=401, detail="A valid private history key is required. Create one in the History page.")
    return hashlib.sha256(key.encode("ascii")).hexdigest()

def _now_utc():
    return datetime.now(UTC).replace(tzinfo=None)

@router.post("/conversations", response_model=GriaChatSaveResponse, status_code=201)
def save_conversation(req: GriaChatSaveRequest, x_history_key: str | None = Header(default=None), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    digest = _key_digest(x_history_key)
    snap = {"type": "gria_chat", "county_name": req.county_name, "month": req.month, "messages": [m.model_dump() for m in req.messages], "saved_at": _now_utc().isoformat() + "Z"}
    rec = HistoryRecord(id=str(uuid.uuid4()), history_key_hash=digest, snapshot_json=json.dumps(snap, allow_nan=False), created_at=_now_utc())
    db.add(rec)
    # purge old chats same retention as assessments
    cutoff = _now_utc() - timedelta(days=GRIA_CHAT_DAYS)
    db.query(HistoryRecord).filter(HistoryRecord.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return GriaChatSaveResponse(id=rec.id, created_at=rec.created_at.isoformat() + "Z", retention_days=GRIA_CHAT_DAYS)

@router.get("/conversations")
def list_conversations(x_history_key: str | None = Header(default=None), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    digest = _key_digest(x_history_key)
    rows = db.query(HistoryRecord).filter(HistoryRecord.history_key_hash == digest, HistoryRecord.created_at >= _now_utc() - timedelta(days=GRIA_CHAT_DAYS)).order_by(HistoryRecord.created_at.desc()).limit(100).all()
    out = []
    for r in rows:
        try:
            snap = json.loads(r.snapshot_json)
            if snap.get("type") != "gria_chat":
                continue
            preview = snap.get("messages", [{}])[0].get("content", "")[:80] if snap.get("messages") else ""
            out.append({"id": r.id, "county_name": snap.get("county_name"), "month": snap.get("month"), "message_count": len(snap.get("messages", [])), "preview": preview, "created_at": r.created_at.isoformat() + "Z"})
        except Exception:
            continue
    return {"conversations": out, "retention_days": GRIA_CHAT_DAYS}

@router.get("/conversations/{cid}")
def get_conversation(cid: str, x_history_key: str | None = Header(default=None), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    digest = _key_digest(x_history_key)
    rec = db.get(HistoryRecord, cid)
    import secrets as sec
    if not rec or not sec.compare_digest(rec.history_key_hash, digest):
        raise HTTPException(status_code=404, detail="Chat not found or expired.")
    return json.loads(rec.snapshot_json)


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
