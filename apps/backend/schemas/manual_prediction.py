"""Explicit inputs for the trained vegetation-stress classifier.

Field names and transformations match ml-models/notebooks/02_feature_engineering.ipynb.
No historical values are silently substituted.

Two validation tiers:

* **Physical plausibility** bounds (the ``Field`` limits) reject values that cannot
  be true measurements, e.g. negative rainfall.
* **Training distribution** bounds come from ``ml_artifacts/training_feature_ranges.json``
  and reject values the deployed model never saw. Tree models extrapolate
  confidently outside their training range, so a score built from those values
  would be presented with more authority than it has.

A caller who genuinely has an out-of-distribution observation can pass
``accept_extrapolation=True``; the response then carries ``training_range_check``
plus ``training_range_warnings`` so the extrapolation is visible wherever the
score is displayed or stored.
"""
import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Number = Annotated[float, Field(allow_inf_nan=False)]

#: Users enter these 14 features; month_sin/month_cos are derived server-side.
MODEL_INPUTS: tuple[str, ...] = (
    "ndvi_lag1", "ndvi_lag3", "ndvi_roll3_mean", "ndvi_roll3_std", "ndvi_anomaly",
    "temp_mean_c", "rainfall_mm", "soil_moisture", "rainfall_anomaly", "rain_3m_sum",
    "forage_dryness_index", "farming_ratio", "livestock_share", "irrigation_ratio",
)

#: Conservative fallback if the artifact metadata is missing. It is deliberately
#: wider than any observed value so a missing file degrades to "warn", not "crash".
FALLBACK_RANGES: dict[str, tuple[float, float]] = {
    "ndvi_lag1": (0.0, 1.0),
    "ndvi_lag3": (0.0, 1.0),
    "ndvi_roll3_mean": (0.0, 1.0),
    "ndvi_roll3_std": (0.0, 1.0),
    "ndvi_anomaly": (-2.0, 2.0),
    "temp_mean_c": (-20.0, 60.0),
    "rainfall_mm": (0.0, 2000.0),
    "soil_moisture": (0.0, 1.0),
    "rainfall_anomaly": (-2000.0, 2000.0),
    "rain_3m_sum": (0.0, 6000.0),
    "forage_dryness_index": (0.0, 100.0),
    "farming_ratio": (0.0, 1.0),
    "livestock_share": (0.0, 1.0),
    "irrigation_ratio": (0.0, 1.0),
}

RANGES_PATH = Path(__file__).resolve().parents[1] / "ml_artifacts" / "training_feature_ranges.json"


def _load_training_ranges() -> dict[str, tuple[float, float]]:
    """Training min/max per feature, read from the artifact that ships with the model.

    The recorded bounds are rounded, so they are padded outward slightly: a stored
    training row must never be rejected by its own contract.
    """
    try:
        raw = json.loads(RANGES_PATH.read_text(encoding="utf-8"))["ranges"]
    except (OSError, KeyError, ValueError, TypeError):
        return dict(FALLBACK_RANGES)
    ranges: dict[str, tuple[float, float]] = {}
    for key in MODEL_INPUTS:
        bounds = raw.get(key)
        try:
            low, high = float(bounds["min"]), float(bounds["max"])
        except (KeyError, TypeError, ValueError):
            return dict(FALLBACK_RANGES)
        pad = max((high - low) * 0.02, 1e-4)
        ranges[key] = (round(low - pad, 6), round(high + pad, 6))
    return ranges


TRAINING_RANGES: dict[str, tuple[float, float]] = _load_training_ranges()

#: Human-readable units, used in rejection messages.
UNITS: dict[str, str] = {
    "rainfall_mm": "mm",
    "rain_3m_sum": "mm",
    "rainfall_anomaly": "mm",
    "temp_mean_c": "°C",
    "soil_moisture": "m³/m³",
    "ndvi_lag1": "NDVI",
    "ndvi_lag3": "NDVI",
    "ndvi_roll3_mean": "NDVI",
    "ndvi_roll3_std": "NDVI",
    "ndvi_anomaly": "NDVI difference",
    "forage_dryness_index": "index",
    "farming_ratio": "fraction",
    "livestock_share": "fraction",
    "irrigation_ratio": "fraction",
}

