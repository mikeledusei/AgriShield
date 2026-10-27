"""
AgriShield Prediction Engine (2015–2025 Pipeline).
Primary scorer: LightGBM Champion (ml_artifacts/lightgbm_agrishield_v1.joblib).
Fallback scorer: transparent rule-based engine (always available).
All artifact loading is defensive: any missing/corrupt artifact degrades
gracefully to the rule engine — the API can never crash because of ML files.
"""
import json
import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    "SAFE": "Conditions are favorable. Continue routine monitoring and normal farming operations.",
    "MODERATE": "Early stress signals detected. Increase monitoring frequency and review water budgeting.",
    "HIGH": "Significant stress detected. Activate the county drought task force; prioritize water rationing and livestock feed support.",
    "CRITICAL": "Severe risk. Escalate to national emergency management; deploy relief feed, water trucking and cash transfers immediately.",
}


def _focus_advice(focus: Optional[str], level: str) -> str:
    if level not in ("HIGH", "CRITICAL"):
        return ""
    if (focus or "").lower() == "livestock":
        return " Prioritize emergency fodder, water points and veterinary outreach."
    if (focus or "").lower() in ("crop", "crops"):
        return " Fast-track drought-tolerant seed and smallholder irrigation support."
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
    """Loads ML artifacts once; serves predictions with graceful fallback."""

    def __init__(self) -> None:
        self.model = None
        self.model_name: str = "rule_based"
        self.scaler = None
        self.feature_cols: List[str] = []
        self.ndvi_stats: Dict[str, Dict[str, float]] = {}
        self.county_history: Dict[str, pd.DataFrame] = {}
        self.rain_clim: Dict[Tuple[str, int], float] = {}
        self._load_artifacts()

    # ------------------------------------------------------------ loading
    def _load_artifacts(self) -> None:
        # 1. Load feature contract
        cols_path = ARTIFACT_DIR / "feature_columns.json"
        if cols_path.exists():
            try:
                self.feature_cols = json.loads(cols_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to read feature_columns.json: {exc}")
                self.feature_cols = []

        # 2. Load scaler (optional for tree models, used when needed)
        scaler_path = ARTIFACT_DIR / "scaler.joblib"
        if scaler_path.exists():
            try:
                self.scaler = joblib.load(scaler_path)
            except Exception as exc:
                logger.warning(f"Failed to load scaler.joblib: {exc}")

        # 3. Load Champion Model (prefer LightGBM champion, fallback to XGBoost)
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

        # 4. Load county NDVI baseline statistics
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

        # 5. Load engineered county-month matrices (2015-2025) if available
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

    # ----------------------------------------------------- feature vector
    def _latest_month(self, county: str) -> str:
        c_name = normalize_county_name(county)
        hist = self.county_history.get(c_name)
        if hist is not None and not hist.empty and "year_month" in hist.columns:
            return str(hist["year_month"].iloc[-1])
        return "2025-12"

    def _build_vector(self, county: str, month_key: Optional[str] = None) -> Optional[Dict[str, float]]:
        c_name = normalize_county_name(county)
        hist = self.county_history.get(c_name)

        if hist is not None and not hist.empty:
            if month_key and "year_month" in hist.columns:
                sub = hist[hist["year_month"] == month_key]
                row = sub.iloc[-1] if not sub.empty else hist.iloc[-1]
            else:
                row = hist.iloc[-1]
            vec = {}
            for col in self.feature_cols:
                if col in row.index and pd.notna(row[col]):
                    vec[col] = float(row[col])
            if len(vec) == len(self.feature_cols):
                return vec

        # Fallback synthesis from county_ndvi_stats when processed CSVs are absent
        stats = self.ndvi_stats.get(c_name)
        if stats is None or not self.feature_cols:
            return None

        month_num = 12
        if month_key and "-" in str(month_key):
            try:
                month_num = int(str(month_key).split("-")[1])
            except ValueError:
                month_num = 12

        ndvi_mean = stats["mean"]
        ndvi_std = stats["std"]
        is_arid = ndvi_mean < 0.42
        temp_c = 28.5 if is_arid else 21.5
        rain_mm = 35.0 if is_arid else 95.0
        soil_m = 0.18 if is_arid else 0.34
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
            "rainfall_anomaly": 0.0,
            "rain_3m_sum": round(rain_mm * 3.0, 4),
            "forage_dryness_index": forage_dry,
            "farming_ratio": 0.45 if is_arid else 0.68,
            "livestock_share": 0.65 if is_arid else 0.38,
            "irrigation_ratio": 0.04 if is_arid else 0.08,
        }
        if any(c not in vec or pd.isna(vec.get(c)) for c in self.feature_cols):
            return None
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

    # ------------------------------------------------------------- scoring
    def _score(
        self,
        county: str,
        month_key: Optional[str],
        vector: Optional[Dict[str, float]],
        rule_feats: Dict[str, float],
    ) -> Tuple[int, str, str, str]:
        """Returns (score, level, driver, model_used)."""
        if self.model is not None and vector is not None and self.feature_cols:
            try:
                x = pd.DataFrame(
                    [[float(vector[c]) for c in self.feature_cols]],
                    columns=self.feature_cols,
                )
                proba = float(self.model.predict_proba(x)[0][1])
                score = int(min(100, max(0, round(proba * 100))))
                driver = self._ml_driver(vector)
                return score, get_risk_level(score), driver, self.model_name
            except Exception as exc:
                logger.warning(f"ML scoring failed for {county}: {exc}")
        comps = _rule_components(rule_feats)
        score = compute_score(rule_feats)
        return score, get_risk_level(score), _main_driver(comps), "rule_based"

    @staticmethod
    def _ml_driver(v: Dict[str, float]) -> str:
        if v.get("forage_dryness_index", 0.0) >= 0.45 or v.get("ndvi_anomaly", 0.0) <= -0.05:
            return "Vegetation & forage stress (NDVI / Forage Dryness Index)"
        if v.get("rainfall_anomaly", 0.0) <= -15.0:
            return "Rainfall deficit (30-Day Rainfall Anomaly)"
        if v.get("soil_moisture", 1.0) <= 0.20:
            return "Soil moisture deficit"
        if v.get("temp_mean_c", 0.0) >= 28.5:
            return "Heat stress"
        return "Favorable agro-climatic baseline"

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
    ) -> dict:
        focus = focus or county.primary_focus or "crops"
        month_key = self._latest_month(county.name)
        vector = self._build_vector(county.name, month_key)
        rule_feats = self._rule_features(county.name, month_key)
        score, level, driver, used = self._score(county.name, month_key, vector, rule_feats)
        rec = RECOMMENDATIONS[level] + _focus_advice(focus, level)
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
    ) -> dict:
        county = self._get_county(db, county_name)
        return self.predict_for_county_obj(db, county, focus=focus, persist=persist)

    def get_historical_series(self, county_name: str, months: int = 12) -> List[dict]:
        """Compute historical monthly risk trajectory from the 2015-2025 county matrix."""
        c_name = normalize_county_name(county_name)
        hist = self.county_history.get(c_name)
        if hist is None or hist.empty:
            return []
        tail_df = hist.tail(max(1, min(months, 120)))
        series: List[dict] = []
        for _, row in tail_df.iterrows():
            m_key = str(row.get("year_month", "2025-12"))
            vec = {col: float(row[col]) for col in self.feature_cols if col in row.index and pd.notna(row[col])}
            rule_f = self._rule_features(c_name, m_key)
            score, level, _, _ = self._score(
                c_name,
                m_key,
                vec if len(vec) == len(self.feature_cols) else None,
                rule_f,
            )
            series.append({
                "date": m_key,
                "risk_score": score,
                "risk_level": level,
            })
        return series

    def scenario(
        self,
        db: Optional[Session],
        county_name: str,
        rain_pct: float,
        temp_c: float,
        ndvi_shock: float,
    ) -> dict:
        county = self._get_county(db, county_name)
        month_key = self._latest_month(county.name)
        base_vec = self._build_vector(county.name, month_key)
        base_rule = self._rule_features(county.name, month_key)

        # Perturbed rule-based inputs
        sc_rule = dict(base_rule)
        sc_rule["rainfall_anomaly_30d"] = base_rule["rainfall_anomaly_30d"] + rain_pct
        sc_rule["temp_max_avg"] = base_rule["temp_max_avg"] + temp_c
        sc_rule["ndvi_pasture_index"] = max(0.05, min(0.95, base_rule["ndvi_pasture_index"] + ndvi_shock))

        # Perturbed 16-feature ML vector (aligned with Proposal Section 3.3.2)
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

            # Apply vegetation shock to lagged NDVI features and recompute Forage Dryness Index
            stats = self.ndvi_stats.get(county.name, {"mean": 0.5, "std": 0.08})
            new_lag1 = max(0.05, min(0.95, float(base_vec["ndvi_lag1"]) + ndvi_shock))
            sc_vec["ndvi_lag1"] = round(new_lag1, 6)
            sc_vec["ndvi_roll3_mean"] = round(
                max(0.05, min(0.95, float(base_vec["ndvi_roll3_mean"]) + ndvi_shock * 0.7)),
                6,
            )
            sc_vec["ndvi_anomaly"] = round(new_lag1 - stats["mean"], 6)

            soil_m = max(0.05, min(0.45, float(base_vec["soil_moisture"]) * (0.5 + 0.5 * factor)))
            sc_vec["soil_moisture"] = round(soil_m, 4)
            soil_def = max(0.0, 0.45 - soil_m)
            ndvi_drop = max(0.0, stats["mean"] - new_lag1) / (stats["std"] + 1e-6)
            sc_vec["forage_dryness_index"] = round(
                0.5 * ndvi_drop + 0.5 * (soil_def * (new_temp / 25.0)),
                4,
            )

        o_score, o_level, o_driver, o_used = self._score(county.name, month_key, base_vec, base_rule)
        s_score, s_level, s_driver, s_used = self._score(county.name, month_key, sc_vec, sc_rule)
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
        }
        narrative = (
            f"Applying {rain_pct:+.0f}% rainfall, {temp_c:+.1f}°C temperature, and {ndvi_shock:+.2f} NDVI shift "
            f"moves {county.name} from {o_level} ({o_score}) to {s_level} ({s_score})."
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
) -> dict:
    """Module-level convenience wrapper used by Gria AI agent tools and routers."""
    return get_engine().predict(db, county_name, focus=focus, persist=persist)


def quick_risk(county_name: str) -> Tuple[int, str]:
    """Quickly get risk score and level for a county without requiring DB persistence."""
    from database.connection import SessionLocal

    db = SessionLocal() if SessionLocal is not None else None
    try:
        result = get_engine().predict(db, county_name, persist=False)
        return result["risk_score"], result["risk_level"]
    finally:
        if db is not None:
            db.close()
