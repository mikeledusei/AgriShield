"""Behaviour added to close operational gaps: log correlation, AI quotas, auth error
classification.

Each test here corresponds to a defect that was invisible to the rest of the suite:
a request id that was computed and discarded, an endpoint with no bound on paid calls,
and an SDK failure that was reported as a bad credential.
"""
import logging

import pytest
from fastapi import HTTPException


# --------------------------------------------------------------- log correlation

def test_log_format_renders_the_request_id():
    """The filter binds ``request_id``; if the format omits it, the value is discarded.

    A user-reported error carries only the ``X-Request-ID`` header, so a log line without
    it cannot be traced back to that request.
    """
    from services import logging_service

    assert "%(request_id)s" in logging_service.LOG_FORMAT


def test_every_record_gets_a_request_id_supplied():
    """The format references the field, so the filter must always populate it."""
    from services import logging_service

    record = logging.LogRecord(
        name="agrishield", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    assert logging_service.RequestIdFilter().filter(record) is True
    assert record.request_id == "-"  # no request bound

    token = logging_service.request_id_var.set("abc123")
    try:
        record = logging.LogRecord(
            name="agrishield", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hello", args=(), exc_info=None,
        )
        logging_service.RequestIdFilter().filter(record)
        assert record.request_id == "abc123"
    finally:
        logging_service.request_id_var.reset(token)


# ------------------------------------------------------------------- AI quotas

@pytest.fixture
def quota(monkeypatch):
    from core import rate_limit
    from core.config import settings

    rate_limit.reset()
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_PER_MINUTE", 2)
    yield settings
    rate_limit.reset()


def test_limiter_allows_up_to_the_budget_then_asks_the_caller_to_wait(quota):
    from core import rate_limit

    assert rate_limit.check("gria:user-1") is None
    assert rate_limit.check("gria:user-1") is None
    retry_after = rate_limit.check("gria:user-1")
    assert retry_after is not None and retry_after > 0


def test_limiters_are_per_caller(quota):
    from core import rate_limit

    rate_limit.check("gria:a")
    rate_limit.check("gria:a")
    assert rate_limit.check("gria:a") is not None
    # A different identity has its own budget.
    assert rate_limit.check("gria:b") is None


def test_limiter_is_disabled_by_default(monkeypatch):
    """Local development and the rest of the suite must be unaffected."""
    from core import rate_limit
    from core.config import settings

    monkeypatch.setattr(settings, "AI_RATE_LIMIT_PER_MINUTE", 0)
    for _ in range(50):
        assert rate_limit.check("gria:anyone") is None


def test_quota_dependency_raises_429_with_retry_after(quota):
    from core import rate_limit
    from routers.gria import enforce_ai_quota
    from starlette.datastructures import Headers
    from starlette.requests import Request

    def request_for(host="10.0.0.1"):
        scope = {"type": "http", "headers": Headers({}).raw, "client": (host, 1234)}
        return Request(scope)

    user = {"id": "user-1"}
    enforce_ai_quota(request_for(), user)
    enforce_ai_quota(request_for(), user)
    with pytest.raises(HTTPException) as excinfo:
        enforce_ai_quota(request_for(), user)
    assert excinfo.value.status_code == 429
    assert "Retry-After" in excinfo.value.headers
    rate_limit.reset()


# ------------------------------------------------------- auth error classification

class _ExplodingAuth:
    def __init__(self, error):
        self._error = error

    def get_user(self, token):
        raise self._error


class _FakeSupabase:
    def __init__(self, error):
        self.auth = _ExplodingAuth(error)


def _protected(monkeypatch, error):
    from core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_MODE", False)
    monkeypatch.setattr("core.auth.get_supabase", lambda: _FakeSupabase(error))


def test_invalid_credential_is_a_401(monkeypatch):
    """A malformed/undecodable token is genuinely the caller's fault."""
    from core.auth import get_current_user

    _protected(monkeypatch, ValueError("invalid JWT"))
    with pytest.raises(HTTPException) as excinfo:
        get_current_user("Bearer bad")
    assert excinfo.value.status_code == 401
    assert excinfo.value.headers["WWW-Authenticate"] == "Bearer"


def test_unexpected_verification_error_is_not_reported_as_a_bad_credential(monkeypatch):
    """An SDK/library bug (TypeError from a changed signature) must not tell the client
    to re-authenticate. It is an availability problem and must surface as 503."""
    from core.auth import get_current_user

    _protected(monkeypatch, TypeError("get_user() got an unexpected keyword argument"))
    with pytest.raises(HTTPException) as excinfo:
        get_current_user("Bearer good")
    assert excinfo.value.status_code == 503


def test_network_failure_is_a_503_not_a_401(monkeypatch):
    from core.auth import get_current_user

    _protected(monkeypatch, ConnectionError("upstream unreachable"))
    with pytest.raises(HTTPException) as excinfo:
        get_current_user("Bearer good")
    assert excinfo.value.status_code == 503
