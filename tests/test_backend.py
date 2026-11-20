"""AgriShield API & ML integration tests."""
import asyncio
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")


def test_imports():
    """Test that all modules can be imported without side-effect crashes."""
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
    """Test settings load correctly with safe defaults."""
    from core.config import settings
    assert settings.APP_NAME == "AgriShield API"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.DEBUG is not None
    assert settings.PUBLIC_MODE is True
    assert settings.MODEL_PATH.name == "lightgbm_agrishield_v1.joblib"


def test_risk_levels():
    """Test risk threshold constants."""
    from core.config import settings
    assert settings.RISK_THRESHOLDS["CRITICAL"] == 75
    assert settings.RISK_THRESHOLDS["HIGH"] == 50
    assert settings.RISK_THRESHOLDS["MODERATE"] == 25
    assert settings.RISK_THRESHOLDS["SAFE"] == 0


def test_prediction_scoring():
    """Test rule-based fallback scoring."""
    from services.prediction_service import compute_score, get_risk_level, _rule_components
    score = compute_score({
        "rainfall_anomaly_30d": 0.0,
        "ndvi_pasture_index": 0.5,
        "temp_max_avg": 28.0,
        "soil_moisture_deficit": 40.0,
    })
    assert isinstance(score, int)
    assert 0 <= score <= 100
    level = get_risk_level(score)
    assert level in ("SAFE", "MODERATE", "HIGH", "CRITICAL")


def test_ml_artifacts_and_lightgbm_champion():
    """Verify LightGBM champion model and 16-feature contract are loaded and used."""
    from services.prediction_service import get_engine
    engine = get_engine()
    assert engine.model is not None
    assert engine.model_name == "lightgbm_v1"
    assert len(engine.feature_cols) == 16
    assert "forage_dryness_index" in engine.feature_cols
    assert "rainfall_anomaly" in engine.feature_cols
    assert len(engine.ndvi_stats) == 47

    res = engine.predict(None, "Turkana", focus="livestock", persist=False)
    assert res["county_name"] == "Turkana"
    assert res["model_used"] == "lightgbm_v1"
    assert 0 <= res["risk_score"] <= 100
    assert res["risk_level"] in ("SAFE", "MODERATE", "HIGH", "CRITICAL")


def test_county_alias_normalization():
    """Verify hyphenated and apostrophe county variants resolve to canonical names."""
    from seed_counties import normalize_county_name, COUNTIES
    assert len(COUNTIES) == 47
    assert normalize_county_name("Taita-Taveta") == "Taita Taveta"
    assert normalize_county_name("Elgeyo-Marakwet") == "Elgeyo Marakwet"
    assert normalize_county_name("KEIYO-MARAKWET") == "Elgeyo Marakwet"
    assert normalize_county_name("Tharaka-Nithi") == "Tharaka Nithi"
    assert normalize_county_name("Muranga") == "Murang'a"
    assert normalize_county_name("Homabay") == "Homa Bay"


def test_schema_validation():
    """Test Pydantic schema validation including document context in GriaChatRequest."""
    from schemas.pydantic_models import ModelInput, GriaChatRequest, UploadResponse
    from schemas.predictions import CountyPredictionRequest, PredictionOut, BatchResponse

    inp = ModelInput(
        county_name="Turkana",
        rainfall_anomaly_30d=0.0,
        ndvi_pasture_index=0.5,
        temp_max_avg=28.0,
        soil_moisture_deficit=40.0,
    )
    assert inp.county_name == "Turkana"

    req = CountyPredictionRequest(county_name="Turkana")
    assert req.focus is None

    chat = GriaChatRequest(
        message="Test",
        county_name="Turkana",
        document_context="Sample text",
        document_name="report.pdf",
    )
    assert chat.message == "Test"
    assert chat.document_name == "report.pdf"

    resp = PredictionOut(
        county_name="Turkana",
        risk_score=50,
        risk_level="MODERATE",
        main_driver="Test",
        recommendation="Test",
        model_used="lightgbm_v1",
    )
    assert resp.county_name == "Turkana"

    batch = BatchResponse(generated_at="2026-01-01", county_count=1, counties=[resp])
    assert batch.county_count == 1


def test_health_endpoint():
    """Test health endpoint reports ML model status and services."""
    from main import app
    from httpx import ASGITransport, AsyncClient

    async def _run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get("/api/v1/health")

    result = asyncio.run(_run())
    assert result.status_code == 200
    data = result.json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True
    assert data["model_name"] == "lightgbm_v1"
    assert "services" in data


def test_retired_unsafe_endpoints_and_gria():
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as client:
        assert len(client.get('/api/v1/predictions/counties').json()) == 47
        for path in ['/predictions/crop-yield', '/predictions/forecast', '/predictions/scenario', '/upload/analyze', '/reports/create', '/storage/upload']:
            assert client.post('/api/v1' + path, json={}).status_code == 410
        for path in ['/predictions/batch', '/predictions/explain', '/predictions/months', '/reports/1/pdf']:
            assert client.get('/api/v1' + path).status_code == 410
        chat = client.post('/api/v1/gria/chat', json={'message': 'Explain', 'county_name': 'Turkana', 'month': '2025-02'})
        assert chat.status_code == 200
        assert chat.json()['mode'] in ('summary', 'ai')


def test_gria_agent_tool_requires_real_historical_period():
    from agents.tools import get_current_county_risk
    risk_out = get_current_county_risk.invoke({"county_name": "Nakuru", "month": "2025-02"})
    assert risk_out["county"] == "Nakuru"
    assert risk_out["period"] == "2025-02"
    assert "risk_score" in risk_out
    missing = get_current_county_risk.invoke({"county_name": "Nakuru", "month": "2099-01"})
    assert "error" in missing and "risk_score" not in missing


def test_model_imports():
    """Test SQLAlchemy model imports."""
    from database.models import County, CountyFeature, Prediction, Report, ChatMessage, Upload
    assert County.__tablename__ == "counties"
    assert CountyFeature.__tablename__ == "county_features"
    assert Prediction.__tablename__ == "predictions"
    assert Report.__tablename__ == "reports"
    assert ChatMessage.__tablename__ == "chat_messages"
    assert Upload.__tablename__ == "uploads"
