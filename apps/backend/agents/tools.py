"""
Tools available to the Gria Agentic AI.
These functions allow the LLM to interact with the AgriShield backend and database.
"""
from langchain_core.tools import tool
from database.connection import SessionLocal
from database import crud
from services import prediction_service


@tool
def get_current_county_risk(county_name: str) -> dict:
    """
    Get the current agricultural risk score, risk level, and main driver
    for a specific Kenyan county. Use this when the user asks about current
    conditions, safety, or risk levels.
    """
    db = SessionLocal() if SessionLocal is not None else None
    try:
        result = prediction_service.predict(db, county_name, "crops", persist=False)
        return {
            "county": result["county_name"],
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
            "main_driver": result["main_driver"],
            "recommendation": result["recommendation"],
            "model_used": result.get("model_used", "lightgbm_v1"),
        }
    except Exception as e:
        return {"error": f"Could not fetch risk for {county_name}: {str(e)}"}
    finally:
        if db is not None:
            db.close()


@tool
def get_historical_trends(county_name: str) -> list:
    """
    Get the historical risk trends for a specific Kenyan county over the last 12 months.
    Use this when the user asks about past data, trends, or how conditions have changed.
    """
    db = SessionLocal() if SessionLocal is not None else None
    try:
        if db is not None:
            county = crud.get_county_by_name(db, county_name)
            if county:
                predictions = crud.get_county_predictions(db, county.id, limit=12)
                if predictions and len(predictions) >= 2:
                    return [
                        {
                            "date": p.created_at.strftime("%Y-%m-%d"),
                            "risk_score": p.risk_score,
                            "risk_level": p.risk_level,
                        }
                        for p in predictions
                    ]

        series = prediction_service.get_engine().get_historical_series(county_name, months=12)
        if series:
            return series
        return [{"info": f"No historical data available yet for {county_name}."}]
    finally:
        if db is not None:
            db.close()


@tool
def compare_two_counties(county_1: str, county_2: str) -> dict:
    """
    Compare the current risk levels of two different Kenyan counties.
    Use this when the user wants to know which county is safer or more at risk.
    """
    db = SessionLocal() if SessionLocal is not None else None
    try:
        res1 = prediction_service.predict(db, county_1, "crops", persist=False)
        res2 = prediction_service.predict(db, county_2, "crops", persist=False)
        return {
            "county_1": {
                "name": res1["county_name"],
                "score": res1["risk_score"],
                "level": res1["risk_level"],
            },
            "county_2": {
                "name": res2["county_name"],
                "score": res2["risk_score"],
                "level": res2["risk_level"],
            },
        }
    except Exception as e:
        return {"error": f"Could not compare {county_1} and {county_2}: {str(e)}"}
    finally:
        if db is not None:
            db.close()
