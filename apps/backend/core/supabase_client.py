try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - optional dependency path
    Client = None
    create_client = None

from core.config import settings

supabase = None
if create_client is not None and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )


def get_supabase():
    """Get Supabase client instance."""
    if supabase is None:
        raise RuntimeError("Supabase is not configured for this environment.")
    return supabase