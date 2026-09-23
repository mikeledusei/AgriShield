"""AgriShield API tests."""
import pytest
import os
import sys
import httpx
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")


def test_imports():
    """Test that all modules can be imported."""
    import core.config
    import core.database
    import database.models
    import database.crud
    import schemas.pydantic_models
    import schemas.predictions
    import services.prediction_service
    import services.cache_service
    import services.export_service
    import services.pdf_generator
    import services.logging_service
    import routers.auth
    import routers.predictions
    import routers.reports
    import routers.uploads
    import routers.gria
    import routers.storage
    import routers.health
    import middleware.auth
    import agents.gria_agent
    import agents.file_processor
    import agents.tools
    assert True


def test_settings():
    """Test settings load correctly."""
    from core.config import settings
    assert settings.APP_NAME == "AgriShield API"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.DEBUG is not None
    assert settings.PUBLIC_MODE is True


def test_risk_levels():
    """Test risk threshold constants."""
    from core.config import settings
    assert settings.RISK_THRESHOLDS["CRITICAL"] == 75
    assert settings.RISK_THRESHOLDS["HIGH"] == 50
    assert settings.RISK_THRESHOLDS["MODERATE"] == 25
    assert settings.RISK_THRESHOLDS["SAFE"] == 0


def test_prediction_scoring():
    """Test rule-based scoring."""
    from services.prediction_service import compute_score, get_risk_level, _rule_components
    score = compute_score({"rainfall_anomaly_30d": 0.0, "ndvi_pasture_index": 0.5,
                            "temp_max_avg": 28.0, "soil_moisture_deficit": 40.0})
    assert isinstance(score, int)
    assert 0 <= score <= 100
    level = get_risk_level(score)
    assert level in ("SAFE", "MODERATE", "HIGH", "CRITICAL")


def test_schema_validation():
    """Test Pydantic schema validation."""
    from schemas.pydantic_models import ModelInput, GriaChatRequest, UploadResponse
    from schemas.predictions import CountyPredictionRequest, PredictionOut, BatchResponse

    inp = ModelInput(county_name="Turkana", rainfall_anomaly_30d=0.0,
                       ndvi_pasture_index=0.5, temp_max_avg=28.0, soil_moisture_deficit=40.0)
    assert inp.county_name == "Turkana"

    req = CountyPredictionRequest(county_name="Turkana")
    assert req.focus is None

    chat = GriaChatRequest(message="Test", county_name="Turkana")
    assert chat.message == "Test"

    resp = PredictionOut(county_name="Turkana", risk_score=50, risk_level="MODERATE",
                           main_driver="Test", recommendation="Test", model_used="rule_based")
    assert resp.county_name == "Turkana"

    batch = BatchResponse(generated_at="2026-01-01", county_count=1, counties=[resp])
    assert batch.county_count == 1


def test_health_endpoint():
    """Test health endpoint exists."""
    from fastapi import FastAPI
    from main import app
    from httpx import ASGITransport, AsyncClient
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    result = asyncio.run(client.get("/api/v1/health"))
    assert result.status_code == 200
    data = result.json()
    assert "status" in data
    assert "services" in data


def test_model_imports():
    """Test SQLAlchemy model imports."""
    from database.models import County, CountyFeature, Prediction, Report, ChatMessage, Upload
    assert County.__tablename__ == "counties"
    assert CountyFeature.__tablename__ == "county_features"
    assert Prediction.__tablename__ == "predictions"
    assert Report.__tablename__ == "reports"
    assert ChatMessage.__tablename__ == "chat_messages"
    assert Upload.__tablename__ == "uploads"
