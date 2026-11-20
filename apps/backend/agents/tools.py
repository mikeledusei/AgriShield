"""Evidence-grounded historical lookup available to the Gria agent.

The tool resolves the county and period directly, so it does not depend on an HTTP
route signature (an earlier version imported ``historical_observations`` from the
router and broke whenever that signature changed).
"""
import pandas as pd
from langchain_core.tools import tool
from seed_counties import normalize_county_name
from services.prediction_service import get_engine


@tool
def get_current_county_risk(county_name: str, month: str) -> dict:
    """Get a historical vegetation-stress proxy score for an explicit YYYY-MM period, not a current warning or confirmed loss."""
    engine = get_engine()
    county = normalize_county_name(county_name)
    history = engine.county_history.get(county)
    if history is None:
        return {'error': 'No historical data exists for that county.'}
    rows = history[history['year_month'].astype(str) == str(month)]
    if rows.empty:
        return {'error': 'No complete historical observation exists for that county and month.'}
    if engine.model is None or not engine.feature_cols:
        return {'error': 'The trained model is unavailable.'}
    row = rows.iloc[-1]
    if any(column not in row.index or pd.isna(row[column]) for column in engine.feature_cols):
        return {'error': 'Historical features are incomplete for that county and month.'}
    try:
        result = engine._score(county, str(month), {c: float(row[c]) for c in engine.feature_cols})
    except ValueError:
        return {'error': 'Could not evaluate this county and month.'}
    score, band = result[0], result[1]
    return {
        'county': county,
        'period': str(month),
        'risk_score': score,
        'score_band': band,
        'model_used': result[3],
        'note': 'Historical proxy score; not a live warning or confirmed crop loss.',
    }
