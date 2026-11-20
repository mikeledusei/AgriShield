"""Shared test configuration.

The database is a temporary SQLite file per session, provisioned by Alembic, so a
test run never touches a developer's ``apps/backend/agrishield.db`` and never
depends on import order. Importers must set ``DATABASE_URL`` before importing the
application, which is why this happens at module import time.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
FRONTEND = ROOT / "apps" / "frontend"

_DB_DIR = Path(tempfile.mkdtemp(prefix="agrishield-tests-"))
DB_PATH = _DB_DIR / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["APP_ENV"] = "development"
os.environ["PUBLIC_MODE"] = "true"
os.environ.setdefault("AGRISHIELD_API_URL", "http://127.0.0.1:8000/api/v1")

for path in (str(BACKEND), str(FRONTEND)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(scope="session", autouse=True)
def provisioned_database():
    """Build the schema once with migrations, then seed the counties."""
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    from seed_counties import seed

    seed()
    yield
    from database.connection import engine

    if engine is not None:
        engine.dispose()


@pytest.fixture
def api():
    """TestClient bound to the real application (lifespan included)."""
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def example():
    """A real held-out feature row: test input, never a UI default."""
    import pandas as pd
    from schemas.manual_prediction import MODEL_INPUTS

    row = pd.read_csv(ROOT / "data_pipeline/data/processed/test_matrix.csv").iloc[0]
    return {
        "county_name": row["county"],
        "period": row["year_month"],
        **{key: float(row[key]) for key in MODEL_INPUTS},
    }
