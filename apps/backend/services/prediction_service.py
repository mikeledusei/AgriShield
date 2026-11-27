"""
AgriShield Prediction & TreeSHAP Explainability Engine (2015-2025 pipeline).

Scorer: XGBoost champion (ml_artifacts/champion_model.joblib → xgboost_agrishield_v1.joblib),
selected on 2022-2023 validation F1 (0.8689). LightGBM artifact remains in ml_artifacts
for reproducibility but is not served. Loaded only after its SHA-256 matches the hash
recorded with the training ranges. Explainability: exact TreeSHAP contributions.

There is no fallback scorer. If the artifact is missing, unreadable or fails its
hash check, every scoring path raises and the API reports the model as
unavailable; it never substitutes a rule-based or historical number for a score.
"""
import hashlib
import json
import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from core.config import settings
from core.scales import score_and_band
from database import models
from seed_counties import COUNTY_METADATA, ensure_counties_seeded, normalize_county_name
from sqlalchemy.orm import Session

logger = logging.getLogger("agrishield")

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent.parent
ARTIFACT_DIR = BACKEND_DIR / "ml_artifacts"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data_pipeline" / "data" / "processed"

# Default benchmark month showing realistic dry-season risk differentiation across Kenya's 47 counties
DEFAULT_ACTIVE_MONTH = "2025-02"

FEATURE_LABELS: dict[str, str] = {
    "forage_dryness_index": "Forage Dryness Index (Pasture Stress)",
    "rainfall_mm": "Monthly Rainfall (mm)",
    "ndvi_anomaly": "NDVI Vegetation Anomaly (vs. Normal)",
    "rain_3m_sum": "3-Month Cumulative Rainfall (mm)",
    "rainfall_anomaly": "30-Day Rainfall Anomaly (mm vs. Normal)",
    "soil_moisture": "Root-Zone Soil Moisture (m³/m³)",
    "ndvi_roll3_std": "3-Month NDVI Volatility (Std Dev)",
    "ndvi_lag3": "Pasture Greenness 3 Months Ago (NDVI Lag-3)",
    "ndvi_roll3_mean": "3-Month Rolling Pasture Greenness (NDVI Mean)",
    "temp_mean_c": "Land Surface Temperature (°C)",
    "month_sin": "Seasonal Cycle (Sine Component)",
    "irrigation_ratio": "County Irrigation Coverage Ratio",
    "livestock_share": "County Livestock Household Share",
    "month_cos": "Seasonal Cycle (Cosine Component)",
    "ndvi_lag1": "Previous Month Pasture Greenness (NDVI Lag-1)",
    "farming_ratio": "County Farming Household Ratio",
}

class CountyNotFoundError(Exception):
    pass


# ------------------------------------------------------------ risk levels

def get_risk_level(score: float) -> str:
    """Legacy label mapping kept for stored snapshots and the research scripts."""
    if score < 25:
        return "SAFE"
    if score < 50:
        return "MODERATE"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


RECOMMENDATIONS = {
    "Lower": "Conditions are favourable. Continue routine monitoring, soil conservation, and normal planting or grazing operations.",
    "Moderate": "Early moisture and pasture stress detected. Increase field monitoring, conserve water, and prepare supplemental livestock fodder.",
    "Elevated": "Significant drought stress detected. Activate county drought response, prioritise smallholder irrigation and drought-tolerant seeds, and pre-position livestock feed.",
    "High": "Severe agricultural and forage shock. Escalate to national emergency management; deploy emergency water trucking, livestock feed relief, and targeted cash transfers.",
}


def _focus_advice(focus: str | None, level: str) -> str:
    if level not in ("HIGH", "CRITICAL", "Elevated", "High"):
        return ""
    if (focus or "").lower() == "livestock":
        return " Prioritise emergency fodder banks, borehole maintenance, and veterinary outreach for pastoral herds."
    if (focus or "").lower() in ("crop", "crops"):
        return " Fast-track early-maturing drought-tolerant seeds, mulching, and micro-irrigation support."
    return ""


