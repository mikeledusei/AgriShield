"""Auth is public — Neon is the only backend dependency."""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
def auth_status() -> dict[str, str]:
    return {"status": "public", "database": "neon"}
