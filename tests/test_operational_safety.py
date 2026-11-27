"""Behaviour added to close operational gaps: log correlation, AI quotas."""

import logging

import pytest


def test_log_format_renders_the_request_id():
    from services import logging_service

    assert "%(request_id)s" in logging_service.LOG_FORMAT


def test_every_record_gets_a_request_id_supplied():
    from services import logging_service

    record = logging.LogRecord(
        name="agrishield", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    assert logging_service.RequestIdFilter().filter(record) is True
    assert record.request_id == "-"

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
    assert rate_limit.check("gria:b") is None


def test_limiter_is_disabled_by_default(monkeypatch):
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
    with pytest.raises(Exception) as excinfo:
        enforce_ai_quota(request_for(), user)
    assert excinfo.value.status_code == 429
    assert "Retry-After" in excinfo.value.headers
    rate_limit.reset()
