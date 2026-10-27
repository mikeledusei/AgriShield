"""Canonical Kenya county and region metadata for the AgriShield dashboard."""

from __future__ import annotations

from typing import Dict

REGIONS = [
    "Coast",
    "North Eastern",
    "Eastern",
    "Central",
    "Rift Valley",
    "Western",
    "Nyanza",
    "Nairobi",
]

# Canonical 47 Kenyan county names matching the backend and kenya_counties.geojson
KENYA_COUNTIES = sorted([
    "Baringo",
    "Bomet",
    "Bungoma",
    "Busia",
    "Elgeyo Marakwet",
    "Embu",
    "Garissa",
    "Homa Bay",
    "Isiolo",
    "Kajiado",
    "Kakamega",
    "Kericho",
    "Kiambu",
    "Kilifi",
    "Kirinyaga",
    "Kisii",
    "Kisumu",
    "Kitui",
    "Kwale",
    "Laikipia",
    "Lamu",
    "Machakos",
    "Makueni",
    "Mandera",
    "Marsabit",
    "Meru",
    "Migori",
    "Mombasa",
    "Murang'a",
    "Nairobi",
    "Nakuru",
    "Nandi",
    "Narok",
    "Nyamira",
    "Nyandarua",
    "Nyeri",
    "Samburu",
    "Siaya",
    "Taita Taveta",
    "Tana River",
    "Tharaka Nithi",
    "Trans Nzoia",
    "Turkana",
    "Uasin Gishu",
    "Vihiga",
    "Wajir",
    "West Pokot",
])

COUNTY_COORDINATES: Dict[str, Dict[str, object]] = {
    "Baringo": {"lat": 0.482, "lon": 35.972, "region": "Rift Valley"},
    "Bomet": {"lat": -0.78, "lon": 35.342, "region": "Rift Valley"},
    "Bungoma": {"lat": 0.563, "lon": 34.561, "region": "Western"},
    "Busia": {"lat": 0.46, "lon": 34.111, "region": "Western"},
    "Elgeyo Marakwet": {"lat": 1.051, "lon": 35.57, "region": "Rift Valley"},
    "Embu": {"lat": -0.533, "lon": 37.456, "region": "Eastern"},
    "Garissa": {"lat": -0.453, "lon": 39.646, "region": "North Eastern"},
    "Homa Bay": {"lat": -0.523, "lon": 34.457, "region": "Nyanza"},
    "Isiolo": {"lat": 0.354, "lon": 37.586, "region": "Eastern"},
    "Kajiado": {"lat": -1.85, "lon": 36.78, "region": "Rift Valley"},
    "Kakamega": {"lat": 0.282, "lon": 34.751, "region": "Western"},
    "Kericho": {"lat": -0.367, "lon": 35.283, "region": "Rift Valley"},
    "Kiambu": {"lat": -1.117, "lon": 36.817, "region": "Central"},
    "Kilifi": {"lat": -3.63, "lon": 39.8499, "region": "Coast"},
    "Kirinyaga": {"lat": -0.5, "lon": 37.27, "region": "Central"},
    "Kisii": {"lat": -0.673, "lon": 34.786, "region": "Nyanza"},
    "Kisumu": {"lat": -0.102, "lon": 34.761, "region": "Nyanza"},
    "Kitui": {"lat": -1.367, "lon": 38.019, "region": "Eastern"},
    "Kwale": {"lat": -4.174, "lon": 39.452, "region": "Coast"},
    "Laikipia": {"lat": 0.276, "lon": 36.827, "region": "Rift Valley"},
    "Lamu": {"lat": -2.268, "lon": 40.902, "region": "Coast"},
    "Machakos": {"lat": -1.517, "lon": 37.266, "region": "Eastern"},
    "Makueni": {"lat": -1.784, "lon": 37.623, "region": "Eastern"},
    "Mandera": {"lat": 3.936, "lon": 41.857, "region": "North Eastern"},
    "Marsabit": {"lat": 2.334, "lon": 37.989, "region": "Eastern"},
    "Meru": {"lat": 0.046, "lon": 37.655, "region": "Eastern"},
    "Migori": {"lat": -1.063, "lon": 34.473, "region": "Nyanza"},
    "Mombasa": {"lat": -4.0435, "lon": 39.6682, "region": "Coast"},
    "Murang'a": {"lat": -0.721, "lon": 37.151, "region": "Central"},
    "Nairobi": {"lat": -1.286, "lon": 36.817, "region": "Nairobi"},
    "Nakuru": {"lat": -0.303, "lon": 36.08, "region": "Rift Valley"},
    "Nandi": {"lat": 0.177, "lon": 35.109, "region": "Rift Valley"},
    "Narok": {"lat": -1.093, "lon": 35.87, "region": "Rift Valley"},
    "Nyamira": {"lat": -0.562, "lon": 34.935, "region": "Nyanza"},
    "Nyandarua": {"lat": -0.15, "lon": 36.39, "region": "Central"},
    "Nyeri": {"lat": -0.417, "lon": 36.95, "region": "Central"},
    "Samburu": {"lat": 1.172, "lon": 37.071, "region": "Rift Valley"},
    "Siaya": {"lat": -0.061, "lon": 34.288, "region": "Nyanza"},
    "Taita Taveta": {"lat": -3.4, "lon": 38.35, "region": "Coast"},
    "Tana River": {"lat": -1.93, "lon": 40.1, "region": "Coast"},
    "Tharaka Nithi": {"lat": -0.298, "lon": 37.87, "region": "Eastern"},
    "Trans Nzoia": {"lat": 1.019, "lon": 34.99, "region": "Rift Valley"},
    "Turkana": {"lat": 3.117, "lon": 35.606, "region": "Rift Valley"},
    "Uasin Gishu": {"lat": 0.515, "lon": 35.28, "region": "Rift Valley"},
    "Vihiga": {"lat": 0.078, "lon": 34.728, "region": "Western"},
    "Wajir": {"lat": 1.748, "lon": 40.057, "region": "North Eastern"},
    "West Pokot": {"lat": 1.516, "lon": 35.116, "region": "Rift Valley"},
}

