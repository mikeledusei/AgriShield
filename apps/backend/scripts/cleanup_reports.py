"""Delete expired report snapshots. Run regularly with a scheduler."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database.connection import SessionLocal
from routers.snapshot_reports import cleanup_expired
from routers.history import purge_history

if __name__ == '__main__':
    if SessionLocal is None:
        raise SystemExit('Database is not configured.')
    db = SessionLocal()
    try:
        count = cleanup_expired(db)
        history_count = purge_history(db)
        db.commit()
        print(f'Deleted {count} expired report snapshots and {history_count} expired history records.')
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
