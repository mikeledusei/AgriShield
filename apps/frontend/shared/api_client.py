"""Typed Backend API client for the AgriShield Streamlit frontend."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests
import streamlit as st

from shared.kenya_counties import normalize_county_name
from shared.types import (
    BatchResponse,
    CompareResponse,
    GriaChatResponse,
    HealthResponse,
    HistoryResponse,
    PredictionOut,
    RegionResponse,
    ReportListResponse,
    ReportOut,
    ScenarioResponse,
    UploadResponse,
)

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def _backend_url() -> str:
    backend_url = os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL)
    try:
        backend_url = st.secrets.get("BACKEND_URL", backend_url)
    except Exception:
        pass
    return str(backend_url).rstrip("/")


def _auth_headers(include_json: bool = True) -> dict[str, str]:
    headers: dict[str, str] = {}
    if include_json:
        headers["Content-Type"] = "application/json"

    api_key = os.getenv("BACKEND_API_KEY", "")
    try:
        api_key = st.secrets.get("BACKEND_API_KEY", api_key)
    except Exception:
        pass
    if api_key:
        headers["X-API-Key"] = str(api_key)

    try:
        token = st.session_state.get("auth_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    except Exception:
        pass

    return headers


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    url = f"{_backend_url()}{path}"
    kwargs.setdefault("timeout", 30)
    if "headers" not in kwargs:
        include_json = (
            "json" not in kwargs
            and "data" not in kwargs
            and kwargs.get("files") is None
        )
        kwargs["headers"] = _auth_headers(include_json=include_json)
    return requests.request(method, url, **kwargs)


def health() -> HealthResponse:
    response = _request("GET", "/api/v1/health", timeout=8)
    response.raise_for_status()
    return response.json()


def auth_status() -> dict[str, str]:
    response = _request("GET", "/api/v1/auth/status", timeout=8)
    response.raise_for_status()
    return response.json()


def root_info() -> dict[str, Any]:
    response = _request("GET", "/", timeout=8)
    response.raise_for_status()
    return response.json()


def get_available_counties() -> list[str]:
    response = _request("GET", "/api/v1/predictions/counties")
    response.raise_for_status()
    return [normalize_county_name(c) for c in response.json() if c]


def get_batch_predictions() -> BatchResponse:
    response = _request("GET", "/api/v1/predictions/batch")
    response.raise_for_status()
    return response.json()


def predict_county(county_name: str, focus: str = "crops") -> PredictionOut:
    canonical = normalize_county_name(county_name)
    response = _request(
        "POST",
        "/api/v1/predictions/crop-yield",
        json={"county_name": canonical, "focus": focus},
    )
    response.raise_for_status()
    return response.json()


def get_county_history(county_name: str, months: int = 12) -> HistoryResponse:
    canonical = normalize_county_name(county_name)
    encoded_county = quote(canonical, safe="")
    response = _request(
        "GET",
        f"/api/v1/predictions/history?county_name={encoded_county}&months={int(months)}",
    )
    response.raise_for_status()
    return response.json()


def compare_counties(counties: list[str]) -> CompareResponse:
    canonical_list = [normalize_county_name(c) for c in counties if c]
    response = _request(
        "POST",
        "/api/v1/predictions/compare",
        json={"counties": canonical_list},
    )
    response.raise_for_status()
    return response.json()


def get_region_aggregation(region_name: str) -> RegionResponse:
    response = _request(
        "POST",
        "/api/v1/predictions/region",
        json={"region_name": region_name.strip()},
    )
    response.raise_for_status()
    return response.json()


def scenario_analysis(
    county_name: str,
    rainfall_change_pct: float = 0.0,
    temp_change_c: float = 0.0,
    ndvi_shock: float = 0.0,
) -> ScenarioResponse:
    canonical = normalize_county_name(county_name)
    response = _request(
        "POST",
        "/api/v1/predictions/scenario",
        json={
            "county_name": canonical,
            "rainfall_change_pct": float(rainfall_change_pct),
            "temp_change_c": float(temp_change_c),
            "ndvi_shock": float(ndvi_shock),
        },
    )
    response.raise_for_status()
    return response.json()


def create_report(
    county_name: str,
    report_type: str = "combined",
    detailed: bool = False,
) -> ReportOut:
    canonical = normalize_county_name(county_name)
    response = _request(
        "POST",
        "/api/v1/reports/create",
        json={
            "county_name": canonical,
            "report_type": report_type,
            "detailed": bool(detailed),
        },
    )
    response.raise_for_status()
    return response.json()


def list_reports(
    report_type: str | None = None,
    limit: int = 20,
) -> ReportListResponse:
    params: dict[str, Any] = {"limit": int(limit)}
    if report_type:
        params["report_type"] = report_type
    response = _request("GET", "/api/v1/reports/", params=params)
    response.raise_for_status()
    return response.json()


def download_report_pdf(report_id: int | str) -> bytes:
    response = _request("GET", f"/api/v1/reports/{report_id}/pdf")
    response.raise_for_status()
    return response.content


def chat_with_gria(
    message: str,
    county_name: str | None = None,
    document_context: str | None = None,
    document_name: str | None = None,
) -> GriaChatResponse:
    payload = {
        "message": message,
        "county_name": normalize_county_name(county_name) if county_name else None,
        "document_context": document_context,
        "document_name": document_name,
    }
    response = _request("POST", "/api/v1/gria/chat", json=payload)
    response.raise_for_status()
    return response.json()


def upload_and_analyze(file_bytes: bytes, file_name: str) -> UploadResponse:
    response = _request(
        "POST",
        "/api/v1/upload/analyze",
        files={"file": (file_name, file_bytes)},
    )
    response.raise_for_status()
    return response.json()


def upload_to_storage(
    file_bytes: bytes,
    file_name: str,
    folder: str = "default",
) -> dict[str, Any]:
    encoded_folder = quote(folder.strip() or "default", safe="")
    response = _request(
        "POST",
        f"/api/v1/storage/upload?folder={encoded_folder}",
        files={"file": (file_name, file_bytes)},
    )
    response.raise_for_status()
    return response.json()


def delete_storage_file(file_path: str) -> dict[str, Any]:
    clean_path = file_path.strip().lstrip("/")
    response = _request("DELETE", f"/api/v1/storage/delete/{clean_path}")
    response.raise_for_status()
    return response.json()
