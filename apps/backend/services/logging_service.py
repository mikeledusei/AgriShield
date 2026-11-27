"""Central logging for the AgriShield backend — beautiful terminal edition.

``LOG_LEVEL`` is honoured, every line carries the request id when one is bound, and
uvicorn's own loggers are routed through the same handler so access logs and
application errors share one format. Nothing here changes *what* is logged — only
*how* it looks.

Colors are ANSI and auto-disabled when stdout is not a TTY (CI, file, pipe)
so logs stay clean in non-interactive sinks. ``LOG_FORMAT`` is kept plain for
the test ``\"%(request_id)s\" in LOG_FORMAT`` — the coloured format wraps it.
"""
import logging
import sys
from contextvars import ContextVar

from core.config import settings

#: Bound per request by ``RequestContextMiddleware``.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Plain — tests assert this contains %(request_id)s. Never remove it.
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | rid=%(request_id)s | %(name)s | %(message)s"

# ── ANSI palette (true-color, works in every modern terminal) ────────────────
RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"

# Level → (glyph, bg-tinted tag)
LEVEL_STYLE = {
    "DEBUG":    ("\033[38;2;120;160;200m", "⬢ DEBUG   "),
    "INFO":     ("\033[38;2; 56;168; 82m", "⬢ INFO    "),
    "WARNING":  ("\033[38;2;230;170;  0m", "⬢ WARN    "),
    "WARN":     ("\033[38;2;230;170;  0m", "⬢ WARN    "),
    "ERROR":    ("\033[38;2;220; 60; 60m", "⬢ ERROR   "),
    "CRITICAL": ("\033[38;2;255; 45; 85m", "⬢ CRIT    "),
}

COLORS = {
    "time": "\033[38;2;130;135;140m",
    "rid":  "\033[38;2;160;120;255m",
    "name": "\033[38;2; 80;180;160m",
    "msg_info":  "\033[38;2;225;230;235m",
    "msg_warn":  "\033[38;2;255;220;110m",
    "msg_error": "\033[38;2;255;120;120m",
    "msg_debug": "\033[38;2;170;190;210m",
    "pipe": "\033[38;2; 60; 70; 65m",
    "banner_title": "\033[38;2; 56;168; 82m",
    "banner_sub":   "\033[38;2;130;170;140m",
    "banner_line":  "\033[38;2; 45; 95; 65m",
}

BANNER = f"""{COLORS['banner_line']}────────────────────────────────────────────────────────────────{RESET}
{COLORS['banner_title']}{BOLD}   █████╗  ██████╗ ██████╗ ██╗  ███████╗██╗  ██╗██╗███████╗██╗     ██████╗{RESET}
{COLORS['banner_title']}{BOLD}  ██╔══██╗██╔════╝ ██╔══██╗██║  ██╔════╝██║  ██║██║██╔════╝██║     ██╔══██╗{RESET}
{COLORS['banner_title']}{BOLD}  ███████║██║  ███╗██████╔╝██║  ███████╗███████║██║█████╗  ██║     ██║  ██║{RESET}
{COLORS['banner_title']}{BOLD}  ██╔══██║██║   ██║██╔══██╗██║  ╚════██║██╔══██║██║██╔══╝  ██║     ██║  ██║{RESET}
{COLORS['banner_title']}{BOLD}  ██║  ██║╚██████╔╝██║  ██║██║  ███████║██║  ██║██║███████╗███████╗██████╔╝{RESET}
{COLORS['banner_line']}────────────────────────────────────────────────────────────────{RESET}
{COLORS['banner_sub']}  🌿  Neon PostgreSQL  ·  XGBoost Champion (val F1 0.8689)  ·  Real-time SHAP  ·  Open-Meteo live{RESET}
{COLORS['banner_line']}────────────────────────────────────────────────────────────────{RESET}"""


