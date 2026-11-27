"""Readiness checks that prove the app can actually serve a request.

Configuration alone is not evidence: the model is exercised with one row, the
artifact digest is compared with the recorded hash, and the database (Neon
PostgreSQL) is asked for the tables the app writes to.
"""
from dataclasses import dataclass, field

import pandas as pd
from core.config import settings
from database.connection import engine
from schemas.manual_prediction import MODEL_INPUTS, TRAINING_RANGES
from services.prediction_service import get_engine
from sqlalchemy import inspect, text

REQUIRED_TABLES = ("counties", "assessment_report_snapshots", "assessment_history")


@dataclass
class HealthReport:
    services: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.problems


def _midpoint_ranges() -> dict[str, float]:
    """A representative in-range feature row, derived from the training ranges."""
    return {
        key: round((TRAINING_RANGES[key][0] + TRAINING_RANGES[key][1]) / 2, 6)
        for key in MODEL_INPUTS
    }


def check_model(services: dict[str, str], problems: list[str]) -> None:
    engine_ = get_engine()
    if engine_.model is None or not engine_.feature_cols:
        services["ml_engine"] = "unavailable"
        problems.append("the trained model is not loaded")
        return

    expected = engine_._expected_model_sha256()
    if settings.REQUIRE_MODEL_HASH and expected and engine_.model_sha256 != expected:
        services["ml_engine"] = "artifact hash mismatch"
        problems.append("the loaded model does not match the recorded artifact hash")
        return

    missing = sorted(set(engine_.feature_cols) - set(TRAINING_RANGES) - {"month_sin", "month_cos"})
    if missing:
        services["ml_engine"] = f"missing training ranges: {', '.join(missing)}"
        problems.append("training ranges are missing for part of the feature contract")
        return
    try:
        vector = _midpoint_ranges()
        vector["month_sin"], vector["month_cos"] = 0.0, 1.0
        frame = pd.DataFrame([[vector[c] for c in engine_.feature_cols]], columns=engine_.feature_cols)
        probability = float(engine_.model.predict_proba(frame)[0][1])
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability outside [0, 1]")
    except Exception:
        services["ml_engine"] = "smoke inference failed"
        problems.append("the model could not score a probe row")
        return

    services["ml_engine"] = engine_.model_name
    services["historical_data"] = (
        "available" if engine_.county_history and engine_.available_months else "unavailable"
    )
    if not engine_.county_history:
        problems.append("no packaged historical feature rows are loaded")
    services["model_artifact_sha256"] = (engine_.model_sha256 or "unknown")[:12]


def check_database(services: dict[str, str], problems: list[str]) -> None:
    if engine is None:
        services["database"] = "not configured (Neon DATABASE_URL missing)"
        problems.append("DATABASE_URL is not configured — set Neon pooled URL")
        return
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            existing = set(inspect(connection).get_table_names())
    except Exception:
        services["database"] = "unreachable"
        problems.append("Neon database is unreachable — check DATABASE_URL and network")
        return
    missing = [table for table in REQUIRED_TABLES if table not in existing]
    if missing:
        services["database"] = "missing tables: " + ", ".join(missing)
        problems.append("database migrations have not been applied (run alembic upgrade head)")
        return
    services["database"] = "connected (Neon)"


def check_configuration(services: dict[str, str], problems: list[str]) -> None:
    services["database_provider"] = "Neon PostgreSQL"
    services["redis"] = "configured (not checked)" if settings.REDIS_URL else "not configured"
    services["auth_mode"] = "public (anonymous) — no Supabase"


def build_health_report() -> HealthReport:
    report = HealthReport()
    check_model(report.services, report.problems)
    check_database(report.services, report.problems)
    check_configuration(report.services, report.problems)

    from agents.gria_agent import active_model, agent_executor

    report.services["gria_ai"] = f"configured ({active_model})" if agent_executor is not None else "summary mode"
    return report
