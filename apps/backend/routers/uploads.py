"""File upload endpoints."""
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import settings
from core.database import get_db
from database import crud
from schemas.pydantic_models import UploadResponse
from agents import file_processor

router = APIRouter(prefix="/upload", tags=["uploads"])

ALLOWED_TYPES = {"csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"}


@router.post("/analyze", response_model=UploadResponse)
async def upload_and_analyze(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    raw_name = (file.filename or "").strip()
    if not raw_name or "." not in raw_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid file extension.",
        )

    file_ext = Path(raw_name).suffix.lower().lstrip(".")
    if file_ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds maximum size limit of 10 MB.",
        )

    result = file_processor.process(Path(raw_name).name, file_ext, file_bytes)

    try:
        crud.save_upload(
            db,
            file_name=result.file_name,
            file_type=result.file_type,
            county_name=result.extracted_data.county_name,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
        )
    except Exception:
        db.rollback()

    return result
