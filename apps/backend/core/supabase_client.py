"""Lazy Supabase client initialization."""
from typing import Optional
from fastapi import HTTPException, status
from supabase import create_client, Client
from core.config import settings

_supabase_client: Optional[Client] = None


def is_supabase_configured() -> bool:
    """Return True when both SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set."""
    return bool(
        settings.SUPABASE_URL.strip()
        and settings.SUPABASE_SERVICE_ROLE_KEY.strip()
        and not settings.SUPABASE_URL.startswith("https://your-project")
    )


def get_supabase() -> Client:
    """Lazily initialize and return the Supabase client instance."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not is_supabase_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.",
        )
    try:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        return _supabase_client
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to initialize Supabase client: {exc}",
        )