#: Hints for the most likely wrong-unit mistake, keyed by feature.
UNIT_HINTS: dict[str, str] = {
    "forage_dryness_index": "this index is a fraction-like value, not a percentage",
    "farming_ratio": "enter a fraction such as 0.65, not 65",
    "livestock_share": "enter a fraction such as 0.45, not 45",
    "irrigation_ratio": "enter a fraction such as 0.05, not 5",
    "soil_moisture": "enter volumetric soil moisture as a fraction such as 0.25, not 25",
}


def training_range_violations(values: dict) -> list[str]:
    """Return one message per feature outside its training range."""
    problems = []
    for key, (low, high) in TRAINING_RANGES.items():
        if key not in values or values[key] is None:
            continue
        value = float(values[key])
        if low <= value <= high:
            continue
        unit = UNITS.get(key, "")
        hint = UNIT_HINTS.get(key)
        message = (
            f"{key}={value:g} {unit} is outside the training range "
            f"[{low:g}, {high:g}]"
        )
        if hint:
            message += f" ({hint})"
        problems.append(message)
    return problems


class ManualPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    county_name: str = Field(min_length=1, max_length=100)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    rainfall_mm: Number = Field(ge=0, le=2000)
    rain_3m_sum: Number = Field(ge=0, le=6000)
    rainfall_anomaly: Number = Field(ge=-2000, le=2000)
    temp_mean_c: Number = Field(ge=-20, le=60)
    soil_moisture: Number = Field(ge=0, le=1)
    ndvi_lag1: Number = Field(ge=-1, le=1)
    ndvi_lag3: Number = Field(ge=-1, le=1)
    ndvi_roll3_mean: Number = Field(ge=-1, le=1)
    ndvi_roll3_std: Number = Field(ge=0, le=1)
    ndvi_anomaly: Number = Field(ge=-2, le=2)
    # Wide on purpose: a percentage entry (40) is caught by the training-range
    # check below with a targeted unit hint instead of a bare bound error.
    forage_dryness_index: Number = Field(ge=0, le=100)
    farming_ratio: Number = Field(ge=0, le=1)
    livestock_share: Number = Field(ge=0, le=1)
    irrigation_ratio: Number = Field(ge=0, le=1)

    #: Opt in to scoring values outside the training distribution.
    accept_extrapolation: bool = Field(
        default=False,
        description=(
            "Score an observation outside the model's training ranges. The result is "
            "flagged as extrapolation; it is not a validated estimate."
        ),
    )

    @model_validator(mode="after")
    def check_consistency(self):
        if int(self.period[:4]) < 1:
            raise ValueError("Enter a valid calendar year.")
        if self.rain_3m_sum + 1e-6 < self.rainfall_mm:
            raise ValueError(
                "Three-month rainfall must include the selected month's rainfall and cannot be smaller than it."
            )
        violations = training_range_violations(self.model_dump())
        if violations and not self.accept_extrapolation:
            raise ValueError(
                "Outside the model's training range: "
                + "; ".join(violations)
                + ". Correct the value or resubmit with accept_extrapolation=true to record an extrapolation."
            )
        return self

    @property
    def extrapolation_reasons(self) -> list[str]:
        return training_range_violations(self.model_dump())

    def model_values(self) -> dict[str, float]:
        """The 14 model inputs, without county/period/opt-in fields."""
        return {key: float(getattr(self, key)) for key in MODEL_INPUTS}


class RawObservationRequest(BaseModel):
    """Raw measurements required to reproduce the notebook's feature engineering."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    county_name: str = Field(min_length=1, max_length=100)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    rainfall_mm: Number = Field(ge=0, le=2000)
    rain_previous_1: Number = Field(ge=0, le=2000)
    rain_previous_2: Number = Field(ge=0, le=2000)
    rain_normal: Number = Field(ge=0, le=2000)
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
    accept_extrapolation: bool = False

    @model_validator(mode="after")
    def check_counts(self):
        if int(self.period[:4]) < 1:
            raise ValueError("Enter a valid calendar year.")
        if any(
            n > self.total_households
            for n in (self.farming_households, self.crop_households, self.livestock_households)
        ):
            raise ValueError("A household count cannot exceed the total number of households.")
        if self.irrigation_households > self.farming_households:
            raise ValueError("Irrigating households cannot exceed farming households.")
        return self


class CompareInputsRequest(BaseModel):
    """Two complete observations for a non-causal what-if comparison."""

    model_config = ConfigDict(extra='forbid')
    baseline: ManualPredictionRequest
    alternative: ManualPredictionRequest
