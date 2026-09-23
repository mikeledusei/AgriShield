"""Clean data: standardize and validate raw datasets."""
import os
import pandas as pd
from config import DATA_DIR, PROCESSED_DIR


def clean_data(filepath: str, output_name: str) -> pd.DataFrame:
    """Clean a raw dataset: remove duplicates, handle missing values, standardize types."""
    df = pd.read_csv(filepath)
    df = df.drop_duplicates()
    df = df.dropna(how="all")
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df


def clean_all():
    """Process all raw data files."""
    raw_dir = os.path.join(DATA_DIR, "raw") if os.path.exists(os.path.join(DATA_DIR, "raw")) else "."
    for fname in os.listdir(raw_dir):
        if fname.endswith((".csv", ".xlsx")):
            filepath = os.path.join(raw_dir, fname)
            df = clean_data(filepath, fname)
            out_path = os.path.join(PROCESSED_DIR, f"cleaned_{fname}")
            df.to_csv(out_path, index=False)
            print(f"Cleaned: {fname} -> {out_path}")
