"""
AgriShield Prediction Engine.
Primary scorer: XGBoost champion (ml_artifacts/xgboost_agrishield_v1.joblib).
Fallback scorer: transparent rule-based engine (always available).
All artifact loading is defensive: any missing/corrupt artifact degrades
gracefully to the rule engine — the API can never crash because of ML files.
"""
import json
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from database import models

logger = logging.getLogger("agrishield")

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "ml_artifacts"


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
    return int(min(100, sum(_rule_components(f).values())))


def _main_driver(comps: Dict[str, float]) -> str:
    top = max(comps, key=comps.get)
    return top if comps[top] > 0 else "No dominant risk factor detected"


# ------------------------------------------------------------------ engine
class PredictionEngine:
    """Loads ML artifacts once; serves predictions with graceful fallback."""

    def __init__(self) -> None:
        self.model = None
        self.feature_cols: List[str] = []
        self.ndvi_stats: Dict[str, Dict[str, float]] = {}
        self.ndvi_hist: Dict[str, pd.DataFrame] = {}
        self.met_hist: Dict[str, pd.DataFrame] = {}
        self.rain_clim: Dict[tuple, float] = {}
        self.demo: Dict[str, Dict[str, float]] = {}
        self._load_artifacts()

    # ------------------------------------------------------------ loading
    def _load_artifacts(self) -> None:
        try:
            model_path = ARTIFACT_DIR / "xgboost_agrishield_v1.joblib"
            cols_path = ARTIFACT_DIR / "feature_columns.json"
            if model_path.exists() and cols_path.exists():
                self.model = joblib.load(model_path)
                self.feature_cols = json.loads(cols_path.read_text())
                logger.info(" Champion XGBoost model loaded.")
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Champion model unavailable ({exc}). Using rule-based engine.")
            self.model = None

        try:
            stats = pd.read_csv(ARTIFACT_DIR / "county_ndvi_stats.csv")
            self.ndvi_stats = {
                r.county: {"mean": float(r.ndvi_mean_train), "std": float(r.ndvi_std_train) or 1e-6}
                for r in stats.itertuples()
            }
        except Exception:
            self.ndvi_stats = {}

        try:
            ndvi = pd.read_csv(ARTIFACT_DIR / "NDVI_cleaned_FINAL.csv")
            self.ndvi_hist = {c: g.sort_values("month") for c, g in ndvi.groupby("county")}
        except Exception:
            self.ndvi_hist = {}

        try:
            met = pd.read_csv(ARTIFACT_DIR / "Metrological_Cleaned_Data_2_FINAL.csv")
            met["month_key"] = met["year"].astype(str) + "-" + met["month"].astype(int).astype(str).str.zfill(2)
            met = met.sort_values(["county", "month_key"])
            met["rain_3m_sum"] = met.groupby("county")["rainfall_mm"].transform(
                lambda s: s.rolling(3, min_periods=1).sum()
            )
            self.met_hist = {c: g for c, g in met.groupby("county")}
            clim = met.groupby(["county", "month"])["rainfall_mm"].mean().reset_index()
            self.rain_clim = {(r.county, int(r.month)): float(r.rainfall_mm) for r in clim.itertuples()}
        except Exception:
            self.met_hist, self.rain_clim = {}, {}

        try:
            demo = pd.read_csv(ARTIFACT_DIR / "Demographic_FINAL.csv")
            self.demo = {
                r.county: {
                    "livestock_share": float(r.livestock_production) / (float(r.crop_production) + float(r.livestock_production) + 1),
                    "irrigation_ratio": float(r.irrigation) / (float(r.farming) + 1),
                    "farming_ratio": float(r.farming) / (float(r.total) + 1),
                }
                for r in demo.itertuples()
            }
        except Exception:
            self.demo = {}

        mode = "XGBoost champion" if self.model else "rule-based engine"
        logger.info(f"⚡ Prediction engine ready ({mode}).")

    # ----------------------------------------------------- feature vector
    def _latest_month(self, county: str) -> Optional[str]:
        nh, mh = self.ndvi_hist.get(county), self.met_hist.get(county)
        if nh is None or mh is None:
            return None
        common = set(nh["month"]) & set(mh["month_key"])
        return max(common) if common else None

    def _build_vector(self, county: str, month_key: str) -> Optional[Dict[str, float]]:
        nh, mh = self.ndvi_hist.get(county), self.met_hist.get(county)
        if nh is None or mh is None:
            return None
        rrow = nh[nh["month"] == month_key]
        mrow = mh[mh["month_key"] == month_key]
        if rrow.empty or mrow.empty:
            return None
        r, m = rrow.iloc[0], mrow.iloc[0]
        stats = self.ndvi_stats.get(county, {"mean": float(r["ndvi_mean"]), "std": 1e-6})
        rain_mean = self.rain_clim.get((county, int(m["month"])), float(m["rainfall_mm"]))
        rainfall_anomaly = (float(m["rainfall_mm"]) - rain_mean) / (rain_mean + 1e-6)
        ndvi_anomaly = float(r["ndvi_mean"]) - stats["mean"]
        d = self.demo.get(county, {"livestock_share": 0.5, "irrigation_ratio": 0.05, "farming_ratio": 0.5})
        vec = {
            "month_sin": float(r["month_sin"]), "month_cos": float(r["month_cos"]),
            "ndvi_lag1": float(r["ndvi_lag1"]), "ndvi_lag3": float(r["ndvi_lag3"]),
            "ndvi_roll3_mean": float(r["ndvi_roll3_mean"]), "ndvi_roll3_std": float(r["ndvi_roll3_std"]),
            "ndvi_anomaly": ndvi_anomaly, "ndvi_mom_change": float(r["ndvi_mom_change"]),
            "ndvi_zscore": ndvi_anomaly / stats["std"],
            "temp_mean_c": float(m["temp_mean_c"]), "rainfall_mm": float(m["rainfall_mm"]),
            "soil_moisture": float(m["soil_moisture"]),
            "rainfall_anomaly": rainfall_anomaly,
            "rain_3m_sum": float(m["rain_3m_sum"]),
            "rain_ndvi_sync": rainfall_anomaly * ndvi_anomaly,
            **d,
        }
        if any(pd.isna(vec.get(c)) for c in self.feature_cols):
            return None
        return vec

    def _rule_features(self, county: str, month_key: Optional[str]) -> Dict[str, float]:
        if month_key and county in self.ndvi_hist and county in self.met_hist:
            r = self.ndvi_hist[county]
            m = self.met_hist[county]
            rr, mm = r[r["month"] == month_key], m[m["month_key"] == month_key]
            if not rr.empty and not mm.empty:
                rv, mv = rr.iloc[0], mm.iloc[0]
                rain_mean = self.rain_clim.get((county, int(mv["month"])), float(mv["rainfall_mm"]))
                return {
                    "rainfall_anomaly_30d": 100 * (float(mv["rainfall_mm"]) - rain_mean) / (rain_mean + 1e-6),
                    "ndvi_pasture_index": float(rv["ndvi_mean"]),
                    "temp_max_avg": float(mv["temp_mean_c"]),
                    "soil_moisture_deficit": max(0.0, (0.45 - float(mv["soil_moisture"])) * 100),
                }
        return {"rainfall_anomaly_30d": 0.0, "ndvi_pasture_index": 0.5,
                "temp_max_avg": 28.0, "soil_moisture_deficit": 40.0}

    # ------------------------------------------------------------- scoring
    def _score(self, county: str, month_key: Optional[str],
               vector: Optional[Dict[str, float]], rule_feats: Dict[str, float]):
        """Returns (score, level, driver, model_used)."""
        if self.model is not None and vector is not None:
            try:
                x = pd.DataFrame([[vector[c] for c in self.feature_cols]], columns=self.feature_cols)
                proba = float(self.model.predict_proba(x)[0][1])
                score = int(round(proba * 100))
                driver = self._ml_driver(vector)
                return score, get_risk_level(score), driver, "xgboost_v1"
            except Exception as exc:
                logger.warning(f"ML scoring failed for {county}: {exc}")
        comps = _rule_components(rule_feats)
        score = compute_score(rule_feats)
        return score, get_risk_level(score), _main_driver(comps), "rule_based"

    @staticmethod
    def _ml_driver(v: Dict[str, float]) -> str:
        if v.get("ndvi_zscore", 0) <= -1.0:
            return "Vegetation stress (NDVI)"
        if v.get("rainfall_anomaly", 0) <= -0.3:
            return "Rainfall deficit"
        if v.get("soil_moisture", 1) <= 0.2:
            return "Soil moisture deficit"
        if v.get("temp_mean_c", 0) >= 29.0:
            return "Heat stress"
        return "No dominant risk factor detected"

    # ----------------------------------------------------------- public API
    def _get_county(self, db: Session, name: str) -> models.County:
        county = db.query(models.County).filter(models.County.name.ilike(name.strip())).first()
        if county is None:
            raise CountyNotFoundError(f"County '{name}' not found.")
        return county

    def predict(self, db: Session, county_name: str, focus: Optional[str] = None,
                persist: bool = True) -> dict:
        county = self._get_county(db, county_name)
        focus = focus or county.primary_focus
        month_key = self._latest_month(county.name)
        vector = self._build_vector(county.name, month_key) if month_key else None
        rule_feats = self._rule_features(county.name, month_key)
        score, level, driver, used = self._score(county.name, month_key, vector, rule_feats)
        rec = RECOMMENDATIONS[level] + _focus_advice(focus, level)
        out = {
            "county_name": county.name, "region": county.region, "focus": focus,
            "month": month_key, "risk_score": score, "risk_level": level,
            "main_driver": driver, "recommendation": rec, "model_used": used,
        }
        if persist:
            self._persist(db, county, out)
        return out

    def scenario(self, db: Session, county_name: str, rain_pct: float,
                 temp_c: float, ndvi_shock: float) -> dict:
        county = self._get_county(db, county_name)
        month_key = self._latest_month(county.name)
        base_vec = self._build_vector(county.name, month_key) if month_key else None
        base_rule = self._rule_features(county.name, month_key)

        # Perturbed inputs
        sc_rule = dict(base_rule)
        sc_rule["rainfall_anomaly_30d"] = base_rule["rainfall_anomaly_30d"] + rain_pct
        sc_rule["temp_max_avg"] = base_rule["temp_max_avg"] + temp_c
        sc_vec = None
        if base_vec is not None:
            sc_vec = dict(base_vec)
            factor = 1.0 + rain_pct / 100.0
            sc_vec["rainfall_mm"] = base_vec["rainfall_mm"] * factor
            sc_vec["rain_3m_sum"] = base_vec["rain_3m_sum"] * factor
            sc_vec["temp_mean_c"] = base_vec["temp_mean_c"] + temp_c
            rain_mean = base_vec["rainfall_mm"] / factor if factor else base_vec["rainfall_mm"]
            sc_vec["rainfall_anomaly"] = (sc_vec["rainfall_mm"] - rain_mean) / (rain_mean + 1e-6)
            ndvi_new = (base_vec["ndvi_anomaly"] + ndvi_shock)
            sc_vec["ndvi_anomaly"] = ndvi_new
            sc_vec["ndvi_zscore"] = base_vec["ndvi_zscore"] + ndvi_shock / 0.05
            sc_vec["rain_ndvi_sync"] = sc_vec["rainfall_anomaly"] * ndvi_new

        o_score, o_level, o_driver, o_used = self._score(county.name, month_key, base_vec, base_rule)
        s_score, s_level, s_driver, s_used = self._score(county.name, month_key, sc_vec, sc_rule)
        rec_o = RECOMMENDATIONS[o_level] + _focus_advice(county.primary_focus, o_level)
        rec_s = RECOMMENDATIONS[s_level] + _focus_advice(county.primary_focus, s_level)

        original = {"county_name": county.name, "region": county.region, "focus": county.primary_focus,
                    "month": month_key, "risk_score": o_score, "risk_level": o_level,
                    "main_driver": o_driver, "recommendation": rec_o, "model_used": o_used}
        scenario = {"county_name": county.name, "region": county.region, "focus": county.primary_focus,
                    "month": month_key, "risk_score": s_score, "risk_level": s_level,
                    "main_driver": s_driver, "recommendation": rec_s, "model_used": s_used}
        narrative = (f"Applying {rain_pct:+.0f}% rainfall and {temp_c:+.1f}°C temperature shift "
                     f"moves {county.name} from {o_level} ({o_score}) to {s_level} ({s_score}).")
        return {"county_name": county.name, "original": original, "scenario": scenario,
                "score_delta": s_score - o_score, "narrative": narrative}

    def _persist(self, db: Session, county: models.County, pred: dict) -> None:
        try:
            db.add(models.Prediction(
                county_id=county.id, risk_score=pred["risk_score"], risk_level=pred["risk_level"],
                main_driver=pred["main_driver"], recommendation=pred["recommendation"],
                focus=pred["focus"],
            ))
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"Prediction persist skipped: {exc}")


@lru_cache()
def get_engine() -> PredictionEngine:
    return PredictionEngine()