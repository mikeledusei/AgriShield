"""Verify raw 2015-2025 datasets in data_pipeline/data/."""
from pathlib import Path
from typing import List

RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def fetch_data() -> List[Path]:
    """Return list of raw 2015-2025 dataset files present in data_pipeline/data/."""
    if not RAW_DATA_DIR.exists():
        return []
    return sorted(p for p in RAW_DATA_DIR.iterdir() if p.is_file())
