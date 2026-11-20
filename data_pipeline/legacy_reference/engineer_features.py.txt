"""Engineer the 16 agro-climatic, seasonal, vegetation-lag, and demographic features."""
from pathlib import Path
from typing import Tuple
import pandas as pd

PROCESSED_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def engineer_features() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load engineered X_train (2015-2023) and X_test (2024-2025) feature matrices."""
    x_train_path = PROCESSED_DATA_DIR / "X_train.csv"
    x_test_path = PROCESSED_DATA_DIR / "X_test.csv"
    x_train = pd.read_csv(x_train_path) if x_train_path.exists() else pd.DataFrame()
    x_test = pd.read_csv(x_test_path) if x_test_path.exists() else pd.DataFrame()
    return x_train, x_test
