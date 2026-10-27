"""
AgriShield Frontend API Client (shared/api_client.py).

Communicates with the FastAPI backend (`apps/backend/main.py`) across all
endpoints (`/predictions/*`, `/predictions/forecast`, `/predictions/explain`,
`/gria/chat`, `/uploads/file`) and includes a resilient local ML fallback
powered by the same LightGBM Champion artifact (`lightgbm_agrishield_v1.joblib`)
and TreeSHAP engine when the HTTP backend is temporarily unreachable.
"""
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import requests

from shared.constants import API_BASE_URL, API_TIMEOUT_SECONDS, KENYA_COUNTIES
from shared.kenya_counties import COUNTY_COORDINATES, normalize_county_name
from shared.types import (
    BatchResult,
    CompareResult,
    ExplainResult,
    FutureForecastResult,
    GriaResponse,
    HistoryResult,
    PredictionResult,
    RegionResult,
    ScenarioResult,
    UploadResult,
)

logger = logging.getLogger("agrishield.frontend")

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parent.parent
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend"
ARTIFACT_DIR = BACKEND_DIR / "ml_artifacts"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data_pipeline" / "data" / "processed"

# Ensure backend services/agents can be reused seamlessly in embedded offline mode
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _get_backend_engine():
    from services.prediction_service import get_engine
    return get_engine()


