"""Central HTTP client for all AgriShield backend API calls with auth."""
import os
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "https://agrishield-dnao.onrender.com")
try:
    import streamlit as st
    BACKEND_URL = st.secrets.get("BACKEND_URL", BACKEND_URL)
except Exception:
    pass

DEFAULT_TIMEOUT = 30


def _get_headers(include_json: bool = True) -> dict:
    api_key = os.getenv("API_KEY", "")
    try:
        import streamlit as st
        api_key = st.secrets.get("API_KEY", api_key)
    except Exception:
        pass
    token = st.session_state.get("access_token", "") if 'st' in dir() else ""
    headers = {}
    if include_json:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(method: str, path: str, files=None, **kwargs) -> requests.Response:
    url = f"{BACKEND_URL}{path}"
    kwargs.setdefault("headers", _get_headers(include_json=files is None))
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    if files is not None:
        kwargs["files"] = files
    return requests.request(method, url, **kwargs)


# ---------- Auth ----------
def login(email: str, password: str) -> dict:
    resp = _request("POST", "/api/v1/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()


def register(email: str, password: str, full_name: str, role: str = "farmer") -> dict:
    resp = _request("POST", "/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": full_name, "role": role,
    })
    resp.raise_for_status()
    return resp.json()


def get_current_user() -> dict | None:
    resp = _request("GET", "/api/v1/auth/me")
    if resp.status_code == 200:
        return resp.json()
    return None


# ---------- Health ----------
def check_health() -> dict | None:
    resp = requests.get(f"{BACKEND_URL}/api/v1/health", timeout=5)
    if resp.status_code == 200:
        return resp.json()
    return None


def get_root() -> dict | None:
    resp = requests.get(f"{BACKEND_URL}/", timeout=5)
    if resp.status_code == 200:
        return resp.json()
    return None


# ---------- Predictions ----------
def predict(county_name: str, focus: str = "crops") -> dict:
    resp = _request("POST", "/api/v1/predictions/crop-yield", json={
        "county_name": county_name, "focus": focus,
    })
    resp.raise_for_status()
    return resp.json()


def get_history(county_name: str, months: int = 12) -> dict:
    resp = _request("GET", f"/api/v1/predictions/history?county_name={county_name}&months={months}")
    resp.raise_for_status()
    return resp.json()


def get_batch_predictions() -> dict:
    resp = _request("GET", "/api/v1/predictions/batch")
    resp.raise_for_status()
    return resp.json()


def compare_counties(counties: list[str]) -> dict:
    resp = _request("POST", "/api/v1/predictions/compare", json={"counties": counties})
    resp.raise_for_status()
    return resp.json()


def get_region_aggregation(region_name: str) -> dict:
    resp = _request("POST", "/api/v1/predictions/region", json={"region_name": region_name})
    resp.raise_for_status()
    return resp.json()


def scenario_analysis(county_name: str, rainfall_change_pct: float = 0.0,
                      temp_change_c: float = 0.0, ndvi_shock: float = 0.0) -> dict:
    resp = _request("POST", "/api/v1/predictions/scenario", json={
        "county_name": county_name,
        "rainfall_change_pct": rainfall_change_pct,
        "temp_change_c": temp_change_c,
        "ndvi_shock": ndvi_shock,
    })
    resp.raise_for_status()
    return resp.json()


# ---------- Reports ----------
def create_report(county_name: str, report_type: str = "combined",
                  detailed: bool = False) -> dict:
    resp = _request("POST", "/api/v1/reports/create", json={
        "county_name": county_name, "report_type": report_type, "detailed": detailed,
    })
    resp.raise_for_status()
    return resp.json()


def list_reports(report_type: str | None = None, limit: int = 20) -> dict:
    params = {}
    if report_type:
        params["report_type"] = report_type
    resp = _request("GET", "/api/v1/reports/", params=params)
    resp.raise_for_status()
    return resp.json()


def get_report(report_id: int | str) -> dict:
    resp = _request("GET", f"/api/v1/reports/{report_id}")
    resp.raise_for_status()
    return resp.json()


def download_report_pdf(report_id: int | str) -> bytes:
    resp = _request("GET", f"/api/v1/reports/{report_id}/pdf")
    resp.raise_for_status()
    return resp.content


# ---------- Gria ----------
def chat_with_gria(message: str, county_name: str | None = None) -> dict:
    resp = _request("POST", "/api/v1/gria/chat", json={
        "message": message, "county_name": county_name,
    })
    resp.raise_for_status()
    return resp.json()


# ---------- Uploads ----------
def upload_and_analyze(file_bytes: bytes, file_name: str) -> dict:
    files = {"file": (file_name, file_bytes)}
    resp = _request("POST", "/api/v1/upload/analyze", files=files)
    resp.raise_for_status()
    return resp.json()


# ---------- Storage ----------
def upload_file(file_bytes: bytes, file_name: str, folder: str = "default") -> dict:
    files = {"file": (file_name, file_bytes)}
    resp = _request("POST", f"/api/v1/storage/upload?folder={folder}", files=files)
    resp.raise_for_status()
    return resp.json()


def delete_file(file_path: str) -> dict:
    resp = _request("DELETE", f"/api/v1/storage/delete/{file_path}")
    resp.raise_for_status()
    return resp.json()
