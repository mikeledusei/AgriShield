"""Reported historical crop outcomes, separate from model predictions.

The CSV is parsed once and cached on (path, mtime), so a page load costs one parse
instead of two. A malformed row is skipped and reported, never allowed to take down
the whole endpoint.
"""
import csv
from threading import Lock

from core.auth import get_current_user
from core.config import PROJECT_ROOT
from fastapi import APIRouter, Depends, HTTPException
from seed_counties import COUNTY_METADATA
from services import logging_service

router = APIRouter(prefix='/outcomes', tags=['Reported crop outcomes'])
DATA = PROJECT_ROOT / 'data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv'
PROVENANCE = (
    'Third-party mirror of a county maize workbook attributed to Kilimodata/KNBS. '
    'The primary workbook and redistribution terms were not independently verified. '
    'Annual reported yield is not a real-time loss observation or an agricultural risk forecast.'
)

_lock = Lock()
_cache: tuple[tuple[str, float], list[dict]] | None = None


def _parse() -> list[dict]:
    with DATA.open(encoding='utf-8', newline='') as file:
        raw_rows = list(csv.DictReader(file))
    if not raw_rows:
        raise ValueError('empty file')
    rows, skipped = [], 0
    for raw in raw_rows:
        county = (raw.get('county') or '').strip()
        if county not in COUNTY_METADATA:
            skipped += 1
            continue
        try:
            year = int(raw['year'])
            flag = (raw.get('quality_flag') or '').strip()
            usable = flag == 'ok'
            rows.append({
                'county': county,
                'year': year,
                'quality_flag': flag or 'unknown',
                'yield_tonnes_per_ha': float(raw['yield_tonnes_per_ha']) if usable else None,
                'harvested_area_ha': float(raw['harvested_area_ha']) if usable else None,
                'production_tonnes': float(raw['production_tonnes']) if usable else None,
            })
        except (KeyError, TypeError, ValueError):
            skipped += 1
    if skipped:
        logging_service.warning('Skipped %s unusable reported-outcome rows in %s', skipped, DATA.name)
    if not rows:
        raise ValueError('no usable rows')
    return rows


def _rows() -> list[dict]:
    global _cache
    if not DATA.exists():
        raise HTTPException(status_code=503, detail='Reported maize outcome data is not installed.')
    stamp = (str(DATA), DATA.stat().st_mtime)
    with _lock:
        if _cache is not None and _cache[0] == stamp:
            return _cache[1]
    try:
        rows = _parse()
    except (OSError, ValueError, csv.Error):
        logging_service.exception('Reported maize outcome data could not be read')
        raise HTTPException(status_code=503, detail='Reported maize outcome data could not be read.') from None
    with _lock:
        _cache = (stamp, rows)
    return rows


@router.get('/maize-years')
def maize_years(user: dict = Depends(get_current_user)):
    return sorted({row['year'] for row in _rows()}, reverse=True)


@router.get('/maize')
def maize_outcomes(year: int, user: dict = Depends(get_current_user)):
    selected = [row for row in _rows() if row['year'] == year]
    if not selected:
        raise HTTPException(status_code=404, detail='No reported maize outcomes are available for that year.')
    observations = [
        {key: row[key] for key in
         ('county', 'yield_tonnes_per_ha', 'harvested_area_ha', 'production_tonnes', 'quality_flag')}
        for row in sorted(selected, key=lambda item: item['county'])
    ]
    return {
        'year': year,
        'source': PROVENANCE,
        'source_page': 'https://nipfn.knbs.or.ke/download/maize-production-by-county-2012-2020/',
        'mirror': 'https://github.com/Msang-dev/kenya-maize-forecast/blob/main/Maize-Production-2012-2020-Combined.xlsx',
        'observations': observations,
    }
