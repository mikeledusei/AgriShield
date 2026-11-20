"""Live modelled point weather; never infer agricultural risk from it."""
from datetime import datetime, timezone, timedelta
from threading import Lock
import math
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from core.auth import get_current_user
from seed_counties import COUNTY_METADATA

router = APIRouter(prefix='/live', tags=['Live weather'])
SOURCE = 'https://api.open-meteo.com/v1/forecast'
CACHE_SECONDS = 600
MAX_AGE = timedelta(hours=3)
_lock = Lock()
_cache = None
_cached_at = 0.0


def _retrieve_weather():
    counties = sorted(COUNTY_METADATA)
    params = {'latitude': ','.join(str(COUNTY_METADATA[c]['latitude']) for c in counties),
              'longitude': ','.join(str(COUNTY_METADATA[c]['longitude']) for c in counties),
              'current': 'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m',
              'timezone': 'GMT'}
    response = httpx.get(SOURCE, params=params, timeout=15.0, follow_redirects=False)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or len(data) != len(counties):
        raise ValueError('Incomplete provider response')
    now = datetime.now(timezone.utc)
    items = []
    for index, (county, entry) in enumerate(zip(counties, data)):
        if entry.get('location_id', 0) != index:
            raise ValueError('Provider location ordering does not match county ordering')
        current = entry['current']
        timestamp = datetime.fromisoformat(current['time'])
        timestamp = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp.astimezone(timezone.utc)
        if timestamp > now + timedelta(minutes=30) or now - timestamp > MAX_AGE:
            raise ValueError('Stale or future provider data')
        values = [float(current[k]) for k in ('temperature_2m', 'relative_humidity_2m', 'precipitation', 'wind_speed_10m')]
        if not all(math.isfinite(v) for v in values) or not (-60 <= values[0] <= 60 and 0 <= values[1] <= 100 and 0 <= values[2] <= 500 and 0 <= values[3] <= 500):
            raise ValueError('Invalid weather values')
        interval = int(current['interval'])
        if not 0 < interval <= 3600:
            raise ValueError('Invalid model interval')
        meta = COUNTY_METADATA[county]
        items.append({'county': county, 'latitude': meta['latitude'], 'longitude': meta['longitude'],
                      'time_utc': timestamp.isoformat(), 'temperature_c': values[0], 'humidity_percent': values[1],
                      'precipitation_mm': values[2], 'wind_kmh': values[3], 'interval_seconds': interval})
    return {'source': 'Open-Meteo', 'source_url': 'https://open-meteo.com/', 'retrieved_at': now.isoformat(),
            'description': 'Current modelled weather at one representative point per county; not a county average or an agricultural risk score.',
            'observations': items}


@router.get('/weather')
def live_weather(response: Response, user: dict = Depends(get_current_user)):
    global _cache, _cached_at
    response.headers['Cache-Control'] = 'no-store'
    with _lock:
        if _cache is not None and time.monotonic() - _cached_at < CACHE_SECONDS:
            oldest = min(datetime.fromisoformat(item['time_utc']) for item in _cache['observations'])
            if datetime.now(timezone.utc) - oldest <= MAX_AGE:
                return _cache
        try:
            result = _retrieve_weather()
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError):
            _cache = None
            raise HTTPException(status_code=503, detail='Live weather is unavailable or stale. No historical or estimated replacement is shown.')
        _cache, _cached_at = result, time.monotonic()
        return result
