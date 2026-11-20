"""Backwards-compatible import shim.

The engine lives in ``database.connection`` so migrations, models and routers share
one definition. This module keeps the older import path working.
"""
from database.connection import (  # noqa: F401
    Base,
    SessionLocal,
    engine,
    get_db,
    is_configured,
)

__all__ = ["Base", "SessionLocal", "engine", "get_db", "is_configured"]
