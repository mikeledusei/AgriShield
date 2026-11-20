"""Regenerate the simplified county GeoJSON used by the dashboard map.

The full-resolution boundary file has 166k vertices (6.8 MB). Sending that to the
browser on every page load is wasteful, so the map uses a Douglas-Peucker
simplification (~8k vertices, ~320 KB). Run this after replacing the full file:

    python apps/frontend/scripts/simplify_geojson.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def _simplify_ring(points: list[list[float]], tolerance: float) -> list[list[float]]:
    """Douglas-Peucker on a closed ring, keeping the first and last point."""
    if len(points) < 4:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        x0, y0 = points[start][:2]
        x1, y1 = points[end][:2]
        dx, dy = x1 - x0, y1 - y0
        norm = (dx * dx + dy * dy) ** 0.5
        best, best_index = -1.0, -1
        for index in range(start + 1, end):
            px, py = points[index][:2]
            if norm == 0:
                distance = ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
            else:
                distance = abs(dy * px - dx * py + x1 * y0 - y1 * x0) / norm
            if distance > best:
                best, best_index = distance, index
        if best > tolerance:
            keep[best_index] = True
            stack.append((start, best_index))
            stack.append((best_index, end))
    simplified = [point for point, kept in zip(points, keep, strict=True) if kept]
    return simplified if len(simplified) >= 4 else points


def simplify(geojson: dict, tolerance: float) -> dict:
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        rings = geometry.get("coordinates") or []
        if geometry.get("type") == "Polygon":
            geometry["coordinates"] = [_simplify_ring(ring, tolerance) for ring in rings]
        elif geometry.get("type") == "MultiPolygon":
            geometry["coordinates"] = [
                [_simplify_ring(ring, tolerance) for ring in polygon] for polygon in rings
            ]
    return geojson


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ASSETS / "kenya_counties.geojson")
    parser.add_argument("--target", type=Path, default=ASSETS / "kenya_counties_simplified.geojson")
    parser.add_argument("--tolerance", type=float, default=0.01, help="Degrees; ~1 km at the equator.")
    args = parser.parse_args()

    geojson = json.loads(args.source.read_text(encoding="utf-8"))
    source_count = sum(len(ring) for feature in geojson["features"] for ring in _all_rings(feature))
    simplify(geojson, args.tolerance)
    target_count = sum(len(ring) for feature in geojson["features"] for ring in _all_rings(feature))

    args.target.write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")
    print(
        f"{args.source.name}: {source_count:,} vertices -> {args.target.name}: {target_count:,} "
        f"({args.target.stat().st_size / 1024:.0f} KB)"
    )
    return 0


def _all_rings(feature: dict):
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    if geometry.get("type") == "Polygon":
        return coordinates
    if geometry.get("type") == "MultiPolygon":
        return [ring for polygon in coordinates for ring in polygon]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
