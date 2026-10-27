"""Database connection to Neon (serverless PostgreSQL) or local SQLite fallback."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from fastapi import HTTPException, status
from core.config import settings

Base = declarative_base()
engine = None
SessionLocal = None

if settings.DATABASE_URL:
    database_url = settings.DATABASE_URL.strip()
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")

    if database_url.startswith("sqlite"):
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )
    else:
        if "sslmode" not in database_url and (
            database_url.startswith("postgres://") or database_url.startswith("postgresql://")
        ):
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            separator = "&" if "?" in database_url else "?"
            database_url = f"{database_url}{separator}sslmode=require"
        engine = create_engine(database_url, pool_pre_ping=True)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def is_configured() -> bool:
    return engine is not None


def get_db():
    if SessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured. Set DATABASE_URL in .env.",
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
