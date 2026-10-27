"""Predictions API: county, forecast, explain, history, batch, compare, region, scenario."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from database import models
from schemas import predictions as sch
from seed_counties import ensure_counties_seeded
from services.prediction_service import CountyNotFoundError, get_engine

router = APIRouter(prefix="/predictions", tags=["Predictions"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _predict(engine, db, name, focus=None, persist=True, month=None) -> sch.PredictionOut:
    try:
        return sch.PredictionOut(
            **engine.predict(db, name, focus, persist=persist, month=month)
        )
    except CountyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/crop-yield", response_model=sch.PredictionOut)
def crop_yield(
    req: sch.CountyPredictionRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    return _predict(
        get_engine(),
        db,
        req.county_name,
        req.focus,
        persist=True,
        month=req.month,
    )


@router.post("/forecast", response_model=sch.FutureForecastResponse)
def forecast_future_risk(
    req: sch.FutureForecastRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Run future risk forecast using Champion Model feature sliders."""
    ensure_counties_seeded(db)
    overrides = {
        "rainfall_mm": req.rainfall_mm,
        "rain_3m_sum": req.rain_3m_sum,
        "rainfall_anomaly": req.rainfall_anomaly,
        "temp_mean_c": req.temp_mean_c,
        "soil_moisture": req.soil_moisture,
        "ndvi_lag1": req.ndvi_lag1,
        "ndvi_lag3": req.ndvi_lag3,
        "ndvi_roll3_mean": req.ndvi_roll3_mean,
        "ndvi_roll3_std": req.ndvi_roll3_std,
        "ndvi_anomaly": req.ndvi_anomaly,
        "forage_dryness_index": req.forage_dryness_index,
        "farming_ratio": req.farming_ratio,
        "livestock_share": req.livestock_share,
        "irrigation_ratio": req.irrigation_ratio,
    }
    try:
        res = get_engine().forecast_future(
            db,
            county_name=req.county_name,
            target_month=req.target_month,
            focus=req.focus,
            auto_derive_indices=req.auto_derive_indices,
            overrides=overrides,
        )
        return sch.FutureForecastResponse(**res)
    except CountyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/explain", response_model=sch.ExplainResponse)
def explain_county_prediction(
    county_name: str,
    month: Optional[str] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return local TreeSHAP contributions and global feature importances for a county."""
    ensure_counties_seeded(db)
    try:
        return sch.ExplainResponse(**get_engine().explain(db, county_name, month=month))
    except CountyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/months", response_model=list[str])
def list_available_months(user: dict = Depends(get_current_user)):
    """Return all available year-month keys (2015-01 to 2025-12)."""
    return get_engine().get_available_months()


@router.get("/history")
def prediction_history(
    county_name: str,
    months: int = Query(default=12, ge=1, le=132),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    engine = get_engine()
    try:
        county = engine._get_county(db, county_name)
    except CountyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Always prefer the rich 2015-2025 county agro-climatic series so charts include rainfall, NDVI, soil moisture, and FDI
    trend = engine.get_historical_series(county.name, months=months)
    if not trend and getattr(county, "id", 0):
        cutoff = _utcnow() - timedelta(days=31 * months)
        rows = (
            db.query(models.Prediction)
            .filter(
                models.Prediction.county_id == county.id,
                models.Prediction.created_at >= cutoff,
            )
            .order_by(desc(models.Prediction.created_at))
            .limit(200)
            .all()
        )
        trend = [
            {
                "date": r.created_at.isoformat(),
                "risk_score": int(round(r.risk_score)),
                "risk_level": r.risk_level,
            }
            for r in reversed(rows)
        ]

    return {
        "county_name": county.name,
        "months": months,
        "trend": trend,
    }


@router.get("/batch", response_model=sch.BatchResponse)
def batch_predictions(
    month: Optional[str] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    engine = get_engine()
    counties = db.query(models.County).order_by(models.County.name).all()
    preds = [
        sch.PredictionOut(
            **engine.predict_for_county_obj(
                db, c, persist=False, month=month, include_shap=False
            )
        )
        for c in counties
    ]
    resolved_m = preds[0].month if preds else month
    return sch.BatchResponse(
        generated_at=_utcnow().isoformat(),
        month=resolved_m,
        county_count=len(preds),
        counties=preds,
    )


@router.post("/compare", response_model=sch.CompareResponse)
def compare_counties(
    req: sch.CompareRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    engine = get_engine()
    preds = [
        _predict(engine, db, name, persist=False, month=req.month)
        for name in req.counties
    ]
    ranked = sorted(preds, key=lambda p: p.risk_score, reverse=True)
    return sch.CompareResponse(
        counties=ranked,
        highest_risk=ranked[0],
        lowest_risk=ranked[-1],
    )


@router.post("/region", response_model=sch.RegionResponse)
def region_aggregation(
    req: sch.RegionRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    engine = get_engine()
    counties = (
        db.query(models.County)
        .filter(models.County.region.ilike(req.region_name.strip()))
        .order_by(models.County.name)
        .all()
    )
    if not counties:
        raise HTTPException(
            status_code=404,
            detail=f"No counties found in region '{req.region_name}'.",
        )
    preds = [
        sch.PredictionOut(
            **engine.predict_for_county_obj(
                db, c, persist=False, month=req.month, include_shap=False
            )
        )
        for c in counties
    ]
    avg = round(sum(p.risk_score for p in preds) / len(preds), 1)
    level = (
        "SAFE"
        if avg < 25
        else "MODERATE"
        if avg < 50
        else "HIGH"
        if avg < 75
        else "CRITICAL"
    )
    return sch.RegionResponse(
        region_name=req.region_name.strip(),
        county_count=len(preds),
        average_risk=avg,
        risk_level=level,
        counties=preds,
    )


@router.post("/scenario", response_model=sch.ScenarioResponse)
def scenario_analysis(
    req: sch.ScenarioRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    try:
        return sch.ScenarioResponse(
            **get_engine().scenario(
                db,
                req.county_name,
                req.rainfall_change_pct,
                req.temp_change_c,
                req.ndvi_shock,
                month=req.month,
            )
        )
    except CountyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/counties", response_model=list[str])
def list_counties(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return list of all 47 available Kenyan counties in the database."""
    ensure_counties_seeded(db)
    counties = db.query(models.County).order_by(models.County.name).all()
    return [c.name for c in counties]
