"""
AgriShield Prediction, Future Forecasting & TreeSHAP Explainability Engine (2015–2025 Pipeline).
Primary scorer: LightGBM Champion (ml_artifacts/lightgbm_agrishield_v1.joblib).
Explainability: Exact TreeSHAP feature contributions (pred_contrib=True) + Global Importance.
Fallback scorer: transparent rule-based engine (always available).
"""
import json
import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from database import models
from seed_counties import COUNTY_METADATA, ensure_counties_seeded, normalize_county_name

logger = logging.getLogger("agrishield")

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent.parent
ARTIFACT_DIR = BACKEND_DIR / "ml_artifacts"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data_pipeline" / "data" / "processed"

# Default benchmark month showing realistic dry-season risk differentiation across Kenya's 47 counties
DEFAULT_ACTIVE_MONTH = "2025-02"

FEATURE_LABELS: Dict[str, str] = {
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

FEATURE_RANGES: Dict[str, Dict[str, float]] = {
    "rainfall_mm": {"min": 0.0, "max": 450.0, "step": 5.0, "default": 65.0},
    "rain_3m_sum": {"min": 0.0, "max": 1000.0, "step": 10.0, "default": 220.0},
    "rainfall_anomaly": {"min": -200.0, "max": 200.0, "step": 5.0, "default": -10.0},
    "temp_mean_c": {"min": 10.0, "max": 38.5, "step": 0.5, "default": 24.0},
    "soil_moisture": {"min": 0.03, "max": 0.47, "step": 0.01, "default": 0.25},
    "ndvi_lag1": {"min": 0.15, "max": 0.82, "step": 0.01, "default": 0.55},
    "ndvi_lag3": {"min": 0.15, "max": 0.82, "step": 0.01, "default": 0.56},
    "ndvi_roll3_mean": {"min": 0.15, "max": 0.82, "step": 0.01, "default": 0.55},
    "ndvi_roll3_std": {"min": 0.00, "max": 0.20, "step": 0.005, "default": 0.04},
    "ndvi_anomaly": {"min": -0.25, "max": 0.25, "step": 0.01, "default": 0.00},
    "forage_dryness_index": {"min": 0.00, "max": 1.80, "step": 0.02, "default": 0.20},
    "farming_ratio": {"min": 0.02, "max": 0.85, "step": 0.01, "default": 0.65},
    "livestock_share": {"min": 0.35, "max": 0.88, "step": 0.01, "default": 0.45},
    "irrigation_ratio": {"min": 0.01, "max": 0.30, "step": 0.005, "default": 0.05},
    "month_sin": {"min": -1.0, "max": 1.0, "step": 0.05, "default": 0.5},
    "month_cos": {"min": -1.0, "max": 1.0, "step": 0.05, "default": 0.866},
}


class CountyNotFoundError(Exception):
    pass


# ---------------------------------------------------------------- risk scale
def get_risk_level(score: float) -> str:
    if score < 25:
        return "SAFE"
    if score < 50:
        return "MODERATE"
    if score < 75:
        return "HIGH"
    return "CRITICAL"


RECOMMENDATIONS = {
    "SAFE": "Conditions are favorable. Continue routine monitoring, soil conservation, and normal planting or grazing operations.",
    "MODERATE": "Early moisture and pasture stress detected. Increase field monitoring, conserve water, and prepare supplemental livestock fodder.",
    "HIGH": "Significant drought stress detected. Activate county drought response, prioritize smallholder irrigation and drought-tolerant seeds, and pre-position livestock feed.",
    "CRITICAL": "Severe agricultural & forage shock. Escalate to national emergency management; deploy emergency water trucking, livestock feed relief, and targeted cash transfers immediately.",
}


def _focus_advice(focus: Optional[str], level: str) -> str:
    if level not in ("HIGH", "CRITICAL"):
        return ""
    if (focus or "").lower() == "livestock":
        return " Prioritize emergency fodder banks, borehole maintenance, and veterinary outreach for pastoral herds."
    if (focus or "").lower() in ("crop", "crops"):
        return " Fast-track early-maturing drought-tolerant seeds, mulching, and micro-irrigation support."
    return ""


# ------------------------------------------------------------- rule engine
def _rule_components(f: Dict[str, float]) -> Dict[str, float]:
    rain = float(f.get("rainfall_anomaly_30d", 0.0))
    ndvi = float(f.get("ndvi_pasture_index", 0.5))
    temp = float(f.get("temp_max_avg", 28.0))
    soil = float(f.get("soil_moisture_deficit", 40.0))
    return {
        "Rainfall deficit": 40 if rain <= -30 else 25 if rain <= -10 else 10 if rain < 0 else 0,
        "Vegetation stress (NDVI)": 30 if ndvi <= 0.25 else 20 if ndvi <= 0.4 else 8 if ndvi <= 0.55 else 0,
        "Heat stress": 15 if temp >= 34 else 8 if temp >= 31 else 0,
        "Soil moisture deficit": 15 if soil >= 70 else 8 if soil >= 55 else 0,
    }


def compute_score(f: Dict[str, float]) -> int:
    return int(min(100, max(0, sum(_rule_components(f).values()))))


def _main_driver(comps: Dict[str, float]) -> str:
    top = max(comps, key=comps.get)
    return top if comps[top] > 0 else "No dominant risk factor detected"


# ------------------------------------------------------------------ engine
class PredictionEngine:
    """Loads ML artifacts once; serves predictions, future forecasts, and TreeSHAP explanations."""

    def __init__(self) -> None:
        self.model = None
        self.model_name: str = "rule_based"
        self.scaler = None
        self.feature_cols: List[str] = []
        self.ndvi_stats: Dict[str, Dict[str, float]] = {}
        self.county_history: Dict[str, pd.DataFrame] = {}
        self.available_months: List[str] = []
        self.rain_clim: Dict[Tuple[str, int], float] = {}
        self._load_artifacts()

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

        candidate_models = [
            (ARTIFACT_DIR / "lightgbm_agrishield_v1.joblib", "lightgbm_v1"),
            (ARTIFACT_DIR / "champion_model.joblib", "lightgbm_v1"),
            (ARTIFACT_DIR / "xgboost_agrishield_v1.joblib", "xgboost_v1"),
        ]
        for model_path, model_tag in candidate_models:
            if model_path.exists() and self.feature_cols:
                try:
                    self.model = joblib.load(model_path)
                    cls_name = type(self.model).__name__.lower()
                    if "lgbm" in cls_name or "lightgbm" in cls_name:
                        self.model_name = "lightgbm_v1"
                    elif "xgb" in cls_name:
                        self.model_name = "xgboost_v1"
                    else:
                        self.model_name = model_tag
                    logger.info(f"Champion model loaded from {model_path.name} ({self.model_name}).")
                    break
                except Exception as exc:
                    logger.warning(f"Could not load {model_path.name}: {exc}")
                    self.model = None

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

        frames: List[pd.DataFrame] = []
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

    def get_available_months(self) -> List[str]:
        if self.available_months:
            return self.available_months
        return ["2025-02", "2025-03", "2025-09", "2025-10", "2025-11", "2025-12"]

    # ----------------------------------------------------- feature vector
    def _resolve_month(self, county: str, requested_month: Optional[str] = None) -> str:
        c_name = normalize_county_name(county)
        hist = self.county_history.get(c_name)
        if hist is not None and not hist.empty and "year_month" in hist.columns:
            available = set(hist["year_month"].astype(str))
            if requested_month and str(requested_month) in available:
                return str(requested_month)
            if DEFAULT_ACTIVE_MONTH in available:
                return DEFAULT_ACTIVE_MONTH
            return str(hist["year_month"].iloc[-1])
        return requested_month or DEFAULT_ACTIVE_MONTH

    def _build_vector(self, county: str, month_key: Optional[str] = None) -> Optional[Dict[str, float]]:
        c_name = normalize_county_name(county)
        hist = self.county_history.get(c_name)
        resolved_month = self._resolve_month(c_name, month_key)

        if hist is not None and not hist.empty:
            sub = hist[hist["year_month"] == resolved_month]
            row = sub.iloc[-1] if not sub.empty else hist.iloc[-1]
            vec = {}
            for col in self.feature_cols:
                if col in row.index and pd.notna(row[col]):
                    vec[col] = round(float(row[col]), 6)
            if len(vec) == len(self.feature_cols):
                return vec

        stats = self.ndvi_stats.get(c_name)
        if stats is None or not self.feature_cols:
            return None

        month_num = 2
        if resolved_month and "-" in str(resolved_month):
            try:
                month_num = int(str(resolved_month).split("-")[1])
            except ValueError:
                month_num = 2

        ndvi_mean = stats["mean"]
        ndvi_std = stats["std"]
        is_arid = ndvi_mean < 0.45
        temp_c = 29.5 if is_arid else 22.0
        rain_mm = 18.0 if is_arid else 78.0
        soil_m = 0.14 if is_arid else 0.31
        soil_def = max(0.0, 0.45 - soil_m)
        forage_dry = round(0.5 * soil_def * (temp_c / 25.0), 4)

        vec = {
            "month_sin": round(math.sin(2 * math.pi * month_num / 12.0), 6),
            "month_cos": round(math.cos(2 * math.pi * month_num / 12.0), 6),
            "ndvi_lag1": round(ndvi_mean, 6),
            "ndvi_lag3": round(ndvi_mean, 6),
            "ndvi_roll3_mean": round(ndvi_mean, 6),
            "ndvi_roll3_std": round(ndvi_std * 0.5, 6),
            "ndvi_anomaly": 0.0,
            "temp_mean_c": temp_c,
            "rainfall_mm": rain_mm,
            "soil_moisture": soil_m,
            "rainfall_anomaly": -20.0 if is_arid else 0.0,
            "rain_3m_sum": round(rain_mm * 3.0, 4),
            "forage_dryness_index": forage_dry,
            "farming_ratio": 0.45 if is_arid else 0.68,
            "livestock_share": 0.65 if is_arid else 0.38,
            "irrigation_ratio": 0.04 if is_arid else 0.08,
        }
        return vec

    def _rule_features(self, county: str, month_key: Optional[str]) -> Dict[str, float]:
        c_name = normalize_county_name(county)
        vec = self._build_vector(c_name, month_key)
        if vec is not None:
            rain_mm = float(vec.get("rainfall_mm", 60.0))
            rain_anom_mm = float(vec.get("rainfall_anomaly", 0.0))
            rain_base = max(rain_mm - rain_anom_mm, 1.0)
            rain_pct = 100.0 * rain_anom_mm / rain_base
            soil_def = max(0.0, (0.45 - float(vec.get("soil_moisture", 0.27))) * 100.0)
            return {
                "rainfall_anomaly_30d": round(rain_pct, 2),
                "ndvi_pasture_index": round(float(vec.get("ndvi_lag1", 0.5)), 4),
                "temp_max_avg": round(float(vec.get("temp_mean_c", 25.0)), 2),
                "soil_moisture_deficit": round(soil_def, 2),
            }
        return {
            "rainfall_anomaly_30d": 0.0,
            "ndvi_pasture_index": 0.5,
            "temp_max_avg": 28.0,
            "soil_moisture_deficit": 40.0,
        }

    # --------------------------------------------------- TreeSHAP & scoring
    def _compute_shap(
        self, vector: Dict[str, float]
    ) -> Tuple[List[Dict[str, Any]], float]:
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
            if hasattr(self.model, "booster_"):
                contrib = self.model.booster_.predict(x, pred_contrib=True)[0]
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
            logger.warning(f"SHAP computation fallback triggered: {exc}")

        items: List[Dict[str, Any]] = []
        for col, s_val in zip(self.feature_cols, shap_vals):
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

    def get_global_importance(self) -> List[Dict[str, Any]]:
        """Return global feature importances across all 16 features of the LightGBM Champion model."""
        if self.model is None or not hasattr(self.model, "feature_importances_"):
            return []
        raw_imp = np.asarray(self.model.feature_importances_, dtype=float)
        total = float(raw_imp.sum()) or 1.0
        items = []
        for col, imp in zip(self.feature_cols, raw_imp):
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
        shap_items: List[Dict[str, Any]],
        vector: Dict[str, float],
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
        vector: Optional[Dict[str, float]],
        shap_items: List[Dict[str, Any]],
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
            f"- **Model Verdict:** The LightGBM Champion Model predicts a **{score}/100 ({level})** drought and forage risk.\n"
            f"- **What the Field Numbers Show:** Monthly rainfall is **{rain_mm:.1f} mm** ({rain_word}), "
            f"land surface temperature is **{temp_c:.1f} °C**, root-zone soil moisture is **{soil_m:.2f} m³/m³**, "
            f"pasture greenness (NDVI) is **{ndvi_l1:.2f}**, and the **Forage Dryness Index** is **{fdi:.2f}**.\n"
            f"- **Why the Model Decided This (SHAP Explainability):** {why_text}\n"
            f"- **Recommended Action:** {RECOMMENDATIONS.get(level, '')}{_focus_advice(focus, level)}"
        )

    def _score(
        self,
        county: str,
        month_key: Optional[str],
        vector: Optional[Dict[str, float]],
        rule_feats: Dict[str, float],
    ) -> Tuple[int, str, str, str, List[Dict[str, Any]]]:
        """Returns (score, level, driver, model_used, shap_contributions)."""
        if self.model is not None and vector is not None and self.feature_cols:
            try:
                x = pd.DataFrame(
                    [[float(vector[c]) for c in self.feature_cols]],
                    columns=self.feature_cols,
                )
                proba = float(self.model.predict_proba(x)[0][1])
                score = int(min(100, max(0, round(proba * 100))))
                shap_items, _ = self._compute_shap(vector)
                driver = self._driver_from_shap(score, shap_items, vector)
                return score, get_risk_level(score), driver, self.model_name, shap_items
            except Exception as exc:
                logger.warning(f"ML scoring failed for {county}: {exc}")
        comps = _rule_components(rule_feats)
        score = compute_score(rule_feats)
        return score, get_risk_level(score), _main_driver(comps), "rule_based", []

    # ----------------------------------------------------------- public API
    def _get_county(self, db: Optional[Session], name: str) -> models.County:
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
        db: Optional[Session],
        county: models.County,
        focus: Optional[str] = None,
        persist: bool = False,
        month: Optional[str] = None,
        include_shap: bool = True,
    ) -> dict:
        focus = focus or county.primary_focus or "crops"
        month_key = self._resolve_month(county.name, month)
        vector = self._build_vector(county.name, month_key)
        rule_feats = self._rule_features(county.name, month_key)
        score, level, driver, used, shap_items = self._score(
            county.name, month_key, vector, rule_feats
        )
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
        if persist and db is not None and getattr(county, "id", 0):
            self._persist(db, county, out)
        return out

    def predict(
        self,
        db: Optional[Session],
        county_name: str,
        focus: Optional[str] = None,
        persist: bool = True,
        month: Optional[str] = None,
    ) -> dict:
        county = self._get_county(db, county_name)
        return self.predict_for_county_obj(
            db, county, focus=focus, persist=persist, month=month
        )

    def explain(
        self,
        db: Optional[Session],
        county_name: str,
        month: Optional[str] = None,
    ) -> dict:
        """Return full local TreeSHAP waterfall + global feature importance for a county."""
        county = self._get_county(db, county_name)
        month_key = self._resolve_month(county.name, month)
        vector = self._build_vector(county.name, month_key) or {}
        rule_feats = self._rule_features(county.name, month_key)
        score, level, driver, _, shap_items = self._score(
            county.name, month_key, vector, rule_feats
        )
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
            "feature_ranges": FEATURE_RANGES,
        }

    def forecast_future(
        self,
        db: Optional[Session],
        county_name: str,
        target_month: int = 2,
        focus: Optional[str] = "combined",
        auto_derive_indices: bool = True,
        overrides: Optional[Dict[str, Optional[float]]] = None,
    ) -> dict:
        """
        Run a future forecast using explicit Champion Model feature sliders.
        Compares the county's baseline against the user-configured future feature vector.
        """
        county = self._get_county(db, county_name)
        focus_val = focus or county.primary_focus or "combined"
        base_month = self._resolve_month(county.name, None)
        base_vec = self._build_vector(county.name, base_month) or {}
        base_rule = self._rule_features(county.name, base_month)

        overrides = overrides or {}
        future_vec = dict(base_vec)

        # 1. Update seasonal cyclical features from target_month (1..12)
        m_num = max(1, min(12, int(target_month)))
        future_vec["month_sin"] = round(math.sin(2 * math.pi * m_num / 12.0), 6)
        future_vec["month_cos"] = round(math.cos(2 * math.pi * m_num / 12.0), 6)

        # 2. Apply any slider overrides provided by the user
        for col in self.feature_cols:
            if col in ("month_sin", "month_cos"):
                continue
            val = overrides.get(col)
            if val is not None:
                future_vec[col] = round(float(val), 6)

        # 3. If auto_derive_indices is enabled, keep linked agro-climatic indices consistent
        if auto_derive_indices and future_vec:
            stats = self.ndvi_stats.get(county.name, {"mean": 0.52, "std": 0.08})
            hist_rain = self.rain_clim.get(
                (county.name, m_num),
                float(base_vec.get("rainfall_mm", 65.0)) - float(base_vec.get("rainfall_anomaly", 0.0)),
            )
            if overrides.get("rainfall_anomaly") is None:
                future_vec["rainfall_anomaly"] = round(
                    float(future_vec.get("rainfall_mm", 65.0)) - hist_rain, 4
                )
            if overrides.get("ndvi_anomaly") is None:
                future_vec["ndvi_anomaly"] = round(
                    float(future_vec.get("ndvi_lag1", stats["mean"])) - stats["mean"], 6
                )
            if overrides.get("forage_dryness_index") is None:
                soil_def = max(0.0, 0.45 - float(future_vec.get("soil_moisture", 0.25)))
                ndvi_drop = max(
                    0.0, stats["mean"] - float(future_vec.get("ndvi_lag1", stats["mean"]))
                ) / (stats["std"] + 1e-6)
                temp_val = float(future_vec.get("temp_mean_c", 24.0))
                future_vec["forage_dryness_index"] = round(
                    0.5 * ndvi_drop + 0.5 * (soil_def * (temp_val / 25.0)), 4
                )

        future_rule = {
            "rainfall_anomaly_30d": float(future_vec.get("rainfall_anomaly", 0.0)),
            "ndvi_pasture_index": float(future_vec.get("ndvi_lag1", 0.5)),
            "temp_max_avg": float(future_vec.get("temp_mean_c", 25.0)),
            "soil_moisture_deficit": max(0.0, (0.45 - float(future_vec.get("soil_moisture", 0.25))) * 100.0),
        }

        b_score, b_level, b_driver, b_used, b_shap = self._score(
            county.name, base_month, base_vec, base_rule
        )
        f_month_label = f"2026-{m_num:02d} (Forecast)"
        f_score, f_level, f_driver, f_used, f_shap = self._score(
            county.name, f_month_label, future_vec, future_rule
        )

        b_rec = RECOMMENDATIONS[b_level] + _focus_advice(focus_val, b_level)
        f_rec = RECOMMENDATIONS[f_level] + _focus_advice(focus_val, f_level)

        b_plain = self.build_plain_explanation(
            county.name, base_month, b_score, b_level, base_vec, b_shap, focus=focus_val
        )
        f_plain = self.build_plain_explanation(
            county.name, f_month_label, f_score, f_level, future_vec, f_shap, focus=focus_val
        )

        baseline_out = {
            "county_name": county.name,
            "region": county.region,
            "focus": focus_val,
            "month": base_month,
            "risk_score": b_score,
            "risk_level": b_level,
            "main_driver": b_driver,
            "recommendation": b_rec,
            "model_used": b_used,
            "plain_summary": b_plain,
            "features": base_vec,
            "shap_contributions": b_shap,
        }
        forecast_out = {
            "county_name": county.name,
            "region": county.region,
            "focus": focus_val,
            "month": f_month_label,
            "risk_score": f_score,
            "risk_level": f_level,
            "main_driver": f_driver,
            "recommendation": f_rec,
            "model_used": f_used,
            "plain_summary": f_plain,
            "features": future_vec,
            "shap_contributions": f_shap,
        }
        delta = f_score - b_score
        narrative = (
            f"For {county.name} targeting month {f_month_label}, the LightGBM Champion Model projects a risk score of "
            f"{f_score}/100 ({f_level}), a {delta:+d} point shift from the {base_month} baseline ({b_score}/100, {b_level}). "
            f"Primary driver: {f_driver}."
        )
        return {
            "county_name": county.name,
            "region": county.region,
            "target_month": m_num,
            "baseline": baseline_out,
            "forecast": forecast_out,
            "score_delta": delta,
            "narrative": narrative,
            "gria_plain_analysis": f_plain,
        }

    def get_historical_series(self, county_name: str, months: int = 12) -> List[dict]:
        """Compute historical monthly risk trajectory and agro-climatic series from the 2015-2025 county matrix."""
        c_name = normalize_county_name(county_name)
        hist = self.county_history.get(c_name)
        if hist is None or hist.empty:
            return []
        tail_df = hist.tail(max(1, min(months, 132)))
        series: List[dict] = []
        for _, row in tail_df.iterrows():
            m_key = str(row.get("year_month", DEFAULT_ACTIVE_MONTH))
            vec = {
                col: float(row[col])
                for col in self.feature_cols
                if col in row.index and pd.notna(row[col])
            }
            rule_f = self._rule_features(c_name, m_key)
            score, level, _, _, _ = self._score(
                c_name,
                m_key,
                vec if len(vec) == len(self.feature_cols) else None,
                rule_f,
            )
            series.append({
                "date": m_key,
                "risk_score": score,
                "risk_level": level,
                "rainfall_mm": round(float(row.get("rainfall_mm", 0.0)), 2),
                "soil_moisture": round(float(row.get("soil_moisture", 0.0)), 4),
                "ndvi_lag1": round(float(row.get("ndvi_lag1", 0.0)), 4),
                "forage_dryness_index": round(float(row.get("forage_dryness_index", 0.0)), 4),
                "temp_mean_c": round(float(row.get("temp_mean_c", 0.0)), 2),
            })
        return series

    def scenario(
        self,
        db: Optional[Session],
        county_name: str,
        rain_pct: float,
        temp_c: float,
        ndvi_shock: float,
        month: Optional[str] = None,
    ) -> dict:
        county = self._get_county(db, county_name)
        month_key = self._resolve_month(county.name, month)
        base_vec = self._build_vector(county.name, month_key)
        base_rule = self._rule_features(county.name, month_key)

        sc_rule = dict(base_rule)
        sc_rule["rainfall_anomaly_30d"] = base_rule["rainfall_anomaly_30d"] + rain_pct
        sc_rule["temp_max_avg"] = base_rule["temp_max_avg"] + temp_c
        sc_rule["ndvi_pasture_index"] = max(
            0.05, min(0.95, base_rule["ndvi_pasture_index"] + ndvi_shock)
        )

        sc_vec = None
        if base_vec is not None:
            sc_vec = dict(base_vec)
            factor = max(0.0, 1.0 + rain_pct / 100.0)
            old_rain = float(base_vec["rainfall_mm"])
            old_anom = float(base_vec["rainfall_anomaly"])
            hist_rain_mean = old_rain - old_anom

            new_rain = round(old_rain * factor, 4)
            sc_vec["rainfall_mm"] = new_rain
            sc_vec["rain_3m_sum"] = round(float(base_vec["rain_3m_sum"]) * factor, 4)
            sc_vec["rainfall_anomaly"] = round(new_rain - hist_rain_mean, 4)

            new_temp = round(float(base_vec["temp_mean_c"]) + temp_c, 4)
            sc_vec["temp_mean_c"] = new_temp

            stats = self.ndvi_stats.get(county.name, {"mean": 0.5, "std": 0.08})
            new_lag1 = max(0.05, min(0.95, float(base_vec["ndvi_lag1"]) + ndvi_shock))
            sc_vec["ndvi_lag1"] = round(new_lag1, 6)
            sc_vec["ndvi_lag3"] = round(
                max(0.05, min(0.95, float(base_vec["ndvi_lag3"]) + ndvi_shock * 0.5)),
                6,
            )
            sc_vec["ndvi_roll3_mean"] = round(
                max(0.05, min(0.95, float(base_vec["ndvi_roll3_mean"]) + ndvi_shock * 0.7)),
                6,
            )
            sc_vec["ndvi_anomaly"] = round(new_lag1 - stats["mean"], 6)

            soil_m = max(
                0.03,
                min(0.47, float(base_vec["soil_moisture"]) * (0.5 + 0.5 * factor) - 0.008 * temp_c),
            )
            sc_vec["soil_moisture"] = round(soil_m, 4)
            soil_def = max(0.0, 0.45 - soil_m)
            ndvi_drop = max(0.0, stats["mean"] - new_lag1) / (stats["std"] + 1e-6)
            sc_vec["forage_dryness_index"] = round(
                0.5 * ndvi_drop + 0.5 * (soil_def * (new_temp / 25.0)),
                4,
            )

        o_score, o_level, o_driver, o_used, o_shap = self._score(
            county.name, month_key, base_vec, base_rule
        )
        s_score, s_level, s_driver, s_used, s_shap = self._score(
            county.name, month_key, sc_vec, sc_rule
        )
        rec_o = RECOMMENDATIONS[o_level] + _focus_advice(county.primary_focus, o_level)
        rec_s = RECOMMENDATIONS[s_level] + _focus_advice(county.primary_focus, s_level)

        original = {
            "county_name": county.name,
            "region": county.region,
            "focus": county.primary_focus,
            "month": month_key,
            "risk_score": o_score,
            "risk_level": o_level,
            "main_driver": o_driver,
            "recommendation": rec_o,
            "model_used": o_used,
            "plain_summary": self.build_plain_explanation(
                county.name, month_key, o_score, o_level, base_vec, o_shap
            ),
            "features": base_vec,
            "shap_contributions": o_shap,
        }
        scenario_out = {
            "county_name": county.name,
            "region": county.region,
            "focus": county.primary_focus,
            "month": month_key,
            "risk_score": s_score,
            "risk_level": s_level,
            "main_driver": s_driver,
            "recommendation": rec_s,
            "model_used": s_used,
            "plain_summary": self.build_plain_explanation(
                county.name, month_key, s_score, s_level, sc_vec, s_shap
            ),
            "features": sc_vec,
            "shap_contributions": s_shap,
        }
        narrative = (
            f"Applying {rain_pct:+.0f}% rainfall, {temp_c:+.1f}°C temperature, and {ndvi_shock:+.2f} NDVI shift "
            f"moves {county.name} from {o_level} ({o_score}/100) to {s_level} ({s_score}/100). "
            f"Top driver under shock: {s_driver}."
        )
        return {
            "county_name": county.name,
            "original": original,
            "scenario": scenario_out,
            "score_delta": s_score - o_score,
            "narrative": narrative,
        }

    def _persist(self, db: Session, county: models.County, pred: dict) -> None:
        try:
            db.add(models.Prediction(
                county_id=county.id,
                risk_score=pred["risk_score"],
                risk_level=pred["risk_level"],
                main_driver=pred["main_driver"],
                recommendation=pred["recommendation"],
                focus=pred["focus"],
            ))
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"Prediction persist skipped: {exc}")


@lru_cache()
def get_engine() -> PredictionEngine:
    return PredictionEngine()


def predict(
    db: Optional[Session],
    county_name: str,
    focus: Optional[str] = None,
    persist: bool = True,
    month: Optional[str] = None,
) -> dict:
    """Module-level convenience wrapper used by Gria AI agent tools and routers."""
    return get_engine().predict(db, county_name, focus=focus, persist=persist, month=month)


def quick_risk(county_name: str, month: Optional[str] = None) -> Tuple[int, str]:
    """Quickly get risk score and level for a county without requiring DB persistence."""
    from database.connection import SessionLocal

    db = SessionLocal() if SessionLocal is not None else None
    try:
        result = get_engine().predict(db, county_name, persist=False, month=month)
        return result["risk_score"], result["risk_level"]
    finally:
        if db is not None:
            db.close()
