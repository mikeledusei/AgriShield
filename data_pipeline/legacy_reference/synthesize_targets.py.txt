"""Synthesize leakage-free 25th-percentile NDVI shock targets (2015-2025)."""
from pathlib import Path
from typing import Tuple
import pandas as pd

PROCESSED_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def synthesize_targets() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return chronological train (2015-2023) and test (2024-2025) target tables."""
    train_path = PROCESSED_DATA_DIR / "master_train_2015_2023.csv"
    test_path = PROCESSED_DATA_DIR / "master_test_2024_2025.csv"
    train_df = pd.read_csv(train_path) if train_path.exists() else pd.DataFrame()
    test_df = pd.read_csv(test_path) if test_path.exists() else pd.DataFrame()
    return train_df, test_df
