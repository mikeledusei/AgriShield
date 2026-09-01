"""Create all tables in Neon DB. Run once: python init_db.py"""
from database.connection import engine, Base, is_configured
from database import models  # noqa: F401


if __name__ == "__main__":
    if not is_configured():
        print("DATABASE_URL is not set. Add it to apps/backend/.env first.")
    else:
        Base.metadata.create_all(bind=engine)
        print("All tables created in Neon DB successfully!")