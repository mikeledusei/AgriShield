"""Explicit inputs for the trained vegetation-stress classifier.

Field names and transformations match ml-models/notebooks/02_feature_engineering.ipynb.
No historical values are silently substituted.
"""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Annotated

Number = Annotated[float, Field(allow_inf_nan=False)]


class ManualPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    county_name: str = Field(min_length=1, max_length=100)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    rainfall_mm: Number = Field(ge=0, le=5000)
    rain_3m_sum: Number = Field(ge=0, le=15000)
    rainfall_anomaly: Number = Field(ge=-5000, le=5000)
    temp_mean_c: Number = Field(ge=-20, le=60)
    soil_moisture: Number = Field(ge=0, le=1)
    ndvi_lag1: Number = Field(ge=-1, le=1)
    ndvi_lag3: Number = Field(ge=-1, le=1)
    ndvi_roll3_mean: Number = Field(ge=-1, le=1)
    ndvi_roll3_std: Number = Field(ge=0, le=1)
    ndvi_anomaly: Number = Field(ge=-2, le=2)
    forage_dryness_index: Number = Field(ge=0, le=100)
    farming_ratio: Number = Field(ge=0, le=1)
    livestock_share: Number = Field(ge=0, le=1)
    irrigation_ratio: Number = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_totals(self):
        if int(self.period[:4]) < 1:
            raise ValueError("Enter a valid calendar year.")
        if self.rain_3m_sum + 1e-6 < self.rainfall_mm:
            raise ValueError("Three-month rainfall must include the selected month's rainfall and cannot be smaller than it.")
        return self


class RawObservationRequest(BaseModel):
    """Raw measurements required to reproduce the notebook's feature engineering."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    county_name: str = Field(min_length=1, max_length=100)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    rainfall_mm: Number = Field(ge=0, le=5000)
    rain_previous_1: Number = Field(ge=0, le=5000)
    rain_previous_2: Number = Field(ge=0, le=5000)
    rain_normal: Number = Field(ge=0, le=5000)
    temp_mean_c: Number = Field(ge=-20, le=60)
    soil_moisture: Number = Field(ge=0, le=1)
    ndvi_lag1: Number = Field(ge=-1, le=1)
    ndvi_lag2: Number = Field(ge=-1, le=1)
    ndvi_lag3: Number = Field(ge=-1, le=1)
    ndvi_historical_mean: Number = Field(ge=-1, le=1)
    ndvi_historical_std: Number = Field(ge=0, le=2)
    total_households: int = Field(ge=1, le=100000000)
    farming_households: int = Field(ge=0, le=100000000)
    crop_households: int = Field(ge=0, le=100000000)
    livestock_households: int = Field(ge=0, le=100000000)
    irrigation_households: int = Field(ge=0, le=100000000)

    @model_validator(mode="after")
    def check_counts(self):
        if int(self.period[:4]) < 1:
            raise ValueError("Enter a valid calendar year.")
        if any(n > self.total_households for n in (self.farming_households, self.crop_households, self.livestock_households)):
            raise ValueError("A household count cannot exceed the total number of households.")
        if self.irrigation_households > self.farming_households:
            raise ValueError("Irrigating households cannot exceed farming households.")
        return self


class CompareInputsRequest(BaseModel):
    """Two complete observations for a non-causal what-if comparison."""
    model_config = ConfigDict(extra='forbid')
    baseline: ManualPredictionRequest
    alternative: ManualPredictionRequest
