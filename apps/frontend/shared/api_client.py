"""HTTP-only client for AgriShield. The frontend never loads model artifacts."""
import os
from typing import Any
import requests


class APIError(Exception):
    """A backend error safe to present to the user."""


class AgriShieldClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.getenv("AGRISHIELD_API_URL") or os.getenv("BACKEND_URL") or "http://127.0.0.1:8000/api/v1").rstrip("/")
        if not self.base_url.endswith("/api/v1"):
            self.base_url += "/api/v1"
        self.token = token or os.getenv("AGRISHIELD_API_TOKEN")
        self.timeout = float(os.getenv("AGRISHIELD_API_TIMEOUT", "30"))

    def _request(self, method: str, path: str, *, binary: bool = False, **kwargs: Any):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        headers.update(kwargs.pop("headers", {}))
        try:
            response = requests.request(method, f"{self.base_url}{path}", headers=headers, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise APIError("The AgriShield backend could not be reached. Check the connection and try again; no substitute result was generated.") from exc
        if not response.ok:
            try:
                detail = response.json().get("detail", "Request failed")
                if isinstance(detail, list):
                    detail = "; ".join(f"{' / '.join(str(x) for x in item.get('loc', []) if x != 'body')}: {item.get('msg', 'Invalid value')}" for item in detail)
            except (ValueError, AttributeError):
                detail = "The backend could not complete this request."
            raise APIError(f"{detail} (HTTP {response.status_code})")
        if binary:
            return response.content
        try:
            return response.json()
        except ValueError as exc:
            raise APIError("The backend returned an unreadable response.") from exc

    def health(self):
        return self._request("GET", "/health")

    def schema(self):
        return self._request("GET", "/predictions/input-schema")

    def counties(self):
        return self._request("GET", "/predictions/counties")

    def predict(self, inputs):
        return self._request("POST", "/predictions/from-inputs", json=inputs)

    def predict_measurements(self, inputs):
        return self._request("POST", "/predictions/from-measurements", json=inputs)

    def compare_inputs(self, baseline, alternative):
        return self._request("POST", "/predictions/compare-inputs", json={"baseline": baseline, "alternative": alternative})

    def predict_csv(self, name, content):
        return self._request("POST", "/predictions/from-csv", files={"file": (name, content, "text/csv")})

    def report(self, inputs, result, include_gria=False):
        snapshot = self._request("POST", "/reports/assessments", json={"inputs": inputs, "expected_model_sha256": result["model_sha256"], "expected_probability": result["model_probability"], "include_gria": include_gria})
        try:
            pdf = self._request("GET", f"/reports/assessments/{snapshot['id']}/pdf", binary=True, headers={"X-Report-Token": snapshot['access_token']})
        except APIError:
            try:
                self.delete_report(snapshot)
            except APIError:
                pass
            raise
        return pdf, snapshot

    def historical_report(self, county, month):
        snapshot = self._request("POST", "/reports/historical", json={"county_name": county, "month": month})
        try:
            pdf = self._request("GET", f"/reports/assessments/{snapshot['id']}/pdf", binary=True, headers={"X-Report-Token": snapshot['access_token']})
        except APIError:
            try:
                self.delete_report(snapshot)
            except APIError:
                pass
            raise
        return pdf, snapshot

    def analyze_assessment(self, inputs, result):
        return self._request("POST", "/gria/analyze", json={"inputs": inputs, "expected_model_sha256": result["model_sha256"], "expected_probability": result["model_probability"]})

    def analyze_history(self, county, month):
        return self._request("POST", "/gria/analyze", json={"county_name": county, "month": month})

    def historical_detail(self, county, month):
        return self._request("GET", "/predictions/historical-detail", params={"county_name": county, "month": month})

    def delete_report(self, snapshot):
        self._request("DELETE", f"/reports/assessments/{snapshot['id']}", binary=True, headers={"X-Report-Token": snapshot['access_token']})
        return True

    def new_history_key(self):
        return self._request('POST', '/history/key')

    def save_history(self, key, inputs, result):
        return self._request('POST', '/history/assessments', headers={'X-History-Key': key}, json={'inputs': inputs, 'expected_model_sha256': result['model_sha256'], 'expected_probability': result['model_probability']})

    def save_historical_history(self, key, county, month):
        return self._request('POST', '/history/historical', headers={'X-History-Key': key}, json={'county_name': county, 'month': month})

    def history(self, key):
        return self._request('GET', '/history/records', headers={'X-History-Key': key})

    def history_record(self, key, record_id):
        return self._request('GET', f'/history/records/{record_id}', headers={'X-History-Key': key})

    def history_pdf(self, key, record_id):
        return self._request('GET', f'/history/records/{record_id}/pdf', binary=True, headers={'X-History-Key': key})

    def delete_history(self, key, record_id):
        self._request('DELETE', f'/history/records/{record_id}', binary=True, headers={'X-History-Key': key})
        return True

    def maize_years(self):
        return self._request("GET", "/outcomes/maize-years")

    def maize_outcomes(self, year):
        return self._request("GET", "/outcomes/maize", params={"year": year})

    def live_weather(self):
        return self._request("GET", "/live/weather")

    def historical_months(self):
        return self._request("GET", "/predictions/historical-months")

    def historical(self, month):
        return self._request("GET", "/predictions/historical-observations", params={"month": month})

    def historical_trends(self, county, month):
        return self._request("GET", "/predictions/historical-trends", params={"county_name": county, "through": month})

    def extract_document(self, name, content, mime):
        return self._request("POST", "/documents/extract", files={"file": (name, content, mime)})

    def chat(self, message, county, month, document_context=None, document_name=None):
        return self._request("POST", "/gria/chat", json={"message": message, "county_name": county, "month": month, "document_context": document_context, "document_name": document_name})


def get_client():
    return AgriShieldClient()
