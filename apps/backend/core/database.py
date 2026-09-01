"""
Synchronous Database Connection for AgriShield.
Matches the synchronous crud.py and prediction_service.py.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from core.config import settings

# 1. Clean the URL to ensure it uses the synchronous psycopg2 driver
# (If your .env accidentally has postgresql+asyncpg://, this fixes it)
db_url = settings.DATABASE_URL
if "+asyncpg" in db_url:
    db_url = db_url.replace("+asyncpg", "")

# 2. Create the synchronous engine
engine = create_engine(db_url, pool_pre_ping=True)

# 3. Create the synchronous session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Base class for models (if your models are defined in this file)
Base = declarative_base()

# 5. FastAPI Dependency
def get_db():
    """Yields a synchronous database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()