from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "AgriShield API"
    APP_ENV: str = "development"
    DEBUG: str = "False"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    API_KEY: str = "dev-api-key-change-in-production"
    PUBLIC_MODE: bool = True

    DATABASE_URL: str = "sqlite:///./agrishield.db"
    DB_ECHO: bool = False

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_BUCKET_NAME: str = "agrishield-uploads"

    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300

    CORS_ORIGINS: str = ""
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB

    LOG_LEVEL: str = "INFO"

    NVIDIA_API_KEY: str = ""
    NVIDIA_MODEL: str = "meta/llama-3.3-70b-instruct"

    MODEL_PATH: Path = BACKEND_DIR / "ml_artifacts" / "lightgbm_agrishield_v1.joblib"

    @property
    def cors_origins_list(self) -> list[str]:
        origins = self.CORS_ORIGINS.strip()
        if origins == "*":
            return ["*"]
        if not origins:
            return [
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:8501",
                "http://127.0.0.1:8501",
            ]
        return [origin.strip() for origin in origins.split(",") if origin.strip()]

    @property
    def RISK_THRESHOLDS(self) -> dict:
        return {"CRITICAL": 75, "HIGH": 50, "MODERATE": 25, "SAFE": 0}

    @property
    def RISK_COLORS(self) -> dict:
        return {
            "CRITICAL": "#d32f2f",
            "HIGH": "#f57c00",
            "MODERATE": "#fbc02d",
            "SAFE": "#2e7d32",
        }

    @property
    def FEATURE_COLUMNS(self) -> list:
        return [
            "rainfall_anomaly_30d",
            "ndvi_pasture_index",
            "temp_max_avg",
            "soil_moisture_deficit",
        ]

    @property
    def DEFAULT_FEATURES(self) -> dict:
        return {
            "rainfall_anomaly_30d": 0.0,
            "ndvi_pasture_index": 0.5,
            "temp_max_avg": 28.0,
            "soil_moisture_deficit": 40.0,
        }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
