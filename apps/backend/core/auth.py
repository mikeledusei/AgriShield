"""Public authentication — no external auth provider.

All endpoints are public. This module is kept so routers keep a single
dependency signature, but it never contacts Neon or Supabase.
"""

from fastapi import Header

PUBLIC_IDENTITY = {
    "id": "public",
    "email": "public@agrishield.ke",
    "full_name": "Public User",
    "role": "farmer",
}


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Return the anonymous public identity for every request."""
    return dict(PUBLIC_IDENTITY)
