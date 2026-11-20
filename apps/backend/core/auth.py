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
    except Exception:
        # Token text is never logged: it is a credential.
        logging_service.warning("Bearer token verification failed.")
        raise _unauthorized("Invalid or expired token.") from None

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
