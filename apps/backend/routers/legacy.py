"""Version-specific endpoints removed from the product.

These paths used to score without user inputs, expose stored files, or regenerate
a different report on each download. They now answer **410 Gone** with a pointer to
the strict replacement, and the retirement is explicit per path: an earlier
``/predictions/{path:path}`` catch-all silently shadowed every live route under
``/predictions`` (and would have kept shadowing future ones).
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=['Retired APIs'])

MESSAGE = (
    'This endpoint was retired because it could return assumed or misleading results. '
    'Use /api/v1/predictions/from-inputs, /from-measurements, /from-csv, '
    '/predictions/historical-observations or /reports/assessments instead.'
)

#: (path, methods) pairs that must keep answering 410.
RETIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('/predictions/crop-yield', ('POST',)),
    ('/predictions/forecast', ('POST',)),
    ('/predictions/scenario', ('POST',)),
    ('/predictions/batch', ('GET', 'POST')),
    ('/predictions/compare', ('POST',)),
    ('/predictions/region', ('POST',)),
    ('/predictions/explain', ('GET',)),
    ('/predictions/months', ('GET',)),
    ('/predictions/history', ('GET',)),
    ('/reports/create', ('POST',)),
    ('/reports/{report_id}/pdf', ('GET',)),
    ('/upload/analyze', ('POST',)),
    ('/uploads/analyze', ('POST',)),
    ('/storage/upload', ('POST',)),
    ('/storage/delete/{file_path:path}', ('DELETE',)),
)


def retired() -> None:
    raise HTTPException(status_code=410, detail=MESSAGE)


def _make_retired(path: str):
    def endpoint() -> None:  # pragma: no cover - always raises
        retired()

    return endpoint


for _path, _methods in RETIRED:
    router.add_api_route(
        _path,
        _make_retired(_path),
        methods=list(_methods),
        include_in_schema=False,
        summary='Retired endpoint',
        responses={410: {'description': 'Retired: use the documented strict endpoints'}},
    )