# ------------------------------------------------------------------ engine
class PredictionEngine:
    """Loads ML artifacts once; serves predictions, future forecasts, and TreeSHAP explanations."""

    def __init__(self) -> None:
        self.model = None
        self.model_sha256 = None
        self.model_name: str = "rule_based"
        self.scaler = None
        self.feature_cols: list[str] = []
        self.ndvi_stats: dict[str, dict[str, float]] = {}
        self.county_history: dict[str, pd.DataFrame] = {}
        self.available_months: list[str] = []
        self.rain_clim: dict[tuple[str, int], float] = {}
        self.feature_ranges: dict[str, dict[str, float]] = {}
        self._load_artifacts()

    @staticmethod
    def _expected_model_sha256() -> str | None:
        """Artifact hash recorded alongside the training ranges, if present."""
        ranges_path = ARTIFACT_DIR / 'training_feature_ranges.json'
        try:
            return json.loads(ranges_path.read_text(encoding='utf-8')).get('model_sha256')
        except (OSError, ValueError, TypeError):
            return None

    # ------------------------------------------------------------ loading
    def _load_artifacts(self) -> None:
        cols_path = ARTIFACT_DIR / "feature_columns.json"
        if cols_path.exists():
            try:
                self.feature_cols = json.loads(cols_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to read feature_columns.json: {exc}")
                self.feature_cols = []

        scaler_path = ARTIFACT_DIR / "scaler.joblib"
        if scaler_path.exists():
            try:
                self.scaler = joblib.load(scaler_path)
            except Exception as exc:
                logger.warning(f"Failed to load scaler.joblib: {exc}")

        model_path = settings.MODEL_PATH
        if model_path.exists() and self.feature_cols:
            try:
                digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
                expected = self._expected_model_sha256()
                if settings.REQUIRE_MODEL_HASH and expected and digest != expected:
                    # joblib.load runs arbitrary code, so the digest is verified first.
                    logger.error(
                        'Refusing to load %s: SHA-256 %s does not match the recorded artifact hash %s.',
                        model_path.name, digest[:12], expected[:12],
                    )
                elif settings.REQUIRE_MODEL_HASH and not expected:
                    logger.error(
                        'Refusing to load %s: no artifact hash is recorded in training_feature_ranges.json.',
                        model_path.name,
                    )
                else:
                    self.model = joblib.load(model_path)
                    self.model_sha256 = digest
                    cls_name = type(self.model).__name__.lower()
                    if 'lgbm' in cls_name or 'lightgbm' in cls_name:
                        self.model_name = 'lightgbm_v1'
                    elif 'xgb' in cls_name or 'xgboost' in cls_name:
                        self.model_name = 'xgboost_v1'
                    else:
                        self.model_name = type(self.model).__name__
                    logger.info('Model loaded from %s (%s).', model_path.name, self.model_name)
            except Exception as exc:
                logger.error('Could not load configured model %s: %s', model_path.name, exc)
                self.model = None
                self.model_sha256 = None
        elif not model_path.exists():
            logger.error('Model artifact %s is missing; scoring endpoints will report it as unavailable.', model_path)

        # Recorded training ranges, used by the request contract and the UI sliders.
        ranges_path = ARTIFACT_DIR / 'training_feature_ranges.json'
        if ranges_path.exists():
            try:
                payload = json.loads(ranges_path.read_text(encoding='utf-8'))
                self.feature_ranges = {
                    key: {'min': float(bounds['min']), 'max': float(bounds['max'])}
                    for key, bounds in payload.get('ranges', {}).items()
                }
            except Exception as exc:
                logger.warning('Could not read %s: %s', ranges_path.name, exc)

        for stats_path in (
            ARTIFACT_DIR / "county_ndvi_stats.csv",
            PROCESSED_DATA_DIR / "county_ndvi_stats.csv",
        ):
            if stats_path.exists():
                try:
                    stats_df = pd.read_csv(stats_path)
                    for r in stats_df.itertuples():
                        mean_val = float(
                            getattr(r, "ndvi_mean_hist", getattr(r, "ndvi_mean_train", 0.5))
                        )
                        std_val = float(
                            getattr(r, "ndvi_std_hist", getattr(r, "ndvi_std_train", 0.08))
                        ) or 1e-6
                        pct25_val = float(getattr(r, "ndvi_25th_pct", mean_val - 0.674 * std_val))
                        c_name = normalize_county_name(getattr(r, "county", ""))
                        self.ndvi_stats[c_name] = {
                            "mean": mean_val,
                            "std": std_val,
                            "pct25": pct25_val,
                        }
                    break
                except Exception as exc:
                    logger.warning(f"Failed to read {stats_path}: {exc}")

        frames: list[pd.DataFrame] = []
        for matrix_name in ("train_matrix.csv", "test_matrix.csv"):
            m_path = PROCESSED_DATA_DIR / matrix_name
            if m_path.exists():
                try:
                    frames.append(pd.read_csv(m_path))
                except Exception as exc:
                    logger.warning(f"Failed to read {m_path}: {exc}")

        if frames:
            full_df = pd.concat(frames, ignore_index=True)
            full_df["county"] = full_df["county"].map(normalize_county_name)
            if "year_month" not in full_df.columns and {"year", "month"}.issubset(full_df.columns):
                full_df["year_month"] = (
                    full_df["year"].astype(int).astype(str)
                    + "-"
                    + full_df["month"].astype(int).astype(str).str.zfill(2)
                )
            full_df = full_df.sort_values(["county", "year_month"]).reset_index(drop=True)
            self.available_months = sorted(full_df["year_month"].dropna().unique().tolist())
            self.county_history = {
                c: grp.reset_index(drop=True) for c, grp in full_df.groupby("county")
            }
            if {"county", "month", "rainfall_mm"}.issubset(full_df.columns):
                clim = (
                    full_df[full_df["year"] <= 2023]
                    .groupby(["county", "month"], as_index=False)["rainfall_mm"]
                    .mean()
                )
                self.rain_clim = {
                    (str(r.county), int(r.month)): float(r.rainfall_mm)
                    for r in clim.itertuples()
                }

        logger.info(
            f"Prediction engine ready (model={self.model_name}, "
            f"counties_with_history={len(self.county_history)}, "
            f"counties_with_stats={len(self.ndvi_stats)})."
        )

    def get_available_months(self) -> list[str]:
        return list(self.available_months)

    def _resolve_month(self, county: str, requested_month: str | None = None) -> str:
        c_name = normalize_county_name(county)
        hist = self.county_history.get(c_name)
        if hist is None or hist.empty or "year_month" not in hist.columns:
            raise ValueError(f"No historical data is available for {c_name}.")
        available = set(hist["year_month"].astype(str))
        if requested_month:
            if str(requested_month) not in available:
                raise ValueError(f"No historical data is available for {c_name} in {requested_month}.")
            return str(requested_month)
        return str(hist["year_month"].iloc[-1])

    def _build_vector(self, county: str, month_key: str | None = None) -> dict[str, float] | None:
        c_name = normalize_county_name(county)
        hist = self.county_history.get(c_name)
        resolved_month = self._resolve_month(c_name, month_key)
        sub = hist[hist["year_month"] == resolved_month]
        if sub.empty:
            return None
        row = sub.iloc[-1]
        if not self.feature_cols or any(c not in row.index or pd.isna(row[c]) for c in self.feature_cols):
            return None
        return {c: float(row[c]) for c in self.feature_cols}

    # --------------------------------------------------- TreeSHAP & scoring
    def _compute_shap(
        self, vector: dict[str, float]
    ) -> tuple[list[dict[str, Any]], float]:
        """Compute exact TreeSHAP feature contributions (log-odds) for a 16-feature vector."""
        if self.model is None or not self.feature_cols:
            return [], 0.0

        x = pd.DataFrame(
            [[float(vector[c]) for c in self.feature_cols]],
            columns=self.feature_cols,
        )
        shap_vals = np.zeros(len(self.feature_cols), dtype=float)
        base_val = 0.0

        try:
            booster = None
            if hasattr(self.model, "get_booster"):
                try:
                    booster = self.model.get_booster()
                except Exception:
                    booster = None
            elif hasattr(self.model, "booster_"):
                booster = self.model.booster_
            if booster is not None:
                import xgboost as xgb
                dmat = xgb.DMatrix(x, enable_categorical=False)
                contrib = booster.predict(dmat, pred_contribs=True)[0]
                shap_vals = np.asarray(contrib[:-1], dtype=float)
                base_val = float(contrib[-1])
            else:
                import shap
                explainer = shap.TreeExplainer(self.model)
                sv = explainer.shap_values(x)
                if isinstance(sv, list):
                    shap_vals = np.asarray(sv[1][0], dtype=float)
                else:
                    shap_vals = np.asarray(sv[0], dtype=float)
        except Exception as exc:
            logger.warning(f"SHAP computation unavailable: {exc}")
            return [], 0.0

        items: list[dict[str, Any]] = []
        for col, s_val in zip(self.feature_cols, shap_vals, strict=False):
            val = float(vector.get(col, 0.0))
            direction = (
                "increases_risk"
                if s_val > 0.01
                else "reduces_risk"
                if s_val < -0.01
                else "neutral"
            )
            items.append({
                "feature": col,
                "label": FEATURE_LABELS.get(col, col),
                "value": round(val, 4),
                "shap_value": round(float(s_val), 4),
                "impact_direction": direction,
            })

        items.sort(key=lambda d: abs(d["shap_value"]), reverse=True)
        return items, round(base_val, 4)

    def get_global_importance(self) -> list[dict[str, Any]]:
        """Return global feature importances across all 16 features of the champion model."""
        if self.model is None or not hasattr(self.model, "feature_importances_"):
            return []
        raw_imp = np.asarray(self.model.feature_importances_, dtype=float)
        total = float(raw_imp.sum()) or 1.0
        items = []
        for col, imp in zip(self.feature_cols, raw_imp, strict=False):
            items.append({
                "feature": col,
                "label": FEATURE_LABELS.get(col, col),
                "importance": round(float(imp), 2),
                "importance_pct": round(float(imp * 100.0 / total), 2),
            })
        items.sort(key=lambda d: d["importance"], reverse=True)
        return items

    @staticmethod
    def _driver_from_shap(
        score: int,
        shap_items: list[dict[str, Any]],
        vector: dict[str, float],
    ) -> str:
        if shap_items:
            pos = [
                it
                for it in shap_items
                if it["shap_value"] > 0 and it["feature"] not in ("month_sin", "month_cos")
            ]
            neg = [
                it
                for it in shap_items
                if it["shap_value"] < 0 and it["feature"] not in ("month_sin", "month_cos")
            ]
            if score >= 25 and pos:
                top = pos[0]
                return f"{top['label']} ({top['value']:g}, SHAP {top['shap_value']:+.2f})"
            if score < 25 and neg:
                top = neg[0]
                return f"Favorable {top['label']} ({top['value']:g}, SHAP {top['shap_value']:+.2f})"
            top = shap_items[0]
            return f"{top['label']} ({top['value']:g}, SHAP {top['shap_value']:+.2f})"

        if vector.get("forage_dryness_index", 0.0) >= 0.45:
            return "Forage Dryness Index (Pasture Stress)"
        if vector.get("rainfall_anomaly", 0.0) <= -15.0:
            return "30-Day Rainfall Anomaly Deficit"
        return "Favorable agro-climatic baseline"

    @staticmethod
    def build_plain_explanation(
        county_name: str,
        month_key: str,
        score: int,
        level: str,
        vector: dict[str, float] | None,
        shap_items: list[dict[str, Any]],
        focus: str = "combined",
    ) -> str:
        """Build a clear, jargon-free explanation of the model's output and SHAP drivers."""
        if not vector:
            return (
                f"In {county_name} ({month_key}), the estimated risk score is {score}/100 ({level}). "
                f"{RECOMMENDATIONS.get(level, '')}"
            )

        rain_mm = vector.get("rainfall_mm", 0.0)
        rain_anom = vector.get("rainfall_anomaly", 0.0)
        soil_m = vector.get("soil_moisture", 0.0)
        temp_c = vector.get("temp_mean_c", 0.0)
        ndvi_l1 = vector.get("ndvi_lag1", 0.0)
        fdi = vector.get("forage_dryness_index", 0.0)

        pos_drivers = [
            it for it in shap_items if it["shap_value"] > 0.05 and it["feature"] not in ("month_sin", "month_cos")
        ][:3]
        neg_drivers = [
            it for it in shap_items if it["shap_value"] < -0.05 and it["feature"] not in ("month_sin", "month_cos")
        ][:2]

        why_parts = []
        if pos_drivers:
            names = ", ".join(f"**{d['label']}** ({d['value']:g})" for d in pos_drivers)
            why_parts.append(f"The main factors pushing drought risk upward are {names}.")
        if neg_drivers:
            names = ", ".join(f"**{d['label']}** ({d['value']:g})" for d in neg_drivers)
            why_parts.append(f"Protective factors helping hold risk down include {names}.")
        why_text = " ".join(why_parts) or "Agro-climatic indicators are near their seasonal averages."

        rain_word = (
            f"{abs(rain_anom):.1f} mm below normal"
            if rain_anom < -2
            else f"{rain_anom:.1f} mm above normal"
            if rain_anom > 2
            else "near the historical average"
        )

        return (
            f"**Plain-Language Summary for {county_name} ({month_key}):**\n"
            f"- **Model Verdict:** The champion model scores **{score}/100 ({level})** for low-vegetation "
            "conditions in this month. It estimates how unusual the vegetation is against that county's own "
            "training-period baseline; it does not forecast a future month, crop loss or forage deficit.\n"
            f"- **What the Field Numbers Show:** Monthly rainfall is **{rain_mm:.1f} mm** ({rain_word}), "
            f"land surface temperature is **{temp_c:.1f} °C**, root-zone soil moisture is **{soil_m:.2f} m³/m³**, "
            f"pasture greenness (NDVI) is **{ndvi_l1:.2f}**, and the **Forage Dryness Index** is **{fdi:.2f}**.\n"
            f"- **Why the Model Decided This (SHAP Explainability):** {why_text}\n"
            f"- **Recommended Action:** {RECOMMENDATIONS.get(level, '')}{_focus_advice(focus, level)}"
        )

    def _score(
        self,
        county: str,
        month_key: str | None,
        vector: dict[str, float] | None,
    ) -> tuple[int, str, str, str, list[dict[str, Any]]]:
        """Returns (score, band, driver, model_used, shap_contributions).

        Raises rather than substituting another number: a missing or failing model is
        an availability problem, not a reason to invent a score.
        """
        if self.model is None or not self.feature_cols:
            raise ValueError(f"No trained model is loaded, so {county} in {month_key} cannot be scored.")
        if vector is None:
            raise ValueError(f"No complete historical feature row exists for {county} in {month_key}.")
        missing = set(self.feature_cols) - set(vector)
        if missing:
            raise ValueError(f"Feature vector for {county} in {month_key} is missing {sorted(missing)}.")
        try:
            x = pd.DataFrame(
                [[float(vector[c]) for c in self.feature_cols]],
                columns=self.feature_cols,
            )
            proba = float(self.model.predict_proba(x)[0][1])
        except Exception as exc:
            raise ValueError(f"The model could not score {county} in {month_key}.") from exc
        if not math.isfinite(proba) or not 0.0 <= proba <= 1.0:
            raise ValueError(f"The model returned an invalid probability for {county} in {month_key}.")
        score, band = score_and_band(proba)
        shap_items, _ = self._compute_shap(vector)
        driver = self._driver_from_shap(score, shap_items, vector)
        return score, band, driver, self.model_name, shap_items

    # ----------------------------------------------------------- public API
    def _get_county(self, db: Session | None, name: str) -> models.County:
        canonical = normalize_county_name(name)
        if db is not None:
            try:
                county = (
                    db.query(models.County)
                    .filter(models.County.name.ilike(canonical))
                    .first()
                )
            except Exception:
                db.rollback()
                ensure_counties_seeded(db)
                county = None

            if county is None and canonical != name.strip():
                try:
                    county = (
                        db.query(models.County)
                        .filter(models.County.name.ilike(name.strip()))
                        .first()
                    )
                except Exception:
                    db.rollback()
                    county = None

            if county is None and canonical in COUNTY_METADATA:
                ensure_counties_seeded(db)
                try:
                    county = (
                        db.query(models.County)
                        .filter(models.County.name.ilike(canonical))
                        .first()
                    )
                except Exception:
                    db.rollback()
                    county = None

            if county is not None:
                return county

        if canonical in COUNTY_METADATA:
            meta = COUNTY_METADATA[canonical]
            return models.County(
                id=0,
                name=canonical,
                region=meta["region"],
                latitude=meta["latitude"],
                longitude=meta["longitude"],
                primary_focus=meta["primary_focus"],
            )
        raise CountyNotFoundError(f"County '{name}' not found.")

    def predict_for_county_obj(
        self,
        db: Session | None,
        county: models.County,
        focus: str | None = None,
        month: str | None = None,
        include_shap: bool = True,
    ) -> dict:
        focus = focus or county.primary_focus or "crops"
        month_key = self._resolve_month(county.name, month)
        vector = self._build_vector(county.name, month_key)
        score, level, driver, used, shap_items = self._score(county.name, month_key, vector)
        rec = RECOMMENDATIONS[level] + _focus_advice(focus, level)
        plain = self.build_plain_explanation(
            county.name, month_key, score, level, vector, shap_items, focus=focus
        )
        out = {
            "county_name": county.name,
            "region": county.region,
            "focus": focus,
            "month": month_key,
            "risk_score": score,
            "risk_level": level,
            "main_driver": driver,
            "recommendation": rec,
            "model_used": used,
            "plain_summary": plain,
            "features": vector,
            "shap_contributions": shap_items if include_shap else None,
        }
        return out

    def predict(
        self,
        db: Session | None,
        county_name: str,
        focus: str | None = None,
        month: str | None = None,
    ) -> dict:
        county = self._get_county(db, county_name)
        return self.predict_for_county_obj(db, county, focus=focus, month=month)

    def explain(
        self,
        db: Session | None,
        county_name: str,
        month: str | None = None,
    ) -> dict:
        """Return full local TreeSHAP waterfall + global feature importance for a county."""
        county = self._get_county(db, county_name)
        month_key = self._resolve_month(county.name, month)
        vector = self._build_vector(county.name, month_key) or {}
        score, level, driver, _, shap_items = self._score(county.name, month_key, vector or None)
        _, base_val = self._compute_shap(vector)
        plain = self.build_plain_explanation(
            county.name, month_key, score, level, vector, shap_items, focus=county.primary_focus or "combined"
        )
        return {
            "county_name": county.name,
            "month": month_key,
            "risk_score": score,
            "risk_level": level,
            "base_value": base_val,
            "main_driver": driver,
            "plain_explanation": plain,
            "local_shap": shap_items,
            "global_importance": self.get_global_importance(),
            "feature_ranges": self.feature_ranges,
        }

@lru_cache
def get_engine() -> PredictionEngine:
    return PredictionEngine()
