"""Auth is public — Neon only. All endpoints return the public identity."""

from core.auth import get_current_user


def test_public_identity():
    identity = get_current_user(None)
    assert identity["id"] == "public"
    assert identity["email"] == "public@agrishield.ke"


def test_auth_header_is_ignored():
    # Bearer token no longer required — still returns public identity
    identity = get_current_user("Bearer anything")
    assert identity["id"] == "public"
