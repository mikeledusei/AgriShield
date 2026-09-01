"""File upload endpoints."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from database.connection import get_db
from database import crud
from schemas.pydantic_models import UploadResponse
from agents import file_processor

router = APIRouter(prefix="/upload", tags=["uploads"])

ALLOWED_TYPES = {"csv", "xlsx", "xls", "pdf", "docx", "png", "jpg", "jpeg"}


@router.post("/analyze", response_model=UploadResponse)
async def upload_and_analyze(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    file_bytes = await file.read()
    result = file_processor.process(file.filename, file_ext, file_bytes)

    crud.save_upload(
        db,
        file_name=result.file_name,
        file_type=result.file_type,
        county_name=result.extracted_data.county_name,
        risk_score=result.risk_score,
        risk_level=result.risk_level,
    )

    return result