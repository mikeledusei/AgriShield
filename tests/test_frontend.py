"""Frontend unit, backend-contract alignment, and headless rendering tests."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "frontend"))
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))
if FRONTEND_DIR not in sys.path:
    sys.path.insert(0, FRONTEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def test_frontend_imports():
    """Verify all frontend modules import without errors."""
    import shared.types
    import shared.kenya_counties
    import shared.ui_helpers
    import shared.api_client
    import streamlit_app
    assert streamlit_app is not None


def test_canonical_47_counties_and_coordinates():
    """Ensure exactly 47 canonical counties and zero Nairobi fallback bugs for hyphenated names."""
    from shared.kenya_counties import (
        KENYA_COUNTIES,
        COUNTY_LOCATIONS,
        REGIONS,
        normalize_county_name,
        get_county_coords,
    )

    assert len(KENYA_COUNTIES) == 47
    assert len(set(KENYA_COUNTIES)) == 47
    assert len(COUNTY_LOCATIONS) == 47
    assert "Nairobi" in REGIONS
    assert len(REGIONS) == 8

    # Hyphenated names must resolve to canonical names and distinct coordinates (not Nairobi's -1.286, 36.817)
    nairobi_coords = COUNTY_LOCATIONS["Nairobi"]
    for alias, expected in [
        ("Taita-Taveta", "Taita Taveta"),
        ("Elgeyo-Marakwet", "Elgeyo Marakwet"),
        ("Tharaka-Nithi", "Tharaka Nithi"),
        ("Muranga", "Murang'a"),
        ("Homabay", "Homa Bay"),
    ]:
        assert normalize_county_name(alias) == expected
        coords = get_county_coords(alias)
        assert coords != nairobi_coords


def test_geojson_asset_loads_47_features():
    """Verify kenya_counties.geojson loads all 47 county boundary features."""
    from streamlit_app import load_kenya_geojson

    geojson = load_kenya_geojson()
    assert geojson is not None
    assert "features" in geojson
    assert len(geojson["features"]) == 47


def test_ui_helpers_and_markdown_formatting():
    """Test risk badge, model label, and Markdown-to-HTML sanitization."""
    from shared.ui_helpers import (
        risk_label_from_score,
        format_model_label,
        summary_badge,
        format_markdown_to_html,
    )

    assert risk_label_from_score(10) == "SAFE"
    assert risk_label_from_score(35) == "MODERATE"
    assert risk_label_from_score(60) == "HIGH"
    assert risk_label_from_score(85) == "CRITICAL"
    assert risk_label_from_score("invalid") == "SAFE"

    assert format_model_label("lightgbm_v1") == "LightGBM Champion v1"
    assert format_model_label("xgboost_v1") == "XGBoost v1"
    assert format_model_label(None) == "LightGBM Champion v1"

    badge = summary_badge("HIGH")
    assert "role='status'" in badge
    assert "HIGH" in badge

    html_out = format_markdown_to_html("**Bold** <script>alert(1)</script>\n- Item 1")
    assert "<strong>Bold</strong>" in html_out
    assert "&lt;script&gt;" in html_out
    assert "• Item 1" in html_out


def test_api_client_backend_contract_alignment():
    """Verify frontend api_client calls match backend routes, query encoding, and schemas."""
    from fastapi.testclient import TestClient
    from main import app
    from shared import api_client

    test_client = TestClient(app)

    def _bridge_request(method: str, url: str, **kwargs):
        path = url.replace("http://127.0.0.1:8000", "")
        kwargs.pop("timeout", None)
        resp = test_client.request(method, path, **kwargs)
        mock_resp = MagicMock()
        mock_resp.status_code = resp.status_code
        mock_resp.json.return_value = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        mock_resp.content = resp.content
        mock_resp.raise_for_status = resp.raise_for_status
        return mock_resp

    with patch("shared.api_client.requests.request", side_effect=_bridge_request):
        # 1. Health check
        h = api_client.health()
        assert h["status"] == "healthy"
        assert h["model_name"] == "lightgbm_v1"

        # 2. Auth status
        a = api_client.auth_status()
        assert "status" in a

        # 3. Available counties (strictly 47, no duplicates)
        counties = api_client.get_available_counties()
        assert len(counties) == 47
        assert len(set(counties)) == 47

        # 4. Single county prediction (including apostrophe/space name)
        pred = api_client.predict_county("Murang'a", focus="crops")
        assert pred["county_name"] == "Murang'a"
        assert pred["model_used"] == "lightgbm_v1"

        # 5. History with URL-encoded county name ("Murang'a")
        hist = api_client.get_county_history("Murang'a", months=12)
        assert hist["county_name"] == "Murang'a"
        assert len(hist["trend"]) == 12

        # 6. Compare counties
        comp = api_client.compare_counties(["Taita-Taveta", "Turkana", "Uasin Gishu"])
        assert len(comp["counties"]) == 3

        # 7. Region aggregation (including Nairobi)
        reg = api_client.get_region_aggregation("Nairobi")
        assert reg["county_count"] == 1

        # 8. Scenario analysis
        scen = api_client.scenario_analysis("Kajiado", rainfall_change_pct=-30.0, temp_change_c=2.0, ndvi_shock=-0.1)
        assert scen["county_name"] == "Kajiado"
        assert "score_delta" in scen

        # 9. Report creation, listing, and PDF download
        rep = api_client.create_report("Bungoma", report_type="combined", detailed=True)
        assert rep["id"] >= 1
        rep_list = api_client.list_reports(limit=5)
        assert rep_list["total"] >= 1
        pdf_bytes = api_client.download_report_pdf(rep["id"])
        assert pdf_bytes.startswith(b"%PDF")

        # 10. Gria chat with document context
        chat_res = api_client.chat_with_gria(
            "Explain current drought risk",
            county_name="Turkana",
            document_context="Sample field observation",
            document_name="notes.txt",
        )
        assert "reply" in chat_res
        assert chat_res["risk_score"] is not None
