"""Retired endpoints that used assumed or silently substituted data."""
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=['Retired APIs'])


def retired():
    raise HTTPException(status_code=410, detail='This legacy endpoint was retired because it could return assumed or misleading results. Use the documented /predictions/from-inputs, /from-measurements, /from-csv, and /historical-* APIs instead.')


@router.api_route('/predictions/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def retired_predictions(path: str):
    return retired()


@router.api_route('/upload/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@router.api_route('/storage/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@router.api_route('/reports/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def retired_unsafe_routes(path: str):
    return retired()
