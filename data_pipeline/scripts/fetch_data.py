"""Inventory local source files; this script does not fetch provider data."""
import hashlib
import json
from pathlib import Path

RAW_DATA_DIR = Path(__file__).resolve().parents[1] / 'data'


def fetch_data():
    """Return locally available raw data paths. Network ingestion is not implemented."""
    if not RAW_DATA_DIR.is_dir():
        raise FileNotFoundError(f'Local source directory not found: {RAW_DATA_DIR}')
    return sorted(p for p in RAW_DATA_DIR.iterdir() if p.is_file())


if __name__ == '__main__':
    print(json.dumps([{'file': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in fetch_data()], indent=2))
    print('Local inventory only; no live data was fetched.')