COUNTY_LOCATIONS: Dict[str, Dict[str, float]] = {
    k: {"lat": float(v["lat"]), "lon": float(v["lon"])}
    for k, v in COUNTY_COORDINATES.items()
}

COUNTY_ALIASES: Dict[str, str] = {
    "muranga": "Murang'a",
    "murang'a": "Murang'a",
    "taita-taveta": "Taita Taveta",
    "taita taveta": "Taita Taveta",
    "tharaka-nithi": "Tharaka Nithi",
    "tharaka nithi": "Tharaka Nithi",
    "tharaka": "Tharaka Nithi",
    "elgeyo-marakwet": "Elgeyo Marakwet",
    "elgeyo marakwet": "Elgeyo Marakwet",
    "keiyo-marakwet": "Elgeyo Marakwet",
    "keiyo marakwet": "Elgeyo Marakwet",
    "homabay": "Homa Bay",
    "homa bay": "Homa Bay",
    "homa-bay": "Homa Bay",
    "trans-nzoia": "Trans Nzoia",
    "trans nzoia": "Trans Nzoia",
    "uasin-gishu": "Uasin Gishu",
    "uasin gishu": "Uasin Gishu",
    "tana-river": "Tana River",
    "tana river": "Tana River",
    "west-pokot": "West Pokot",
    "west pokot": "West Pokot",
    "nairobi city": "Nairobi",
}
for _c in KENYA_COUNTIES:
    COUNTY_ALIASES[_c.lower()] = _c


def normalize_county_name(name: str | None) -> str:
    """Resolve hyphenated or variant county names to canonical 47-county names."""
    if not name:
        return ""
    cleaned = " ".join(str(name).strip().split())
    lower = cleaned.lower()
    if lower in COUNTY_ALIASES:
        return COUNTY_ALIASES[lower]
    no_hyphen = lower.replace("-", " ")
    if no_hyphen in COUNTY_ALIASES:
        return COUNTY_ALIASES[no_hyphen]
    return cleaned


def get_county_coords(name: str | None) -> Dict[str, float]:
    """Return latitude/longitude for any canonical or alias county name."""
    canonical = normalize_county_name(name)
    return COUNTY_LOCATIONS.get(canonical, {"lat": -1.286, "lon": 36.817})
