"""Shared authentication dependency for protected endpoints."""
from typing import Optional

from fastapi import Header, HTTPException

from core.config import settings
from core.supabase_client import get_supabase


def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Validate a Supabase Bearer token from the Authorization header."""
    if settings.PUBLIC_MODE:
        return {"id": "public", "email": "public@agrishield.ke", "full_name": "Public User", "role": "farmer"}
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.",
                            headers={"WWW-Authenticate": "Bearer"})
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token.",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        resp = get_supabase().auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.",
                            headers={"WWW-Authenticate": "Bearer"})
    if resp.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return {"id": resp.user.id, "email": resp.user.email,
            "full_name": (resp.user.user_metadata or {}).get("full_name"),
            "role": (resp.user.user_metadata or {}).get("role", "farmer")}