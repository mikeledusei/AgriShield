"""Per-request correlation id, access logging and unhandled-error reporting."""
import logging
import time
import uuid

from services.logging_service import request_id_var
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("agrishield.access")
HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind an id to every request and emit one structured access line.

    An inbound ``X-Request-ID`` is preserved so a proxy or client can correlate,
    but it is truncated: it is user input that ends up in log lines.
    """

    async def dispatch(self, request: Request, call_next):
        incoming = (request.headers.get(HEADER) or "").strip()[:64]
        request_id = incoming or uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "%s %s -> 500 (%.1f ms) unhandled error",
                request.method, request.url.path, duration_ms,
            )
            raise
        finally:
            request_id_var.reset(token)

        duration_ms = (time.perf_counter() - started) * 1000
        log = logger.warning if response.status_code >= 500 else logger.info
        log(
            "%s %s -> %s (%.1f ms) request_id=%s",
            request.method, request.url.path, response.status_code, duration_ms, request_id,
        )
        response.headers[HEADER] = request_id
        return response
