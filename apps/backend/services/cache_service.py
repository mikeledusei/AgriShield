"""Simple in-memory TTL cache."""
import time
import threading
from typing import Any, Optional
from core.config import settings

_cache = {}
_lock = threading.Lock()

def get(key: str) -> Optional[Any]:
    with _lock:
        entry = _cache.get(key)
        if entry and entry["expires_at"] > time.time():
            return entry["value"]
        if entry: del _cache[key]
        return None

def set(key: str, value: Any, ttl: int = None) -> None:
    ttl = ttl if ttl is not None else settings.CACHE_TTL
    with _lock:
        _cache[key] = {"value": value, "expires_at": time.time() + ttl}

def clear() -> None:
    with _lock:
        _cache.clear()