class RequestIdFilter(logging.Filter):
    """Attach the current request id (``-`` outside a request) to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


class AgriShieldFormatter(logging.Formatter):
    """Colour-aware formatter — same fields as LOG_FORMAT, just prettier.

    Respects NO_COLOR / non-TTY: falls back to the plain LOG_FORMAT so CI
    logs and file redirects stay clean.
    """

    def __init__(self, use_color: bool):
        # %(asctime)s is handled by our formatTime override for HH:MM:SS.mmm
        super().__init__(fmt="%(message)s", datefmt="%H:%M:%S")
        self.use_color = use_color and sys.stdout.isatty() and not _no_color()

    def formatTime(self, record, datefmt=None):  # noqa: N802
        # Keep full date in dim: 2026-11-27  + colored time
        ct = self.converter(record.created)
        date = f"{ct.tm_year:04d}-{ct.tm_mon:02d}-{ct.tm_mday:02d}"
        time = f"{ct.tm_hour:02d}:{ct.tm_min:02d}:{ct.tm_sec:02d}.{int(record.msecs):03d}"
        if self.use_color:
            return f"{DIM}{date}{RESET} {COLORS['time']}{time}{RESET}"
        return f"{date} {time}"

    def format(self, record: logging.LogRecord) -> str:
        if not self.use_color:
            # Plain fallback — identical semantics to the old formatter
            record.asctime = self.formatTime(record, self.datefmt)
            plain = LOG_FORMAT % {
                "asctime": record.asctime,
                "levelname": record.levelname,
                "request_id": getattr(record, "request_id", "-"),
                "name": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info and record.exc_info[0] is not None:
                plain += "\n" + self.formatException(record.exc_info)
            return plain

        # ── coloured path ──
        color, tag = LEVEL_STYLE.get(record.levelname, (COLORS["msg_info"], record.levelname.ljust(10)))
        rid = getattr(record, "request_id", "-")
        # Trim long request ids for alignment, keep 16-char short ones intact
        rid_display = rid if len(rid) <= 16 else rid[:16] + "…"

        asctime = self.formatTime(record, self.datefmt)
        level_tag = f"{color}{BOLD}{tag}{RESET}"
        pipe = f"{COLORS['pipe']}│{RESET}"
        name = f"{COLORS['name']}{record.name}{RESET}"
        rid_part = f"{COLORS['rid']}rid={rid_display}{RESET}" if rid != "-" else f"{DIM}rid=-{RESET}"

        # Message color by level
        if record.levelname in ("ERROR", "CRITICAL"):
            msg_color = COLORS["msg_error"]
        elif record.levelname == "WARNING":
            msg_color = COLORS["msg_warn"]
        elif record.levelname == "DEBUG":
            msg_color = COLORS["msg_debug"]
        else:
            msg_color = COLORS["msg_info"]

        msg = record.getMessage()
        # Highlight key tokens inside the message (method, status, ms) for access logs
        # e.g. "GET /api/v1/health -> 200 (3.2 ms) request_id=abc123"
        # We keep it lightweight — just dim the arrow and bold the status code
        if " -> " in msg and " ms)" in msg:
            msg = msg.replace(" -> ", f" {DIM}→{RESET} ").replace(" (", f" {DIM}({RESET}").replace(" ms)", f"{DIM} ms){RESET}")

        body = f"{asctime} {pipe} {level_tag} {pipe} {rid_part} {pipe} {name} {pipe} {msg_color}{msg}{RESET}"

        if record.exc_info and record.exc_info[0] is not None:
            body += f"\n{DIM}" + self.formatException(record.exc_info) + RESET
        return body


def _no_color() -> bool:
    import os

    return os.getenv("NO_COLOR") is not None or os.getenv("TERM") == "dumb"


def configure_logging() -> None:
    level = settings.log_level
    use_color = not _no_color()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(AgriShieldFormatter(use_color=use_color))
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

    # Banner — only when attached to a terminal, never in CI/files
    if use_color and sys.stdout.isatty():
        print(BANNER, file=sys.stdout, flush=True)


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
