"""Compatibility router retained for older imports and tests.
Authentication was intentionally removed from the product flow.
"""

from core.config import settings
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
def auth_status() -> dict[str, str]:
    return {"status": "public-mode" if settings.PUBLIC_MODE else "bearer-token-required"}
