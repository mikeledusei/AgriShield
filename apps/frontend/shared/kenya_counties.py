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

COUNTY_LOCATIONS: Dict[str, Dict[str, float]] = {
    "Baringo": {"lat": 0.482, "lon": 35.972},
    "Bomet": {"lat": -0.78, "lon": 35.342},
    "Bungoma": {"lat": 0.563, "lon": 34.561},
    "Busia": {"lat": 0.46, "lon": 34.111},
    "Elgeyo Marakwet": {"lat": 1.051, "lon": 35.57},
    "Embu": {"lat": -0.533, "lon": 37.456},
    "Garissa": {"lat": -0.453, "lon": 39.646},
    "Homa Bay": {"lat": -0.523, "lon": 34.457},
    "Isiolo": {"lat": 0.354, "lon": 37.586},
    "Kajiado": {"lat": -1.85, "lon": 36.78},
    "Kakamega": {"lat": 0.282, "lon": 34.751},
    "Kericho": {"lat": -0.367, "lon": 35.283},
    "Kiambu": {"lat": -1.117, "lon": 36.817},
    "Kilifi": {"lat": -3.63, "lon": 39.8499},
    "Kirinyaga": {"lat": -0.5, "lon": 37.27},
    "Kisii": {"lat": -0.673, "lon": 34.786},
    "Kisumu": {"lat": -0.102, "lon": 34.761},
    "Kitui": {"lat": -1.367, "lon": 38.019},
    "Kwale": {"lat": -4.174, "lon": 39.452},
    "Laikipia": {"lat": 0.276, "lon": 36.827},
    "Lamu": {"lat": -2.268, "lon": 40.902},
    "Machakos": {"lat": -1.517, "lon": 37.266},
    "Makueni": {"lat": -1.784, "lon": 37.623},
    "Mandera": {"lat": 3.936, "lon": 41.857},
    "Marsabit": {"lat": 2.334, "lon": 37.989},
    "Meru": {"lat": 0.046, "lon": 37.655},
    "Migori": {"lat": -1.063, "lon": 34.473},
    "Mombasa": {"lat": -4.0435, "lon": 39.6682},
    "Murang'a": {"lat": -0.721, "lon": 37.151},
    "Nairobi": {"lat": -1.286, "lon": 36.817},
    "Nakuru": {"lat": -0.303, "lon": 36.08},
    "Nandi": {"lat": 0.177, "lon": 35.109},
    "Narok": {"lat": -1.093, "lon": 35.87},
    "Nyamira": {"lat": -0.562, "lon": 34.935},
    "Nyandarua": {"lat": -0.15, "lon": 36.39},
    "Nyeri": {"lat": -0.417, "lon": 36.95},
    "Samburu": {"lat": 1.172, "lon": 37.071},
    "Siaya": {"lat": -0.061, "lon": 34.288},
    "Taita Taveta": {"lat": -3.4, "lon": 38.35},
    "Tana River": {"lat": -1.93, "lon": 40.1},
    "Tharaka Nithi": {"lat": -0.298, "lon": 37.87},
    "Trans Nzoia": {"lat": 1.019, "lon": 34.99},
    "Turkana": {"lat": 3.117, "lon": 35.606},
    "Uasin Gishu": {"lat": 0.515, "lon": 35.28},
    "Vihiga": {"lat": 0.078, "lon": 34.728},
    "Wajir": {"lat": 1.748, "lon": 40.057},
    "West Pokot": {"lat": 1.516, "lon": 35.116},
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
