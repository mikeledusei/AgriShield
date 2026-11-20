"""Protected-mode authentication.

These branches gate every endpoint when ``PUBLIC_MODE=False`` and previously had no
coverage at all. The Supabase client is stubbed so the tests exercise our logic, not
the network.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


class FakeUser:
    def __init__(self, user_id="user-1", email="staff@agrishield.ke", metadata=None):
        self.id = user_id
        self.email = email
        self.user_metadata = metadata or {"full_name": "Field Officer", "role": "officer"}


class FakeAuth:
    def __init__(self, user=None, error=None):
        self._user = user
        self._error = error

    def get_user(self, token):
        if self._error is not None:
            raise self._error
        return SimpleNamespace(user=self._user)


class FakeSupabase:
    def __init__(self, **kwargs):
        self.auth = FakeAuth(**kwargs)


@pytest.fixture
def protected(monkeypatch):
    """Switch the running app into protected mode."""
    from core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_MODE", False)
    return monkeypatch


def _client():
    from main import app

    return TestClient(app)


def test_missing_token_is_rejected(protected):
    protected.setattr("core.auth.get_supabase", lambda: FakeSupabase(user=FakeUser()))
    with _client() as client:
        response = client.get("/api/v1/predictions/counties")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_malformed_authorization_header_is_rejected(protected):
    protected.setattr("core.auth.get_supabase", lambda: FakeSupabase(user=FakeUser()))
    with _client() as client:
        for header in ("Token abc", "Bearer", "Bearer    "):
            response = client.get("/api/v1/predictions/counties", headers={"Authorization": header})
            assert response.status_code == 401, header


def test_token_verification_failure_is_rejected(protected):
    protected.setattr(
        "core.auth.get_supabase",
        lambda: FakeSupabase(error=RuntimeError("expired token")),
    )
    with _client() as client:
        response = client.get(
            "/api/v1/predictions/counties", headers={"Authorization": "Bearer stale"}
        )
    assert response.status_code == 401


def test_unknown_user_object_is_rejected(protected):
    protected.setattr("core.auth.get_supabase", lambda: FakeSupabase(user=None))
    with _client() as client:
        response = client.get(
            "/api/v1/predictions/counties", headers={"Authorization": "Bearer abc"}
        )
    assert response.status_code == 401


def test_valid_token_is_accepted_and_identity_surfaces(protected):
    user = FakeUser()
    protected.setattr("core.auth.get_supabase", lambda: FakeSupabase(user=user))
    with _client() as client:
        assert client.get(
            "/api/v1/predictions/counties", headers={"Authorization": "Bearer good"}
        ).status_code == 200

    from core.auth import get_current_user

    identity = get_current_user("Bearer good")
    assert identity == {
        "id": "user-1",
        "email": "staff@agrishield.ke",
        "full_name": "Field Officer",
        "role": "officer",
    }


def test_public_mode_is_anonymous_but_labelled():
    """The default mode must be obvious in the dependency's return value."""
    from core.auth import get_current_user

    identity = get_current_user(None)
    assert identity["id"] == "public"


def test_configuration_error_is_not_a_credential_error():
    """A missing Supabase configuration should not masquerade as a bad token."""
    from core.auth import get_current_user
    from core.config import settings

    original = settings.PUBLIC_MODE
    settings.PUBLIC_MODE = False

    def unavailable():
        raise HTTPException(status_code=503, detail="Supabase is not configured.")

    import core.auth

    original_getter = core.auth.get_supabase
    core.auth.get_supabase = unavailable
    try:
        with pytest.raises(HTTPException) as excinfo:
            get_current_user("Bearer token")
        assert excinfo.value.status_code == 503
    finally:
        core.auth.get_supabase = original_getter
        settings.PUBLIC_MODE = original