class AgriShieldClient:
    """HTTP client for the AgriShield FastAPI service with embedded LightGBM + TreeSHAP fallback."""

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None) -> None:
        self.base_url = (base_url or os.getenv("AGRISHIELD_API_URL") or API_BASE_URL).rstrip("/")
        self.token = token or os.getenv("AGRISHIELD_API_TOKEN")
        self.last_mode: str = "api"

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def check_health(self) -> Dict[str, Any]:
        root_url = self.base_url.replace("/api/v1", "")
        try:
            resp = requests.get(f"{root_url}/health", timeout=3)
            if resp.ok:
                self.last_mode = "api"
                return resp.json()
        except Exception:
            pass
        self.last_mode = "embedded_ml"
        eng = _get_backend_engine()
        return {
            "status": "embedded_ml",
            "model_loaded": eng.model is not None,
            "model_name": eng.model_name,
        }

    def get_available_months(self) -> List[str]:
        try:
            resp = requests.get(
                f"{self.base_url}/predictions/months",
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return list(resp.json())
        except Exception:
            pass
        self.last_mode = "embedded_ml"
        return _get_backend_engine().get_available_months()

    def get_prediction(
        self,
        county_name: str,
        focus: str = "combined",
        month: Optional[str] = None,
    ) -> PredictionResult:
        canonical = normalize_county_name(county_name)
        try:
            payload: Dict[str, Any] = {"county_name": canonical, "focus": focus}
            if month:
                payload["month"] = month
            resp = requests.post(
                f"{self.base_url}/predictions/crop-yield",
                json=payload,
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return PredictionResult.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /predictions/crop-yield fallback: {exc}")
        self.last_mode = "embedded_ml"
        return PredictionResult.from_dict(
            _get_backend_engine().predict(
                None, canonical, focus=focus, persist=False, month=month
            )
        )

    def explain_county(
        self,
        county_name: str,
        month: Optional[str] = None,
    ) -> ExplainResult:
        canonical = normalize_county_name(county_name)
        try:
            params: Dict[str, Any] = {"county_name": canonical}
            if month:
                params["month"] = month
            resp = requests.get(
                f"{self.base_url}/predictions/explain",
                params=params,
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return ExplainResult.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /predictions/explain fallback: {exc}")
        self.last_mode = "embedded_ml"
        return ExplainResult.from_dict(
            _get_backend_engine().explain(None, canonical, month=month)
        )

    def forecast_future(
        self,
        county_name: str,
        target_month: int = 2,
        focus: str = "combined",
        auto_derive_indices: bool = True,
        overrides: Optional[Dict[str, Optional[float]]] = None,
    ) -> FutureForecastResult:
        canonical = normalize_county_name(county_name)
        overrides = overrides or {}
        try:
            payload: Dict[str, Any] = {
                "county_name": canonical,
                "target_month": int(target_month),
                "focus": focus,
                "auto_derive_indices": bool(auto_derive_indices),
                **{k: v for k, v in overrides.items() if v is not None},
            }
            resp = requests.post(
                f"{self.base_url}/predictions/forecast",
                json=payload,
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return FutureForecastResult.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /predictions/forecast fallback: {exc}")
        self.last_mode = "embedded_ml"
        return FutureForecastResult.from_dict(
            _get_backend_engine().forecast_future(
                None,
                county_name=canonical,
                target_month=target_month,
                focus=focus,
                auto_derive_indices=auto_derive_indices,
                overrides=overrides,
            )
        )

    def get_batch_predictions(self, month: Optional[str] = None) -> BatchResult:
        try:
            params = {"month": month} if month else {}
            resp = requests.get(
                f"{self.base_url}/predictions/batch",
                params=params,
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return BatchResult.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /predictions/batch fallback: {exc}")
        self.last_mode = "embedded_ml"
        eng = _get_backend_engine()
        preds = [
            eng.predict(None, c, persist=False, month=month)
            for c in KENYA_COUNTIES
        ]
        resolved_m = preds[0].get("month") if preds else (month or "2025-02")
        return BatchResult.from_dict({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "month": resolved_m,
            "county_count": len(preds),
            "counties": preds,
        })

    def get_history(self, county_name: str, months: int = 12) -> HistoryResult:
        canonical = normalize_county_name(county_name)
        try:
            resp = requests.get(
                f"{self.base_url}/predictions/history",
                params={"county_name": canonical, "months": months},
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                data = resp.json()
                if data.get("trend"):
                    self.last_mode = "api"
                    return HistoryResult.from_dict(data)
        except Exception as exc:
            logger.debug(f"API /predictions/history fallback: {exc}")
        self.last_mode = "embedded_ml"
        eng = _get_backend_engine()
        return HistoryResult.from_dict({
            "county_name": canonical,
            "months": months,
            "trend": eng.get_historical_series(canonical, months=months),
        })

    def run_scenario(
        self,
        county_name: str,
        rainfall_change_pct: float,
        temp_change_c: float,
        ndvi_shock: float,
        month: Optional[str] = None,
    ) -> ScenarioResult:
        canonical = normalize_county_name(county_name)
        try:
            payload: Dict[str, Any] = {
                "county_name": canonical,
                "rainfall_change_pct": rainfall_change_pct,
                "temp_change_c": temp_change_c,
                "ndvi_shock": ndvi_shock,
            }
            if month:
                payload["month"] = month
            resp = requests.post(
                f"{self.base_url}/predictions/scenario",
                json=payload,
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return ScenarioResult.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /predictions/scenario fallback: {exc}")
        self.last_mode = "embedded_ml"
        return ScenarioResult.from_dict(
            _get_backend_engine().scenario(
                None,
                canonical,
                rainfall_change_pct,
                temp_change_c,
                ndvi_shock,
                month=month,
            )
        )

    def compare_counties(
        self,
        counties: List[str],
        month: Optional[str] = None,
    ) -> CompareResult:
        canon_list = [normalize_county_name(c) for c in counties]
        try:
            payload: Dict[str, Any] = {"counties": canon_list}
            if month:
                payload["month"] = month
            resp = requests.post(
                f"{self.base_url}/predictions/compare",
                json=payload,
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return CompareResult.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /predictions/compare fallback: {exc}")
        self.last_mode = "embedded_ml"
        eng = _get_backend_engine()
        preds = [
            eng.predict(None, c, persist=False, month=month)
            for c in canon_list
        ]
        ranked = sorted(preds, key=lambda p: p["risk_score"], reverse=True)
        return CompareResult.from_dict({
            "counties": ranked,
            "highest_risk": ranked[0],
            "lowest_risk": ranked[-1],
        })

    def get_region_summary(
        self,
        region_name: str,
        month: Optional[str] = None,
    ) -> RegionResult:
        try:
            payload: Dict[str, Any] = {"region_name": region_name}
            if month:
                payload["month"] = month
            resp = requests.post(
                f"{self.base_url}/predictions/region",
                json=payload,
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return RegionResult.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /predictions/region fallback: {exc}")
        self.last_mode = "embedded_ml"
        eng = _get_backend_engine()
        matched = [
            name
            for name, meta in COUNTY_COORDINATES.items()
            if meta["region"].lower() == region_name.strip().lower()
        ] or ["Turkana"]
        preds = [
            eng.predict(None, c, persist=False, month=month)
            for c in sorted(matched)
        ]
        avg = round(sum(p["risk_score"] for p in preds) / len(preds), 1)
        lvl = (
            "SAFE"
            if avg < 25
            else "MODERATE"
            if avg < 50
            else "HIGH"
            if avg < 75
            else "CRITICAL"
        )
        return RegionResult.from_dict({
            "region_name": region_name,
            "county_count": len(preds),
            "average_risk": avg,
            "risk_level": lvl,
            "counties": preds,
        })

    def chat_with_gria(
        self,
        message: str,
        county_name: Optional[str] = None,
        month: Optional[str] = None,
        document_context: Optional[str] = None,
        document_name: Optional[str] = None,
    ) -> GriaResponse:
        canonical = normalize_county_name(county_name) if county_name else None
        try:
            resp = requests.post(
                f"{self.base_url}/gria/chat",
                json={
                    "message": message,
                    "county_name": canonical,
                    "month": month,
                    "document_context": document_context,
                    "document_name": document_name,
                },
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return GriaResponse.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /gria/chat fallback: {exc}")

        self.last_mode = "embedded_ml"
        from agents import gria_agent
        res = gria_agent.chat(
            message=message,
            county_name=canonical,
            month=month,
            document_context=document_context,
            document_name=document_name,
        )
        return GriaResponse.from_dict(res)

    def upload_file(
        self,
        file_name: str,
        file_bytes: bytes,
        mime_type: str = "application/octet-stream",
    ) -> UploadResult:
        try:
            resp = requests.post(
                f"{self.base_url}/uploads/file",
                files={"file": (file_name, file_bytes, mime_type)},
                headers=self._headers(),
                timeout=API_TIMEOUT_SECONDS,
            )
            if resp.ok:
                self.last_mode = "api"
                return UploadResult.from_dict(resp.json())
        except Exception as exc:
            logger.debug(f"API /uploads/file fallback: {exc}")

        self.last_mode = "embedded_ml"
        from agents import file_processor
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "csv"
        res = file_processor.process(file_name, ext, file_bytes)
        if hasattr(res, "model_dump"):
            return UploadResult.from_dict(res.model_dump())
        return UploadResult.from_dict(res.dict())


_default_client: Optional[AgriShieldClient] = None


def get_client() -> AgriShieldClient:
    global _default_client
    if _default_client is None:
        _default_client = AgriShieldClient()
    return _default_client


# ---------------------------------------------------------------------------
# Module-level functional helpers for direct HTTP contract & unit tests
# ---------------------------------------------------------------------------
def _raw_root_url() -> str:
    base = os.getenv("AGRISHIELD_API_URL", API_BASE_URL).rstrip("/")
    return base[:-7] if base.endswith("/api/v1") else base


def health() -> Dict[str, Any]:
    r = requests.request("GET", f"{_raw_root_url()}/api/v1/health", timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def auth_status() -> Dict[str, Any]:
    r = requests.request("GET", f"{_raw_root_url()}/api/v1/auth/status", timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def get_available_counties() -> List[str]:
    r = requests.request("GET", f"{_raw_root_url()}/api/v1/predictions/counties", timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return list(dict.fromkeys(r.json()))


def predict_county(county_name: str, focus: str = "combined", month: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"county_name": normalize_county_name(county_name), "focus": focus}
    if month:
        payload["month"] = month
    r = requests.request("POST", f"{_raw_root_url()}/api/v1/predictions/crop-yield", json=payload, timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def get_county_history(county_name: str, months: int = 12) -> Dict[str, Any]:
    from urllib.parse import quote
    canon = quote(normalize_county_name(county_name))
    r = requests.request("GET", f"{_raw_root_url()}/api/v1/predictions/history?county_name={canon}&months={months}", timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def compare_counties(counties: List[str], month: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"counties": [normalize_county_name(c) for c in counties]}
    if month:
        payload["month"] = month
    r = requests.request("POST", f"{_raw_root_url()}/api/v1/predictions/compare", json=payload, timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def get_region_aggregation(region_name: str, month: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"region_name": region_name}
    if month:
        payload["month"] = month
    r = requests.request("POST", f"{_raw_root_url()}/api/v1/predictions/region", json=payload, timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def scenario_analysis(
    county_name: str,
    rainfall_change_pct: float = 0.0,
    temp_change_c: float = 0.0,
    ndvi_shock: float = 0.0,
    month: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "county_name": normalize_county_name(county_name),
        "rainfall_change_pct": rainfall_change_pct,
        "temp_change_c": temp_change_c,
        "ndvi_shock": ndvi_shock,
    }
    if month:
        payload["month"] = month
    r = requests.request("POST", f"{_raw_root_url()}/api/v1/predictions/scenario", json=payload, timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def create_report(county_name: str, report_type: str = "combined", detailed: bool = True) -> Dict[str, Any]:
    r = requests.request(
        "POST",
        f"{_raw_root_url()}/api/v1/reports/create",
        json={"county_name": normalize_county_name(county_name), "report_type": report_type, "detailed": detailed},
        timeout=API_TIMEOUT_SECONDS,
    )
    r.raise_for_status()
    return r.json()


def list_reports(limit: int = 10) -> Dict[str, Any]:
    r = requests.request("GET", f"{_raw_root_url()}/api/v1/reports?limit={limit}", timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def download_report_pdf(report_id: int) -> bytes:
    r = requests.request("GET", f"{_raw_root_url()}/api/v1/reports/{report_id}/pdf", timeout=API_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.content


def chat_with_gria(
    message: str,
    county_name: Optional[str] = None,
    document_context: Optional[str] = None,
    document_name: Optional[str] = None,
) -> Dict[str, Any]:
    r = requests.request(
        "POST",
        f"{_raw_root_url()}/api/v1/gria/chat",
        json={
            "message": message,
            "county_name": normalize_county_name(county_name) if county_name else None,
            "document_context": document_context,
            "document_name": document_name,
        },
        timeout=API_TIMEOUT_SECONDS,
    )
    r.raise_for_status()
    return r.json()
