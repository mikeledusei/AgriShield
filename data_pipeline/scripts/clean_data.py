"""Clean raw 2015-2025 datasets into data_pipeline/data/processed/."""
from pathlib import Path
import pandas as pd

PROCESSED_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def clean_data() -> pd.DataFrame:
    """Load the cleaned 2015-2025 master dataset."""
    master_path = PROCESSED_DATA_DIR / "master_cleaned_2015_2025.csv"
    if master_path.exists():
        return pd.read_csv(master_path)
    return pd.DataFrame()
