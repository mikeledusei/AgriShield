"""SQLAlchemy models for the AgriShield database."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text,
)
from sqlalchemy.orm import relationship
from database.connection import Base


class County(Base):
    __tablename__ = "counties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    region = Column(String, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    primary_focus = Column(String)

    features = relationship("CountyFeature", back_populates="county")
    predictions = relationship("Prediction", back_populates="county")


class CountyFeature(Base):
    __tablename__ = "county_features"

    id = Column(Integer, primary_key=True, index=True)
    county_id = Column(Integer, ForeignKey("counties.id"), index=True)
    record_date = Column(DateTime, default=datetime.utcnow)
    rainfall_anomaly_30d = Column(Float)
    ndvi_pasture_index = Column(Float)
    temp_max_avg = Column(Float)
    soil_moisture_deficit = Column(Float)

    county = relationship("County", back_populates="features")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    county_id = Column(Integer, ForeignKey("counties.id"), index=True)
    prediction_date = Column(DateTime, default=datetime.utcnow)
    focus = Column(String)
    risk_score = Column(Float)
    risk_level = Column(String)
    main_driver = Column(String)
    recommendation = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    county = relationship("County", back_populates="predictions")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    county_id = Column(Integer, ForeignKey("counties.id"), index=True)
    report_type = Column(String)
    detailed = Column(Boolean, default=False)
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    county_name = Column(String)
    user_message = Column(Text)
    gria_reply = Column(Text)
    risk_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String)
    file_type = Column(String)
    county_name = Column(String)
    risk_score = Column(Float)
    risk_level = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)