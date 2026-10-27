"""Frontend constants for AgriShield."""
import os
from shared.kenya_counties import KENYA_COUNTIES, REGIONS as KENYA_REGIONS

API_BASE_URL = os.getenv("AGRISHIELD_API_URL", "http://127.0.0.1:8000/api/v1")
API_TIMEOUT_SECONDS = int(os.getenv("AGRISHIELD_API_TIMEOUT", "15"))

RISK_LEVELS = {
    "SAFE": {"min": 0, "max": 24, "color": "#22c55e", "label": "SAFE"},
    "MODERATE": {"min": 25, "max": 49, "color": "#eab308", "label": "MODERATE"},
    "HIGH": {"min": 50, "max": 74, "color": "#f97316", "label": "HIGH"},
    "CRITICAL": {"min": 75, "max": 100, "color": "#ef4444", "label": "CRITICAL"},
}

__all__ = [
    "API_BASE_URL",
    "API_TIMEOUT_SECONDS",
    "KENYA_COUNTIES",
    "KENYA_REGIONS",
    "RISK_LEVELS",
]
