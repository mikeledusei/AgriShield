"""Synchronous Database Connection for AgriShield. Re-exports from database.connection."""
from database.connection import engine, SessionLocal, Base, get_db, is_configured
