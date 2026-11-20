"""GeoJSON loading and county centroids for the dashboard.

The 6.8 MB county GeoJSON is parsed once per server process, not once per rerun
(Streamlit reruns the whole script on every interaction). Centroids are computed
from the polygons because the file carries no latitude/longitude properties — an
earlier version read those missing properties and silently plotted every county
at (0, 0) off the coast of Africa.
"""
import json
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parents[1] / "assets"
# The simplified file (166k vertices -> 8k, 6.8 MB -> 320 KB) is what the map renders.
# It is generated from the full-resolution copy by scripts/simplify_geojson.py; the
# full file stays for GIS use and higher-detail exports.
GEOJSON_PATH = ASSETS / "kenya_counties_simplified.geojson"
FULL_GEOJSON_PATH = ASSETS / "kenya_counties.geojson"


def _rings(geometry: dict) -> list[list]:
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [ring for ring in coordinates if ring]
    if kind == "MultiPolygon":
        return [ring for polygon in coordinates for ring in polygon if ring]
    return []


def _centroid(geometry: dict) -> tuple[float, float] | None:
    """Area-weighted polygon centroid in (longitude, latitude)."""
    total_area = 0.0
    cx = cy = 0.0
    for ring in _rings(geometry):
        area = cross_x = cross_y = 0.0
        for index in range(len(ring) - 1):
            x0, y0 = ring[index][0], ring[index][1]
            x1, y1 = ring[index + 1][0], ring[index + 1][1]
            cross = x0 * y1 - x1 * y0
            area += cross
            cross_x += (x0 + x1) * cross
            cross_y += (y0 + y1) * cross
        area /= 2.0
        if area == 0:
            continue
        total_area += area
        cx += cross_x / (6.0 * area) * abs(area)
        cy += cross_y / (6.0 * area) * abs(area)
    if not total_area:
        return None
    return cx / abs(total_area), cy / abs(total_area)


@st.cache_data(show_spinner=False)
def load_geojson() -> dict | None:
    """Parsed county GeoJSON, or ``None`` when the asset is missing or invalid."""
    if not GEOJSON_PATH.exists():
        return None
    try:
        return json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@st.cache_data(show_spinner=False)
def county_centroids() -> dict[str, dict[str, float]]:
    """``{county name: {latitude, longitude}}`` derived from the polygons."""
    geo = load_geojson() or {}
    centroids: dict[str, dict[str, float]] = {}
    for feature in geo.get("features", []):
        name = (feature.get("properties") or {}).get("county")
        if not name:
            continue
        point = _centroid(feature.get("geometry") or {})
        if point is None:
            continue
        longitude, latitude = point
        centroids[name] = {"latitude": round(latitude, 5), "longitude": round(longitude, 5)}
    return centroids


def county_names() -> list[str]:
    geo = load_geojson() or {}
    return [
        (feature.get("properties") or {}).get("county")
        for feature in geo.get("features", [])
        if (feature.get("properties") or {}).get("county")
    ]
