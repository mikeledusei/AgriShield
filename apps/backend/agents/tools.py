"""Evidence-grounded historical lookup available to the Gria agent."""
from langchain_core.tools import tool


@tool
def get_current_county_risk(county_name: str, month: str) -> dict:
    """Get a historical vegetation-stress proxy score for an explicit YYYY-MM period, not a current warning or confirmed loss."""
    try:
        from routers.manual_predictions import historical_observations
        from seed_counties import normalize_county_name
        data = historical_observations(month)
        county = normalize_county_name(county_name)
        result = next((item for item in data['observations'] if item['county'] == county), None)
        if result is None:
            return {'error': 'No complete historical observation exists for that county and month.'}
        return {'county': county, 'period': month, 'risk_score': result['score'],
                'score_band': result['band'], 'model_used': data['model_used']}
    except Exception:
        return {'error': 'Could not evaluate this county and month.'}
