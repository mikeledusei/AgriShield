"""Application settings.

Defaults are development-safe and fail closed: ``APP_ENV=production`` refuses to
start unless identity, database and transport security are configured.
"""
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent.parent
ENV_FILE = BACKEND_DIR / ".env"

PLACEHOLDER_PREFIXES = ("your-", "changeme", "change-in-production", "dev-")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "AgriShield API"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    # Containers must listen on all interfaces; the platform terminates TLS.
    HOST: str = "0.0.0.0"  # noqa: S104
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    API_KEY: str = "dev-api-key-change-in-production"

    # Anonymous access is convenient locally and unacceptable in production.
    # ``validate_production_safety`` enforces that.
    PUBLIC_MODE: bool = True

    # Empty means "use the local SQLite file". Production must set this explicitly
    # so records are not silently written to an ephemeral container filesystem.
    DATABASE_URL: str = ""
    DB_ECHO: bool = False
    DB_CONNECT_TIMEOUT: int = 10
    DB_POOL_SIZE: int = 5
    DB_POOL_RECYCLE: int = 280

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
    # Loaded artifacts must match the hash recorded with the training ranges.
    REQUIRE_MODEL_HASH: bool = True

    # --- derived / validated values -------------------------------------------------

    @property
    def local_database_url(self) -> str:
        """SQLite fallback used only outside production."""
        return f"sqlite:///{BACKEND_DIR / 'agrishield.db'}"

    @property
    def resolved_database_url(self) -> str:
        return self.DATABASE_URL.strip() or self.local_database_url

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        origins = self.CORS_ORIGINS.strip()
        if origins == "*":
            return ["*"]
        if not origins:
            return [
                "http://localhost:8501",
                "http://127.0.0.1:8501",
            ]
        return [origin.strip() for origin in origins.split(",") if origin.strip()]

    @property
    def log_level(self) -> int:
        return logging.getLevelName(self.LOG_LEVEL.strip().upper()) if self.LOG_LEVEL.strip() else logging.INFO

    @property
    def supabase_configured(self) -> bool:
        return bool(
            self.SUPABASE_URL.strip()
            and self.SUPABASE_SERVICE_ROLE_KEY.strip()
            and not self.SUPABASE_URL.startswith("https://your-project")
        )

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        """Refuse to start in production with prototype defaults.

        Every message names the environment variable to set, because the failure
        happens at deploy time where the logs are the only diagnostic.
        """
        if self.APP_ENV != "production":
            return self

        problems: list[str] = []
        if self.PUBLIC_MODE:
            problems.append(
                "PUBLIC_MODE=True exposes every endpoint anonymously; set PUBLIC_MODE=False."
            )
        elif not self.supabase_configured:
            problems.append(
                "PUBLIC_MODE=False requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
                "so bearer tokens can be verified."
            )
        if not self.DATABASE_URL.strip():
            problems.append(
                "DATABASE_URL is required in production; the local SQLite file is not durable."
            )
        for name in ("SECRET_KEY", "API_KEY"):
            value = getattr(self, name)
            if not value.strip() or value.startswith(PLACEHOLDER_PREFIXES):
                problems.append(f"{name} still holds its placeholder value; set a random secret.")
        if self.CORS_ORIGINS.strip() == "*":
            problems.append(
                "CORS_ORIGINS='*' with credentials is not safe; list the dashboard origins explicitly."
            )
        if not self.CORS_ORIGINS.strip():
            problems.append(
                "CORS_ORIGINS is empty, so only localhost origins are allowed; set the deployed dashboard origin."
            )
        if problems:
            raise ValueError(
                "Unsafe production configuration:\n  - " + "\n  - ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
