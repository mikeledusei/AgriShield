"""Reported historical crop outcomes, separate from model predictions."""
from pathlib import Path
import csv
from fastapi import APIRouter, Depends, HTTPException
from core.auth import get_current_user
from core.config import PROJECT_ROOT
from seed_counties import COUNTY_METADATA

router = APIRouter(prefix='/outcomes', tags=['Reported crop outcomes'])
DATA = PROJECT_ROOT / 'data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv'
PROVENANCE = ('Third-party mirror of a county maize workbook attributed to Kilimodata/KNBS. '
              'The primary workbook and redistribution terms were not independently verified. '
              'Annual reported yield is not a real-time loss observation or an agricultural risk forecast.')


def _rows():
    if not DATA.exists():
        raise HTTPException(status_code=503, detail='Reported maize outcome data is not installed.')
    try:
        with DATA.open(encoding='utf-8', newline='') as file:
            rows = list(csv.DictReader(file))
        if not rows or any(row['county'] not in COUNTY_METADATA for row in rows):
            raise ValueError('Unknown county')
        return rows
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        raise HTTPException(status_code=503, detail='Reported maize outcome data could not be read.') from exc


@router.get('/maize-years')
def maize_years(user: dict = Depends(get_current_user)):
    return sorted({int(row['year']) for row in _rows()}, reverse=True)


@router.get('/maize')
def maize_outcomes(year: int, user: dict = Depends(get_current_user)):
    selected = [row for row in _rows() if int(row['year']) == year]
    if not selected:
        raise HTTPException(status_code=404, detail='No reported maize outcomes are available for that year.')
    rows = []
    try:
        for row in selected:
            valid = row['quality_flag'] == 'ok'
            rows.append({'county': row['county'], 'yield_tonnes_per_ha': float(row['yield_tonnes_per_ha']) if valid else None,
                         'harvested_area_ha': float(row['harvested_area_ha']) if valid else None,
                         'production_tonnes': float(row['production_tonnes']) if valid else None,
                         'quality_flag': row['quality_flag']})
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail='Reported maize outcome data is invalid.') from exc
    return {'year': year, 'source': PROVENANCE, 'source_page': 'https://nipfn.knbs.or.ke/download/maize-production-by-county-2012-2020/',
            'mirror': 'https://github.com/Msang-dev/kenya-maize-forecast/blob/main/Maize-Production-2012-2020-Combined.xlsx',
            'observations': rows}
