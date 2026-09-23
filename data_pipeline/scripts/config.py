"""Data pipeline configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
GEOSPATIAL_DIR = os.path.join(DATA_DIR, "geospatial")

API_KEYS = {
    "open_meteo": os.getenv("OPEN_METEO_API_KEY", ""),
    "nasa_power": os.getenv("NASA_API_KEY", ""),
    "faostat": os.getenv("FAOSTAT_API_KEY", ""),
    "knbs": os.getenv("KNBS_API_KEY", ""),
}

COUNTIES = [
    "Turkana", "Kajiado", "Uasin Gishu", "Nakuru", "Kilifi",
    "Meru", "Kisumu", "Kitui", "Machakos", "Makueni",
    "Bungoma", "Kakamega", "Siaya", "Trans Nzoia", "Nandi",
    "Kericho", "Muranga", "Nyeri", "Kirinyaga", "Siaya",
    "Kwale", "Taita Taveta", "Garissa", "Wajir", "Mandera",
]

DEFAULT_FEATURES = {
    "rainfall_anomaly_30d": 0.0,
    "ndvi_pasture_index": 0.5,
    "temp_max_avg": 28.0,
    "soil_moisture_deficit": 40.0,
}
