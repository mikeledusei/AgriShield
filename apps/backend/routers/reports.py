"""Reports API: create, list, get reports with PDF generation."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from database import models, crud
from schemas.pydantic_models import ReportRequest
from services.prediction_service import CountyNotFoundError, get_engine
from services.pdf_generator import build as build_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])


class ReportOut(BaseModel):
    id: int
    county_id: int
    report_type: str
    detailed: bool
    file_path: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    reports: list[ReportOut]
    total: int


@router.post("/create", response_model=ReportOut)
def create_report(
    req: ReportRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        engine = get_engine()
        county = db.query(models.County).filter(
            models.County.name.ilike(req.county_name.strip()),
        ).first()
        if county is None:
            raise HTTPException(status_code=404, detail=f"County '{req.county_name}' not found.")
        engine.predict(db, county.name, req.report_type, persist=False)
        saved = crud.save_report(
            db,
            county_id=county.id,
            report_type=req.report_type,
            detailed=req.detailed,
            file_path="",
        )
        return saved
    except CountyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/", response_model=ReportListResponse)
def list_reports(
    report_type: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    query = db.query(models.Report).order_by(desc(models.Report.created_at))
    if report_type:
        query = query.filter(models.Report.report_type == report_type)
    reports = query.limit(limit).all()
    return ReportListResponse(reports=reports, total=len(reports))


def _get_county_name(db: Session, county_id: int) -> str:
    county = db.query(models.County).filter(models.County.id == county_id).first()
    return county.name if county else "Unknown"


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db),
               user: dict = Depends(get_current_user)):
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found.")
    return report


@router.get("/{report_id}/pdf")
def get_report_pdf(report_id: int, db: Session = Depends(get_db),
                   user: dict = Depends(get_current_user)):
    """Generate and stream the PDF for an existing report."""
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found.")
    county_name = _get_county_name(db, report.county_id)
    try:
        prediction = get_engine().predict(db, county_name, persist=False)
    except CountyNotFoundError:
        prediction = {"risk_score": 0, "risk_level": "SAFE", "main_driver": "N/A",
                      "recommendation": ""}
    buffer = build_pdf(county_name, prediction, report.report_type, report.detailed)
    filename = f"AgriShield_Report_{county_name}_{report.id}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})
