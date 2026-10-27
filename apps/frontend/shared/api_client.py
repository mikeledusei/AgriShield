"""Backend API client for the AgriShield Streamlit frontend."""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def _backend_url() -> str:
    backend_url = os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL)
    try:
        backend_url = st.secrets.get("BACKEND_URL", backend_url)
    except Exception:
        pass
    return backend_url.rstrip("/")


def _headers(include_json: bool = True) -> dict[str, str]:
    headers: dict[str, str] = {}
    if include_json:
        headers["Content-Type"] = "application/json"
    return headers


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    url = f"{_backend_url()}{path}"
    kwargs.setdefault("timeout", 30)
    if "headers" not in kwargs:
        kwargs["headers"] = _headers(include_json="json" not in kwargs and "data" not in kwargs and kwargs.get("files") is None)
    return requests.request(method, url, **kwargs)


def health() -> dict[str, Any]:
    response = requests.get(f"{_backend_url()}/api/v1/health", timeout=10)
    response.raise_for_status()
    return response.json()


def root_info() -> dict[str, Any]:
    response = requests.get(f"{_backend_url()}/", timeout=10)
    response.raise_for_status()
    return response.json()


def get_available_counties() -> list[str]:
    response = _request("GET", "/api/v1/predictions/counties")
    response.raise_for_status()
    return response.json()


def get_batch_predictions() -> dict[str, Any]:
    response = _request("GET", "/api/v1/predictions/batch")
    response.raise_for_status()
    return response.json()


def predict_county(county_name: str, focus: str = "crops") -> dict[str, Any]:
    response = _request(
        "POST",
        "/api/v1/predictions/crop-yield",
        json={"county_name": county_name, "focus": focus},
    )
    response.raise_for_status()
    return response.json()


def get_county_history(county_name: str, months: int = 12) -> dict[str, Any]:
    response = _request("GET", f"/api/v1/predictions/history?county_name={county_name}&months={months}")
    response.raise_for_status()
    return response.json()


def compare_counties(counties: list[str]) -> dict[str, Any]:
    response = _request("POST", "/api/v1/predictions/compare", json={"counties": counties})
    response.raise_for_status()
    return response.json()


def get_region_aggregation(region_name: str) -> dict[str, Any]:
    response = _request("POST", "/api/v1/predictions/region", json={"region_name": region_name})
    response.raise_for_status()
    return response.json()


def scenario_analysis(county_name: str, rainfall_change_pct: float = 0.0, temp_change_c: float = 0.0, ndvi_shock: float = 0.0) -> dict[str, Any]:
    response = _request(
        "POST",
        "/api/v1/predictions/scenario",
        json={
            "county_name": county_name,
            "rainfall_change_pct": rainfall_change_pct,
            "temp_change_c": temp_change_c,
            "ndvi_shock": ndvi_shock,
        },
    )
    response.raise_for_status()
    return response.json()


def create_report(county_name: str, report_type: str = "combined", detailed: bool = False) -> dict[str, Any]:
    response = _request(
        "POST",
        "/api/v1/reports/create",
        json={"county_name": county_name, "report_type": report_type, "detailed": detailed},
    )
    response.raise_for_status()
    return response.json()


def list_reports(report_type: str | None = None, limit: int = 20) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
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
) -> dict[str, Any]:
    payload = {
        "message": message,
        "county_name": county_name,
        "document_context": document_context,
        "document_name": document_name,
    }
    response = _request("POST", "/api/v1/gria/chat", json=payload)
    response.raise_for_status()
    return response.json()


def upload_and_analyze(file_bytes: bytes, file_name: str) -> dict[str, Any]:
    response = _request("POST", "/api/v1/upload/analyze", files={"file": (file_name, file_bytes)})
    response.raise_for_status()
    return response.json()


def upload_to_storage(file_bytes: bytes, file_name: str, folder: str = "default") -> dict[str, Any]:
    response = _request("POST", f"/api/v1/storage/upload?folder={folder}", files={"file": (file_name, file_bytes)})
    response.raise_for_status()
    return response.json()


def delete_storage_file(file_path: str) -> dict[str, Any]:
    response = _request("DELETE", f"/api/v1/storage/delete/{file_path}")
    response.raise_for_status()
    return response.json()
