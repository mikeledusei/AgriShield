"""In-process, per-caller rate limiting for the expensive AI endpoints.

Only ``/gria/chat`` and ``/gria/analyze`` are limited. They are the two routes that make
a paid outbound LLM call, and ``/gria/analyze`` also scores all 47 counties to build
national context. Left unbounded, a handful of concurrent callers occupy the bounded
threadpool that every other request shares.

Scope and honesty about limits:

* The counter is a fixed window in process memory. It is correct for the single-process
  deployment in ``render.yaml`` and it is a real defence against a burst or a runaway
  script. It is *not* a global quota: with N workers each gets its own budget. A shared
  limiter belongs in Redis (``REDIS_URL`` is already read) when the app scales out.
* ``AI_RATE_LIMIT_PER_MINUTE = 0`` disables it, which is the local and test default, so
  the existing suite and single-user development are unaffected.
"""
from threading import Lock
from time import monotonic

from core.config import settings

WINDOW_SECONDS = 60.0
#: Bound the table so an attacker rotating identities cannot grow it without limit.
MAX_TRACKED_CALLERS = 10_000

_lock = Lock()
#: caller -> (window_started_at, requests_in_window)
_windows: dict[str, tuple[float, int]] = {}


def reset() -> None:
    """Clear all counters (used by tests and by operators after a config change)."""
    with _lock:
        _windows.clear()


def check(caller: str) -> float | None:
    """Count one request for ``caller``.

    Returns ``None`` when the request is allowed, or the number of seconds to wait when
    the caller has exhausted its budget for the current window.
    """
    limit = settings.AI_RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return None

    now = monotonic()
    with _lock:
        started, count = _windows.get(caller, (now, 0))
        if now - started >= WINDOW_SECONDS:
            started, count = now, 0

        if count >= limit:
            return max(1.0, round(WINDOW_SECONDS - (now - started), 1))

        if len(_windows) >= MAX_TRACKED_CALLERS and caller not in _windows:
            # Drop the whole table rather than grow forever. Every caller gets one fresh
            # window, which is a bounded, self-healing outcome and never a bypass loop.
            _windows.clear()

        _windows[caller] = (started, count + 1)
        return None
