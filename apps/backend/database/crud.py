"""Reusable database operations."""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import models


# ---------- Counties ----------
def get_county_by_name(db: Session, name: str):
    return db.query(models.County).filter(models.County.name == name).first()


def get_all_counties(db: Session):
    return db.query(models.County).all()


def get_counties_by_region(db: Session, region: str):
    return db.query(models.County).filter(models.County.region == region).all()


# ---------- Features ----------
def get_latest_features(db: Session, county_id: int):
    return (
        db.query(models.CountyFeature)
        .filter(models.CountyFeature.county_id == county_id)
        .order_by(desc(models.CountyFeature.record_date))
        .first()
    )


# ---------- Predictions ----------
def save_prediction(db: Session, county_id: int, focus: str, risk_score: float,
                    risk_level: str, main_driver: str, recommendation: str):
    prediction = models.Prediction(
        county_id=county_id,
        focus=focus,
        risk_score=risk_score,
        risk_level=risk_level,
        main_driver=main_driver,
        recommendation=recommendation,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def get_county_predictions(db: Session, county_id: int, limit: int = 12):
    return (
        db.query(models.Prediction)
        .filter(models.Prediction.county_id == county_id)
        .order_by(desc(models.Prediction.created_at))
        .limit(limit)
        .all()
    )


# ---------- Reports ----------
def save_report(db: Session, county_id: int, report_type: str, detailed: bool,
                file_path: str):
    report = models.Report(
        county_id=county_id,
        report_type=report_type,
        detailed=detailed,
        file_path=file_path,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


# ---------- Chat ----------
def save_chat_message(db: Session, county_name: str, user_message: str,
                      gria_reply: str, risk_score: float = None):
    message = models.ChatMessage(
        county_name=county_name,
        user_message=user_message,
        gria_reply=gria_reply,
        risk_score=risk_score,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


# ---------- Uploads ----------
def save_upload(db: Session, file_name: str, file_type: str, county_name: str,
                risk_score: float, risk_level: str):
    upload = models.Upload(
        file_name=file_name,
        file_type=file_type,
        county_name=county_name,
        risk_score=risk_score,
        risk_level=risk_level,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload