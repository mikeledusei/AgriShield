"""Opt-in, private, recoverable assessment history protected by a capability key."""
import hashlib
import json
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from core.auth import get_current_user
from core.database import get_db
from database.models import HistoryRecord
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from routers.manual_predictions import render_assessment_pdf
from schemas.manual_prediction import ManualPredictionRequest
from services import logging_service
from services.analysis_service import historical_evidence, manual_evidence
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(prefix='/history', tags=['Private assessment history'])
HISTORY_DAYS = 90


def now_utc():
    return datetime.now(UTC).replace(tzinfo=None)


def key_digest(key: str | None) -> str:
    if not key or not re.fullmatch(r'[A-Za-z0-9_-]{43}', key):
        raise HTTPException(status_code=401, detail='A valid private history key is required.')
    return hashlib.sha256(key.encode('ascii')).hexdigest()


def purge_history(db, now=None):
    """Delete records past retention. Indexed on created_at."""
    return (
        db.query(HistoryRecord)
        .filter(HistoryRecord.created_at < (now or now_utc()) - timedelta(days=HISTORY_DAYS))
        .delete(synchronize_session=False)
    )


@router.post('/key')
def new_key(response: Response, user: dict = Depends(get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    return {'key': secrets.token_urlsafe(32), 'retention_days': HISTORY_DAYS}


class SaveAssessment(BaseModel):
    inputs: ManualPredictionRequest
    expected_model_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_probability: float = Field(ge=0, le=1, allow_inf_nan=False)


class SaveHistorical(BaseModel):
    county_name: str = Field(min_length=1, max_length=100)
    month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')


def save_evidence(evidence, key, db):
    digest = key_digest(key)
    result = dict(evidence['assessment'])
    result['data_source'] = evidence['source_note']
    if evidence['kind'] == 'historical':
        result['report_context'] = {'national': evidence['national'], 'trend': evidence['trend']}
    now = now_utc()
    result['snapshot_created_at'] = now.isoformat() + 'Z'
    record = HistoryRecord(id=str(uuid.uuid4()), history_key_hash=digest,
                           snapshot_json=json.dumps(result, allow_nan=False), created_at=now)
    try:
        purge_history(db, now)
        db.add(record)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logging_service.exception('Could not persist history record')
        raise HTTPException(status_code=503, detail='Could not save history.') from None
    except (TypeError, ValueError):
        db.rollback()
        logging_service.exception('History record is not serialisable')
        raise HTTPException(status_code=500, detail='The saved assessment could not be serialised.') from None
    return {'id': record.id, 'created_at': result['snapshot_created_at'], 'retention_days': HISTORY_DAYS}


@router.post('/assessments', status_code=201)
def save_assessment(req: SaveAssessment, response: Response, x_history_key: str | None = Header(default=None),
                    db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    key_digest(x_history_key)
    response.headers['Cache-Control'] = 'no-store'
    return save_evidence(manual_evidence(req.inputs, req.expected_model_sha256, req.expected_probability), x_history_key, db)


@router.post('/historical', status_code=201)
def save_historical(req: SaveHistorical, response: Response, x_history_key: str | None = Header(default=None),
                    db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    key_digest(x_history_key)
    response.headers['Cache-Control'] = 'no-store'
    return save_evidence(historical_evidence(req.county_name, req.month), x_history_key, db)


def authorized(record_id, key, db):
    digest = key_digest(key)
    record = db.get(HistoryRecord, record_id)
    if not record or not secrets.compare_digest(record.history_key_hash, digest) or record.created_at < now_utc() - timedelta(days=HISTORY_DAYS):
        raise HTTPException(status_code=404, detail='Saved assessment not found or expired.')
    return record


@router.get('/records')
def list_records(response: Response, x_history_key: str | None = Header(default=None), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    digest = key_digest(x_history_key)
    response.headers['Cache-Control'] = 'no-store'
    records = db.query(HistoryRecord).filter(HistoryRecord.history_key_hash == digest, HistoryRecord.created_at >= now_utc() - timedelta(days=HISTORY_DAYS)).order_by(HistoryRecord.created_at.desc()).limit(500).all()
    result = []
    for record in records:
        try:
            snapshot = json.loads(record.snapshot_json)
            result.append({
                'id': record.id,
                'county': snapshot['county_name'],
                'period': snapshot['period'],
                'score': snapshot['score'],
                'band': snapshot['band'],
                'extrapolated': bool(snapshot.get('extrapolated')),
                'created_at': record.created_at.isoformat() + 'Z',
            })
        except (ValueError, KeyError):
            # One damaged record must not hide the rest of the user's history.
            logging_service.error('Skipping unreadable history record %s', record.id)
    return {'records': result, 'retention_days': HISTORY_DAYS, 'limit': 500}


@router.get('/records/{record_id}')
def get_record(record_id: str, response: Response, x_history_key: str | None = Header(default=None), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    return json.loads(authorized(record_id, x_history_key, db).snapshot_json)


@router.get('/records/{record_id}/pdf')
def history_pdf(record_id: str, x_history_key: str | None = Header(default=None), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    result = json.loads(authorized(record_id, x_history_key, db).snapshot_json)
    return StreamingResponse(render_assessment_pdf(result), media_type='application/pdf',
                             headers={'Cache-Control': 'no-store', 'Content-Disposition': 'attachment; filename=agrishield-history.pdf'})


@router.delete('/records/{record_id}', status_code=204)
def delete_record(record_id: str, x_history_key: str | None = Header(default=None), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db.delete(authorized(record_id, x_history_key, db))
    db.commit()
