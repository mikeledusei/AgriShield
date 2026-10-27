"""Configuration for the 2015-2025 AgriShield data pipeline."""
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PIPELINE_DIR / "data"
PROCESSED_DATA_DIR = PIPELINE_DIR / "data" / "processed"

START_YEAR = 2015
END_YEAR = 2025

KENYA_COUNTIES_47 = sorted([
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo Marakwet", "Embu", "Garissa",
    "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho", "Kiambu", "Kilifi",
    "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale", "Laikipia", "Lamu", "Machakos",
    "Makueni", "Mandera", "Marsabit", "Meru", "Migori", "Mombasa", "Murang'a",
    "Nairobi", "Nakuru", "Nandi", "Narok", "Nyamira", "Nyandarua", "Nyeri",
    "Samburu", "Siaya", "Taita Taveta", "Tana River", "Tharaka Nithi", "Trans Nzoia",
    "Turkana", "Uasin Gishu", "Vihiga", "Wajir", "West Pokot",
])
