"""Predictions API: county, history, batch, compare, region, scenario."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from database import models
from schemas import predictions as sch
from seed_counties import ensure_counties_seeded, normalize_county_name
from services.prediction_service import CountyNotFoundError, get_engine

router = APIRouter(prefix="/predictions", tags=["Predictions"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _predict(engine, db, name, focus=None, persist=True) -> sch.PredictionOut:
    try:
        return sch.PredictionOut(**engine.predict(db, name, focus, persist=persist))
    except CountyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/crop-yield", response_model=sch.PredictionOut)
def crop_yield(
    req: sch.CountyPredictionRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    return _predict(get_engine(), db, req.county_name, req.focus, persist=True)


@router.get("/history")
def prediction_history(
    county_name: str,
    months: int = Query(default=12, ge=1, le=120),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    engine = get_engine()
    try:
        county = engine._get_county(db, county_name)
    except CountyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    cutoff = _utcnow() - timedelta(days=31 * months)
    rows = []
    if getattr(county, "id", 0):
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

    if rows and len(rows) >= 2:
        trend = [
            {
                "date": r.created_at.isoformat(),
                "risk_score": int(round(r.risk_score)),
                "risk_level": r.risk_level,
            }
            for r in reversed(rows)
        ]
    else:
        trend = engine.get_historical_series(county.name, months=months)

    return {
        "county_name": county.name,
        "months": months,
        "trend": trend,
    }


@router.get("/batch", response_model=sch.BatchResponse)
def batch_predictions(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ensure_counties_seeded(db)
    engine = get_engine()
    counties = db.query(models.County).order_by(models.County.name).all()
    preds = [
        sch.PredictionOut(**engine.predict_for_county_obj(db, c, persist=False))
        for c in counties
    ]
    return sch.BatchResponse(
        generated_at=_utcnow().isoformat(),
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
    preds = [_predict(engine, db, name, persist=False) for name in req.counties]
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
        sch.PredictionOut(**engine.predict_for_county_obj(db, c, persist=False))
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
