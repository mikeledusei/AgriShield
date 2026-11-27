"""Shared authentication dependency for protected endpoints.

``PUBLIC_MODE`` (the prototype default) returns an anonymous identity. Otherwise a
Supabase bearer token is required and verified. The distinction matters for
operators: 401 means "your credential is wrong", 503 means "this deployment cannot
verify anyone", and the second must not be reported as the first.
"""

from core.config import settings
from core.supabase_client import get_supabase
from fastapi import Header, HTTPException
from services import logging_service

#: Errors that genuinely mean "this credential is not valid".
#: Everything else (a TypeError from an SDK change, a bug in our own code) must surface as
#: a 500 with a traceback, not as a 401 that sends operators hunting for a token problem.
CREDENTIAL_ERRORS: tuple[type[BaseException], ...] = (
    ValueError,          # malformed/undecodable JWT
    KeyError,            # missing claim the SDK validates by key
    PermissionError,     # raised by some SDK versions for an expired token
)

PUBLIC_IDENTITY = {
    "id": "public",
    "email": "public@agrishield.ke",
    "full_name": "Public User",
    "role": "farmer",
}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Validate a Supabase bearer token (or return the anonymous identity)."""
    if settings.PUBLIC_MODE:
        return dict(PUBLIC_IDENTITY)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized("Missing bearer token.")

    try:
        client = get_supabase()
    except HTTPException:
        # Misconfiguration is an operator problem, not a rejected credential.
        logging_service.error("Cannot verify bearer tokens: Supabase is not configured.")
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured on this deployment.",
        ) from None

    try:
        response = client.auth.get_user(token)
    except CREDENTIAL_ERRORS:
        # Token text is never logged: it is a credential.
        logging_service.warning("Bearer token verification failed.")
        raise _unauthorized("Invalid or expired token.") from None
    except Exception:
        # A network failure or an SDK/library bug is an availability problem, not a bad
        # credential. Log it with the traceback and answer 503 so the client is not told
        # to re-authenticate against a broken deployment.
        logging_service.exception("Bearer token verification errored unexpectedly.")
        raise HTTPException(
            status_code=503,
            detail="Authentication could not be completed on this deployment.",
        ) from None

    user = getattr(response, "user", None)
    if user is None:
        raise _unauthorized("Invalid or expired token.")

    metadata = getattr(user, "user_metadata", None) or {}
    return {
        "id": user.id,
        "email": getattr(user, "email", None),
        "full_name": metadata.get("full_name"),
        "role": metadata.get("role", "farmer"),
    }
