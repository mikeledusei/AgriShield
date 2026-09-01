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
    db = SessionLocal()
    try:
        result = prediction_service.predict_county(db, county_name, "crops")
        return {
            "county": result["county_name"],
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
            "main_driver": result["main_driver"],
            "recommendation": result["recommendation"]
        }
    except Exception as e:
        return {"error": f"Could not fetch risk for {county_name}: {str(e)}"}
    finally:
        db.close()

@tool
def get_historical_trends(county_name: str) -> list:
    """
    Get the historical risk trends for a specific Kenyan county over the last 12 months.
    Use this when the user asks about past data, trends, or how conditions have changed.
    """
    db = SessionLocal()
    try:
        county = crud.get_county_by_name(db, county_name)
        if not county:
            return [{"error": f"County '{county_name}' not found in database."}]
            
        predictions = crud.get_county_predictions(db, county.id, limit=12)
        if not predictions:
            return [{"info": f"No historical data available yet for {county_name}."}]
            
        return [
            {
                "date": p.created_at.strftime("%Y-%m-%d"), 
                "risk_score": p.risk_score, 
                "risk_level": p.risk_level
            }
            for p in predictions
        ]
    finally:
        db.close()

@tool
def compare_two_counties(county_1: str, county_2: str) -> dict:
    """
    Compare the current risk levels of two different Kenyan counties.
    Use this when the user wants to know which county is safer or more at risk.
    """
    db = SessionLocal()
    try:
        res1 = prediction_service.predict_county(db, county_1, "crops")
        res2 = prediction_service.predict_county(db, county_2, "crops")
        return {
            "county_1": {"name": res1["county_name"], "score": res1["risk_score"], "level": res1["risk_level"]},
            "county_2": {"name": res2["county_name"], "score": res2["risk_score"], "level": res2["risk_level"]}
        }
    finally:
        db.close()