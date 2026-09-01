"""Retrieval of observed county feature records."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import CountyFeature
FEATURE_COLUMNS = ("rainfall_anomaly_30d", "ndvi_pasture_index", "temp_max_avg", "soil_moisture_deficit")


def get_latest_features(db: Session, county_id: int) -> dict[str, float]:
    feature = db.scalar(select(CountyFeature).where(CountyFeature.county_id == county_id).order_by(CountyFeature.record_date.desc()))
    if feature is None:
        raise HTTPException(status_code=404, detail="No feature observations exist for this county.")
    return {column: float(getattr(feature, column)) for column in FEATURE_COLUMNS}
