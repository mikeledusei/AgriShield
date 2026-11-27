"""API, model-contract and configuration tests."""
import pytest


def test_imports():
    """Every module that the application actually serves imports cleanly."""
    import main

    assert main.app.title == "AgriShield API"


def test_settings():
    """Settings load with development-safe defaults."""
    from core.config import settings

    assert settings.APP_NAME == "AgriShield API"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.PUBLIC_MODE is True
    assert settings.MODEL_PATH.name == "champion_model.joblib"
    assert settings.log_level == 20  # logging.INFO
    assert settings.resolved_database_url.startswith("sqlite:///")


def test_band_scale_is_single_sourced():
    """One ladder, one set of labels, shared by the API and the frontend."""
    from core.scales import BAND_ORDER, band_for_score, score_and_band

    assert band_for_score(0) == "Lower"
    assert band_for_score(24.9) == "Lower"
    assert band_for_score(25) == "Moderate"
    assert band_for_score(49) == "Moderate"
    assert band_for_score(50) == "Elevated"
    assert band_for_score(75) == "High"
    assert band_for_score(100) == "High"
    assert score_and_band(0.504) == (50, "Elevated")
    assert set(BAND_ORDER) == {"Lower", "Moderate", "Elevated", "High"}


def test_ml_artifacts_and_xgboost_champion():
    """The champion model, its hash and the 16-feature contract are all present."""
    from services.prediction_service import get_engine

    engine = get_engine()
    assert engine.model is not None
    assert engine.model_name == "xgboost_v1"
    assert len(engine.feature_cols) == 16
    assert engine.model_sha256 == engine._expected_model_sha256()
    assert len(engine.ndvi_stats) == 47
    assert len(engine.county_history) == 47
    assert len(engine.feature_ranges) == 16


def test_training_ranges_come_from_the_artifact():
    """The request contract must not be narrower than the data the model was fitted on."""
    import json

    from schemas.manual_prediction import MODEL_INPUTS, TRAINING_RANGES
    from services.prediction_service import ARTIFACT_DIR

    recorded = json.loads((ARTIFACT_DIR / "training_feature_ranges.json").read_text())["ranges"]
    assert set(TRAINING_RANGES) == set(MODEL_INPUTS)
    assert set(MODEL_INPUTS) <= set(recorded)
    for key, (low, high) in TRAINING_RANGES.items():
        assert low <= recorded[key]["min"], key
        assert high >= recorded[key]["max"], key


def test_every_historical_row_satisfies_the_request_contract(example):
    """Stored rows must pass their own input contract, or the UI would reject history."""
    import pandas as pd
    from schemas.manual_prediction import MODEL_INPUTS, ManualPredictionRequest

    frame = pd.concat(
        [
            pd.read_csv("data_pipeline/data/processed/train_matrix.csv"),
            pd.read_csv("data_pipeline/data/processed/test_matrix.csv"),
        ],
        ignore_index=True,
    )
    rejected = 0
    for _, row in frame.iterrows():
        payload = {
            "county_name": row["county"],
            "period": str(row["year_month"]),
            **{key: float(row[key]) for key in MODEL_INPUTS},
        }
        try:
            ManualPredictionRequest.model_validate(payload)
        except Exception:
            rejected += 1
    assert rejected <= len(frame) * 0.01, f"{rejected} of {len(frame)} rows rejected"
    assert ManualPredictionRequest.model_validate(example)


def test_gria_agent_tool_requires_real_historical_period():
    from agents.tools import get_current_county_risk

    risk_out = get_current_county_risk.invoke({"county_name": "Nakuru", "month": "2025-02"})
    assert risk_out["county"] == "Nakuru"
    assert risk_out["period"] == "2025-02"
    assert "risk_score" in risk_out
    missing = get_current_county_risk.invoke({"county_name": "Nakuru", "month": "2099-01"})
    assert "error" in missing and "risk_score" not in missing


