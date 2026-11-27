"""Database engine and session factory.

Production uses Neon PostgreSQL with bounded pooling and timeouts; tests and local
development fall back to SQLite. Schema is owned by Alembic — nothing here calls
``create_all``. Paste the Neon pooled DATABASE_URL from the Neon Console; the
engine normalises postgres:// and injects sslmode=require for Neon automatically.
"""
from collections.abc import Iterator

from core.config import settings
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


def _normalise_url(raw: str) -> str:
    """Accept the URL spellings hosted providers (Neon) hand out."""
    url = raw.strip()
    # A synchronous engine cannot use the async driver.
    url = url.replace("+asyncpg", "").replace("+psycopg_async", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # SQLAlchemy 2.x defaults to psycopg (v3) for postgresql://, but we ship
    # psycopg2-binary. Force psycopg2 so `postgresql://` from Neon works.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    # Neon requires TLS. The dashboard URL already contains sslmode=require and
    # channel_binding=require; inject only if the caller pasted a bare host URL.
    if "sslmode" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    return url


def _build_engine() -> Engine | None:
    raw = settings.resolved_database_url
    if not raw:
        return None
    url = _normalise_url(raw)

    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_POOL_SIZE,
        pool_recycle=settings.DB_POOL_RECYCLE,
        # Bound connection acquisition so a cold Neon compute fails fast instead of
        # hanging the request thread indefinitely.
        pool_timeout=settings.DB_CONNECT_TIMEOUT,
        connect_args={"connect_timeout": settings.DB_CONNECT_TIMEOUT},
        echo=settings.DB_ECHO,
    )


engine: Engine | None = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


def is_configured() -> bool:
    return engine is not None


def get_db() -> Iterator[Session]:
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
