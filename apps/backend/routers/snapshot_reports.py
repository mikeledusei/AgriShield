"""Immutable, capability-protected reports for user-provided observations."""
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from core.auth import get_current_user
from core.database import get_db
from database.models import AssessmentReportSnapshot
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from routers.manual_predictions import render_assessment_pdf, score_observation
from schemas.manual_prediction import ManualPredictionRequest
from services import logging_service
from services.analysis_service import explain_evidence, historical_evidence, manual_evidence
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(prefix='/reports', tags=['Assessment reports'])
RETENTION_DAYS = 7


class SnapshotRequest(BaseModel):
    inputs: ManualPredictionRequest
    expected_model_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_probability: float = Field(ge=0, le=1, allow_inf_nan=False)
    include_gria: bool = False


class HistoricalSnapshotRequest(BaseModel):
    county_name: str = Field(min_length=1, max_length=100)
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')


def cleanup_expired(db: Session, now: datetime | None = None) -> int:
    """Delete snapshots past retention. Indexed on created_at, so this stays cheap."""
    now = now or datetime.now(UTC).replace(tzinfo=None)
    return (
        db.query(AssessmentReportSnapshot)
        .filter(AssessmentReportSnapshot.created_at < now - timedelta(days=RETENTION_DAYS))
        .delete(synchronize_session=False)
    )


@router.post('/assessments', status_code=201)
def create_snapshot(req: SnapshotRequest, response: Response, db: Session = Depends(get_db),
                    user: dict = Depends(get_current_user)):
    if req.include_gria:
        evidence = manual_evidence(req.inputs, req.expected_model_sha256, req.expected_probability)
        result = evidence['assessment']
        result['report_analysis'] = explain_evidence(evidence)
        result['data_source'] = evidence['source_note']
    else:
        result = score_observation(req.inputs)
        if result['model_sha256'] != req.expected_model_sha256:
            raise HTTPException(status_code=409, detail='The model changed. Re-run the assessment before creating a report.')
        if abs(result['model_probability'] - req.expected_probability) > 1e-12:
            raise HTTPException(status_code=409, detail='The result changed. Re-run the assessment before creating a report.')
    return save_snapshot(result, response, db)


@router.post('/historical', status_code=201)
def create_historical_snapshot(req: HistoricalSnapshotRequest, response: Response,
                               db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    evidence = historical_evidence(req.county_name, req.month)
    result = dict(evidence['assessment'])
    result['report_analysis'] = explain_evidence(evidence)
    result['report_context'] = {
        'national': evidence['national'],
        'trend': evidence['trend'],
        'source_note': evidence['source_note'],
    }
    return save_snapshot(result, response, db)


def save_snapshot(result: dict, response: Response, db: Session):
    now = datetime.now(UTC).replace(tzinfo=None)
    result['snapshot_created_at'] = now.isoformat() + 'Z'
    token = secrets.token_urlsafe(32)
    entry = AssessmentReportSnapshot(
        id=str(uuid.uuid4()),
        access_hash=hashlib.sha256(token.encode()).hexdigest(),
        snapshot_json=json.dumps(result, allow_nan=False),
        created_at=now,
    )
    try:
        cleanup_expired(db, now)
        db.add(entry)
        db.commit()
    except SQLAlchemyError:
        # Storage failure is a retryable availability problem.
        db.rollback()
        logging_service.exception('Could not persist report snapshot')
        raise HTTPException(status_code=503, detail='Report storage is unavailable. No report was saved.') from None
    except (TypeError, ValueError):
        # A non-serialisable result is a bug in the caller, not an outage.
        db.rollback()
        logging_service.exception('Report snapshot is not serialisable')
        raise HTTPException(status_code=500, detail='The report could not be serialised.') from None
    response.headers['Cache-Control'] = 'no-store'
    return {'id': entry.id, 'access_token': token, 'created_at': result['snapshot_created_at'],
            'expires_in_days': RETENTION_DAYS}


def get_authorized_snapshot(report_id: str, token: str | None, db: Session):
    entry = db.get(AssessmentReportSnapshot, report_id)
    expired = entry is not None and entry.created_at < datetime.now(UTC).replace(tzinfo=None) - timedelta(days=RETENTION_DAYS)
    if not entry or not token or expired or not secrets.compare_digest(
        entry.access_hash, hashlib.sha256(token.encode()).hexdigest()
    ):
        raise HTTPException(status_code=404, detail='Report not found or expired.')
    return entry


@router.get('/assessments/{report_id}/pdf')
def download_snapshot(report_id: str, x_report_token: str | None = Header(default=None),
                      db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    entry = get_authorized_snapshot(report_id, x_report_token, db)
    buffer = render_assessment_pdf(json.loads(entry.snapshot_json))
    return StreamingResponse(buffer, media_type='application/pdf', headers={
        'Content-Disposition': 'attachment; filename=agrishield-assessment.pdf',
        'Cache-Control': 'no-store',
    })


@router.delete('/assessments/{report_id}', status_code=204)
def delete_snapshot(report_id: str, x_report_token: str | None = Header(default=None),
                    db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    entry = get_authorized_snapshot(report_id, x_report_token, db)
    db.delete(entry)
    db.commit()
