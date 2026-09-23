"""Test SQLAlchemy models."""
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))


def get_test_db():
    from database.connection import SessionLocal, engine, Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return TestSessionLocal, test_engine


def test_model_relationships():
    """Test model relationships are correctly defined."""
    from database.models import County, CountyFeature, Prediction, Report, ChatMessage, Upload

    county = County(name="Turkana", region="Rift Valley",
                      latitude=3.1167, longitude=35.6000, primary_focus="crops")
    assert county.name == "Turkana"
    assert county.region == "Rift Valley"

    feature = CountyFeature(
        county_id=1, rainfall_anomaly_30d=0.0, ndvi_pasture_index=0.5,
        temp_max_avg=28.0, soil_moisture_deficit=40.0)
    assert feature.county_id == 1

    prediction = Prediction(
        county_id=1, focus="crops", risk_score=50, risk_level="MODERATE",
        main_driver="Rainfall deficit", recommendation="Test")
    assert prediction.risk_score == 50
    assert prediction.risk_level == "MODERATE"

    report = Report(county_id=1, report_type="yield", detailed=True, file_path="/tmp/test.pdf")
    assert report.report_type == "yield"

    chat = ChatMessage(county_name="Turkana", user_message="Test", gria_reply="Reply")
    assert chat.county_name == "Turkana"

    upload = Upload(file_name="test.csv", file_type="csv", county_name="Turkana",
                      risk_score=50, risk_level="MODERATE")
    assert upload.file_name == "test.csv"


def test_crud_operations():
    """Test CRUD operations."""
    TestSessionLocal, test_engine = get_test_db()
    from database import models, crud

    db = TestSessionLocal()
    try:
        county = models.County(name="Test County", region="Test",
                                 latitude=0.0, longitude=0.0, primary_focus="crops")
        db.add(county)
        db.commit()
        db.refresh(county)

        fetched = crud.get_county_by_name(db, "Test County")
        assert fetched is not None
        assert fetched.name == "Test County"

        all_counties = crud.get_all_counties(db)
        assert len(all_counties) >= 1

        features = crud.get_latest_features(db, county.id)
        assert features is None

        pred = crud.save_prediction(db, county.id, "crops", 75.0, "HIGH",
                                     "Heat stress", "Reduce irrigation")
        assert pred.risk_score == 75.0

        preds = crud.get_county_predictions(db, county.id)
        assert len(preds) == 1

        report = crud.save_report(db, county.id, "yield", False, "/tmp/test.pdf")
        assert report.report_type == "yield"

        msg = crud.save_chat_message(db, "Test County", "Hello", "Hi", 50.0)
        assert msg.user_message == "Hello"

        upload = crud.save_upload(db, "test.csv", "csv", "Test County", 50.0, "MODERATE")
        assert upload.file_name == "test.csv"
    finally:
        db.close()
        test_engine.dispose()
