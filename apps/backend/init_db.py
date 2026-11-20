"""Provision the database schema. Run once: ``python init_db.py``.

Kept as a thin alias for ``alembic upgrade head`` so existing instructions keep
working; Alembic is the only thing that creates tables.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from database.connection import is_configured


def main() -> int:
    if not is_configured():
        print("DATABASE_URL is not set. Add it to apps/backend/.env first.")
        return 1
    backend_dir = Path(__file__).resolve().parent
    command.upgrade(Config(str(backend_dir / 'alembic.ini')), 'head')
    print("Database schema is up to date (alembic upgrade head).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
