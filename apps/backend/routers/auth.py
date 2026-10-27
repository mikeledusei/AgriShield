"""Compatibility router retained for older imports and tests.
Authentication was intentionally removed from the product flow.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
def auth_status() -> dict[str, str]:
    return {"status": "authentication-disabled"}