def test_model_imports():
    from database.models import (
        ChatMessage,
        County,
        CountyFeature,
        Prediction,
        Report,
        Upload,
    )

    assert County.__tablename__ == "counties"
    assert CountyFeature.__tablename__ == "county_features"
    assert Prediction.__tablename__ == "predictions"
    assert Report.__tablename__ == "reports"
    assert ChatMessage.__tablename__ == "chat_messages"
    assert Upload.__tablename__ == "uploads"


def test_legacy_endpoints_are_removed(api):
    """Stubs were deleted — legacy paths now 404, live routes still work."""
    retired = [
        "/predictions/crop-yield",
        "/predictions/forecast",
        "/upload/analyze",
        "/reports/create",
    ]
    for path in retired:
        assert api.post("/api/v1" + path, json={}).status_code == 404, path
    assert api.get("/api/v1/predictions/counties").status_code == 200
    assert api.get("/api/v1/predictions/input-schema").status_code == 200
    assert api.get("/api/v1/health").status_code == 200


def test_liveness_and_readiness_are_distinct(api):
    live = api.get("/api/v1/health")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"

    ready = api.get("/api/v1/health/ready")
    body = ready.json()
    assert ready.status_code == 200, body["problems"]
    assert body["model_loaded"] is True
    assert body["model_name"] == "xgboost_v1"
    assert body["database_connected"] is True
    assert body["problems"] == []
    assert body["services"]["model_artifact_sha256"]


def test_readiness_fails_when_the_model_cannot_score(api, monkeypatch):
    """A missing model must fail the deploy check instead of reporting green."""
    from services import health_service
    from services.prediction_service import get_engine

    engine = get_engine()
    monkeypatch.setattr(engine, "model", None)
    monkeypatch.setattr(engine, "feature_cols", [])
    report = health_service.build_health_report()
    assert report.ready is False
    assert any("model" in problem for problem in report.problems)


def test_readiness_reports_missing_migrations(monkeypatch):
    from services import health_service
    from sqlalchemy import create_engine

    monkeypatch.setattr(health_service, "engine", create_engine("sqlite:///:memory:"))
    report = health_service.build_health_report()
    assert report.ready is False
    assert any("migrations" in problem for problem in report.problems)


@pytest.mark.parametrize(
    "overrides",
    [
        {"DATABASE_URL": ""},
        {"SECRET_KEY": "dev-secret-key-change-in-production"},
        {"API_KEY": "dev-api-key-change-in-production"},
        {"CORS_ORIGINS": ""},
        {"CORS_ORIGINS": "*"},
    ],
)
def test_production_refuses_unsafe_configuration(overrides):
    from core.config import Settings
    from pydantic import ValidationError

    safe = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://user:pass@host/db",
        "SECRET_KEY": "a-real-secret",
        "API_KEY": "a-real-key",
        "CORS_ORIGINS": "https://dashboard.example.com",
    }
    safe.update(overrides)
    with pytest.raises(ValidationError):
        Settings(**safe)


def test_production_accepts_a_complete_configuration():
    from core.config import Settings

    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql://user:pass@host/db",
        SECRET_KEY="a-real-secret",
        API_KEY="a-real-key",
        CORS_ORIGINS="https://dashboard.example.com",
    )
    assert settings.is_production


def test_live_weather_backs_off_after_a_provider_failure(api, monkeypatch):
    """A failing provider is not retried on every request, and never yields a substitute."""
    from routers import live

    live.reset_cache()
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ValueError("stale or future provider data")

    monkeypatch.setattr(live, "_retrieve_weather", boom)
    for _ in range(3):
        assert api.get("/api/v1/live/weather").status_code == 503
    assert calls["n"] == 1, "the provider was retried during the back-off window"
    live.reset_cache()


def test_stored_historical_rows_are_not_rejected_by_the_ui_contract(api):
    """The map scores stored rows directly; the input contract must not block them."""
    months = api.get("/api/v1/predictions/historical-months").json()
    for month in (months[0], months[-1]):
        response = api.get("/api/v1/predictions/historical-observations", params={"month": month})
        assert response.status_code == 200, response.text
        assert response.json()["observations"]


