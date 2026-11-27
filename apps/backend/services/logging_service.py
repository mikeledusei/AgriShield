"""Central logging for the AgriShield backend.

``LOG_LEVEL`` is honoured, every line carries the request id when one is bound, and
uvicorn's own loggers are routed through the same handler so access logs and
application errors share one format.
"""
import logging
import sys
from contextvars import ContextVar

from core.config import settings

#: Bound per request by ``RequestContextMiddleware``.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# ``request_id`` is supplied by ``RequestIdFilter`` below, which runs on every record
# passing through the handler. Without it in the format the value was computed and then
# thrown away, so a user-reported error could not be traced back to its request.
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | rid=%(request_id)s | %(name)s | %(message)s"


class RequestIdFilter(logging.Filter):
    """Attach the current request id (``-`` outside a request) to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def configure_logging() -> None:
    level = settings.log_level
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn installs its own handlers at import time; reuse ours.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(level)

    logging.getLogger("agrishield").setLevel(level)


configure_logging()
logger = logging.getLogger("agrishield")


def info(message: str, *args: object) -> None:
    logger.info(message, *args)


def warning(message: str, *args: object) -> None:
    logger.warning(message, *args)


def error(message: str, *args: object) -> None:
    logger.error(message, *args)


def exception(message: str, *args: object) -> None:
    logger.exception(message, *args)
