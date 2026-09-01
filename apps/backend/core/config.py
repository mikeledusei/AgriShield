from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

# Dynamically locate the .env file and project root
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent.parent
ENV_FILE = BACKEND_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # --- Application ---
    APP_NAME: str = "AgriShield API"
    APP_ENV: str = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    
    # --- Secrets ---
    SECRET_KEY: str
    API_KEY: str
    
    # --- NeonDB ---
    DATABASE_URL: str
    DB_ECHO: bool = False
    
    # --- Supabase ---
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_BUCKET_NAME: str = "agrishield-uploads"
    
    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300
    
    # --- CORS ---
    CORS_ORIGINS: str = "*"
    
    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    # --- NVIDIA NIM (Gria Agentic AI) ---
    NVIDIA_API_KEY: str = ""
    NVIDIA_MODEL: str = ""

    # --- ML Model Paths (Moved from old config.py) ---
    MODEL_PATH: Path = PROJECT_ROOT / "ml-models" / "models" / "agri-pred-v1.joblib"
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # --- ML Constants (Moved from old config.py) ---
    @property
    def RISK_THRESHOLDS(self) -> dict:
        return {"CRITICAL": 75, "HIGH": 50, "MODERATE": 25, "SAFE": 0}

    @property
    def RISK_COLORS(self) -> dict:
        return {"CRITICAL": "#d32f2f", "HIGH": "#f57c00", "MODERATE": "#fbc02d", "SAFE": "#2e7d32"}

    @property
    def FEATURE_COLUMNS(self) -> list:
        return ["rainfall_anomaly_30d", "ndvi_pasture_index", "temp_max_avg", "soil_moisture_deficit"]

    @property
    def DEFAULT_FEATURES(self) -> dict:
        return {"rainfall_anomaly_30d": 0.0, "ndvi_pasture_index": 0.5, "temp_max_avg": 28.0, "soil_moisture_deficit": 40.0}

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()