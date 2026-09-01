"""Export prediction results to CSV and Excel."""
import io
import pandas as pd


def to_csv(records: list) -> bytes:
    """Convert a list of prediction dicts to CSV bytes."""
    df = pd.DataFrame(records)
    return df.to_csv(index=False).encode("utf-8")


def to_excel(records: list) -> bytes:
    """Convert a list of prediction dicts to Excel bytes."""
    df = pd.DataFrame(records)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="AgriShield")
    buffer.seek(0)
    return buffer.getvalue()