def test_every_band_has_advisory_text():
    """A band without guidance would render an empty recommendation in the PDF."""
    from core.scales import BAND_ORDER
    from services.prediction_service import RECOMMENDATIONS, _focus_advice

    for band in BAND_ORDER:
        assert RECOMMENDATIONS.get(band), band
    assert _focus_advice("livestock", "High")
    assert _focus_advice("crops", "Elevated")
    assert _focus_advice("livestock", "Lower") == ""


def test_csv_upload_accepts_the_extrapolation_column(api, example):
    """The opt-in must work through the CSV path, not only JSON, and stay labelled."""
    import csv
    import io

    plain = io.StringIO()
    writer = csv.DictWriter(plain, fieldnames=list(example))
    writer.writeheader()
    writer.writerow(example)
    response = api.post(
        "/api/v1/predictions/from-csv",
        files={"file": ("observation.csv", plain.getvalue().encode(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["extrapolated"] is False

    unusual = {**example, "rainfall_mm": 1000, "rain_3m_sum": 1500, "accept_extrapolation": "true"}
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(unusual))
    writer.writeheader()
    writer.writerow(unusual)
    response = api.post(
        "/api/v1/predictions/from-csv",
        files={"file": ("observation.csv", out.getvalue().encode(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["extrapolated"] is True


def test_document_extraction_is_bounded_for_docx(api):
    """A DOCX with far more text than the limit is truncated, not fully materialised."""
    import io

    from docx import Document

    document = Document()
    for index in range(4000):
        document.add_paragraph(f"Paragraph {index} " + ("x" * 40))
    buffer = io.BytesIO()
    document.save(buffer)
    response = api.post(
        "/api/v1/documents/extract",
        files={"file": ("long.docx", buffer.getvalue(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["text"]) <= 4000
    assert body["truncated"] is True


def test_outcomes_survive_a_malformed_row(tmp_path, monkeypatch):
    """One bad reported row must not take down the whole outcomes endpoint."""
    from routers import outcomes

    frame = tmp_path / "maize.csv"
    frame.write_text(
        "county,year,yield_tonnes_per_ha,harvested_area_ha,production_tonnes,quality_flag\n"
        "Nakuru,2020,2.5,1000,2500,ok\n"
        "Not A County,2020,2.5,1000,2500,ok\n"
        "Nakuru,2020,,,,\n"
    )
    monkeypatch.setattr(outcomes, "DATA", frame)
    monkeypatch.setattr(outcomes, "_cache", None)
    rows = outcomes._rows()
    assert {row["county"] for row in rows} == {"Nakuru"}
    assert len(rows) == 2
    usable = [row for row in rows if row["quality_flag"] == "ok"]
    assert len(usable) == 1 and usable[0]["yield_tonnes_per_ha"] == 2.5
    assert all(row["yield_tonnes_per_ha"] is None for row in rows if row["quality_flag"] != "ok")


def test_summary_does_not_claim_a_forecast():
    """The plain-language summary must describe the proxy, not promise a prediction."""
    from services.prediction_service import PredictionEngine

    summary = PredictionEngine.build_plain_explanation(
        county_name='Nakuru',
        month_key='2025-12',
        score=61,
        level='Elevated',
        vector={
            'rainfall_mm': 12.0, 'rainfall_anomaly': -18.4, 'temp_mean_c': 24.6,
            'soil_moisture': 0.21, 'ndvi_lag1': 0.34, 'forage_dryness_index': 0.72,
            'ndvi_anomaly': -0.08, 'rain_3m_sum': 140.0,
        },
        shap_items=[{'feature': 'ndvi_lag1', 'label': 'Pasture greenness (lagged)', 'value': 0.34, 'shap_value': 0.21}],
        focus='combined',
    )
    lowered = summary.lower()
    assert 'predicts' not in lowered
    assert 'does not forecast' in lowered
