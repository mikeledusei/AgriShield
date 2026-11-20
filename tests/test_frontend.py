"""Tests for the API-only dashboard and the real champion-model contract."""
import csv
import io
import math
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
import requests
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/frontend'))
sys.path.insert(0, str(ROOT / 'apps/backend'))

from datetime import UTC

from main import app
from services.prediction_service import get_engine
from shared.api_client import AgriShieldClient, APIError


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def example():
    # An actual held-out feature row; it is test input, not a UI default.
    row = pd.read_csv(ROOT / 'data_pipeline/data/processed/test_matrix.csv').iloc[0]
    keys = [x for x in get_engine().feature_cols if x not in ('month_sin', 'month_cos')]
    return {'county_name': row['county'], 'period': row['year_month'], **{k: float(row[k]) for k in keys}}


def test_schema_matches_champion_artifact(api):
    schema = api.get('/api/v1/predictions/input-schema').json()
    keys = [f['key'] for f in schema['features']]
    assert len(keys) == 14
    assert set(keys + schema['derived']) == set(get_engine().feature_cols)
    assert schema['csv_columns'] == ['county_name', 'period'] + keys


def test_complete_user_inputs_match_direct_model(api, example):
    response = api.post('/api/v1/predictions/from-inputs', json=example)
    assert response.status_code == 200, response.text
    result = response.json()
    model = get_engine().model
    cols = get_engine().feature_cols
    frame = pd.DataFrame([[result['features'][c] for c in cols]], columns=cols)
    assert result['model_probability'] == pytest.approx(model.predict_proba(frame)[0][1])
    assert result['features']['month_sin'] == round(math.sin(2 * math.pi / 12), 6)
    assert result['features']['month_cos'] == round(math.cos(2 * math.pi / 12), 6)
    for key in set(example) - {'county_name', 'period'}:
        assert result['features'][key] == example[key]
    assert 'not a calibrated probability' in result['meaning']


def test_invalid_and_incomplete_inputs_are_rejected(api, example):
    for changes in ({'county_name': 'Not a county'}, {'period': '2025-13'}, {'period': '0000-01'},
                    {'soil_moisture': 2}, {'ndvi_lag1': -2}, {'rain_3m_sum': 0}, {'extra_field': 1}):
        assert api.post('/api/v1/predictions/from-inputs', json={**example, **changes}).status_code == 422
    missing = dict(example)
    del missing['ndvi_lag1']
    assert api.post('/api/v1/predictions/from-inputs', json=missing).status_code == 422
    with patch.object(get_engine(), 'model', None):
        assert api.post('/api/v1/predictions/from-inputs', json=example).status_code == 503


def test_csv_and_pdf_use_the_same_complete_vector(api, example):
    schema = api.get('/api/v1/predictions/input-schema').json()
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=schema['csv_columns'])
    writer.writeheader()
    writer.writerow(example)
    response = api.post('/api/v1/predictions/from-csv', files={'file': ('observations.csv', text.getvalue(), 'text/csv')})
    assert response.status_code == 200, response.text
    manual = api.post('/api/v1/predictions/from-inputs', json=example).json()
    assert response.json()['features'] == manual['features']
    assert response.json()['score'] == manual['score']
    response = api.post('/api/v1/predictions/inputs-pdf', json=example)
    assert response.status_code == 200
    assert response.content.startswith(b'%PDF')
    assert api.post('/api/v1/predictions/from-csv', files={'file': ('bad.csv', text.getvalue() + text.getvalue().splitlines(True)[1], 'text/csv')}).status_code == 422
    assert api.post('/api/v1/predictions/from-csv', files={'file': ('bad.csv', b'county_name,period\nNakuru,2025-01\n', 'text/csv')}).status_code == 422


def test_historical_only_uses_existing_data(api):
    months = api.get('/api/v1/predictions/historical-months').json()
    assert '2025-02' in months
    response = api.get('/api/v1/predictions/historical-observations', params={'month': '2025-02'})
    assert response.status_code == 200
    assert len(response.json()['observations']) == 47
    assert api.get('/api/v1/predictions/historical-observations', params={'month': '2099-01'}).status_code == 404
    assert api.post('/api/v1/gria/chat', json={'county_name': 'Nakuru', 'month': '2099-01', 'message': 'Explain'}).status_code == 422


def test_client_surfaces_backend_errors_without_fallback():
    client = AgriShieldClient('http://127.0.0.1:9999')
    with patch('shared.api_client.requests.request', side_effect=requests.ConnectionError('offline')):
        with pytest.raises(APIError, match='no substitute result'):
            client.predict({})


def test_dashboard_pages_render_with_backend_contract(api, example):
    from streamlit.testing.v1 import AppTest

    # Bridge frontend HTTP calls to the real FastAPI app, not an embedded scorer.
    class ResponseAdapter:
        def __init__(self, response):
            self.response = response
            self.ok = response.is_success
            self.status_code = response.status_code
            self.content = response.content
        def json(self):
            return self.response.json()

    def bridge(method, url, **kwargs):
        kwargs.pop('timeout', None)
        path = '/api/v1' + url.split('/api/v1', 1)[1]
        return ResponseAdapter(api.request(method, path, **kwargs))

    with patch('shared.api_client.requests.request', side_effect=bridge):
        dashboard = AppTest.from_file(str(ROOT / 'apps/frontend/streamlit_app.py'), default_timeout=30).run()
        assert not dashboard.exception
        for page in ['New assessment', 'Historical explorer', 'Ask Gria']:
            dashboard.radio[0].set_value(page).run(timeout=60)
            assert not dashboard.exception, [e.value for e in dashboard.exception]
            if page == 'New assessment':
                assert len([x for x in dashboard.number_input if x.key.startswith("feature_")]) == 14
                assert len([x for x in dashboard.number_input if x.key.startswith("raw_")]) == 16
                assert all(field.value is None for field in dashboard.number_input)
                from datetime import date
                dashboard.selectbox[0].set_value(example['county_name'])
                year, month = map(int, example['period'].split('-'))
                dashboard.date_input[0].set_value(date(year, month, 1))
                for field in dashboard.number_input:
                    if field.key.startswith('feature_'):
                        field.set_value(example[field.key.removeprefix('feature_')])
                dashboard.button[0].click().run(timeout=60)
                assert not dashboard.exception, [e.value for e in dashboard.exception]
                assert any(m.label == 'Vegetation-stress score' for m in dashboard.metric)
                assert dashboard.session_state['assessment']['county_name'] == example['county_name']
                next(button for button in dashboard.button if button.label == 'Prepare PDF report').click().run(timeout=60)
                assert dashboard.session_state['report_pdf'].startswith(b'%PDF')


def test_raw_measurements_reproduce_training_features(api):
    data = pd.concat([
        pd.read_csv(ROOT / 'data_pipeline/data/processed/train_matrix.csv'),
        pd.read_csv(ROOT / 'data_pipeline/data/processed/test_matrix.csv'),
    ])
    series = data[data['county'] == 'Baringo'].sort_values('year_month').reset_index(drop=True)
    i = series.index[series['year_month'] == '2024-01'][0]
    row = series.iloc[i]
    raw = {
        'county_name': row['county'], 'period': row['year_month'],
        'rainfall_mm': row['rainfall_mm'], 'rain_previous_1': series.iloc[i-1]['rainfall_mm'],
        'rain_previous_2': series.iloc[i-2]['rainfall_mm'],
        'rain_normal': row['rainfall_mm'] - row['rainfall_anomaly'],
        'temp_mean_c': row['temp_mean_c'], 'soil_moisture': row['soil_moisture'],
        'ndvi_lag1': series.iloc[i-1]['ndvi_mean'], 'ndvi_lag2': series.iloc[i-2]['ndvi_mean'],
        'ndvi_lag3': series.iloc[i-3]['ndvi_mean'],
        'ndvi_historical_mean': row['ndvi_mean_hist'], 'ndvi_historical_std': row['ndvi_std_hist'],
        'total_households': int(row['total']), 'farming_households': int(row['farming']),
        'crop_households': int(row['crop_production']), 'livestock_households': int(row['livestock_production']),
        'irrigation_households': int(row['irrigation']),
    }
    response = api.post('/api/v1/predictions/from-measurements', json=raw)
    assert response.status_code == 200, response.text
    features = response.json()['features']
    for key in get_engine().feature_cols:
        assert features[key] == pytest.approx(float(row[key]), abs=1e-5), key
    raw['irrigation_households'] = raw['farming_households'] + 1
    assert api.post('/api/v1/predictions/from-measurements', json=raw).status_code == 422


def test_historical_trend_is_aligned_to_requested_month(api):
    response = api.get('/api/v1/predictions/historical-trends', params={'county_name': 'Nakuru', 'through': '2024-05'})
    assert response.status_code == 200, response.text
    items = response.json()['observations']
    assert len(items) == 12
    assert items[-1]['period'] == '2024-05'
    assert api.get('/api/v1/predictions/historical-trends', params={'county_name': 'Nakuru', 'through': '2099-01'}).status_code == 404


def test_map_boundaries_match_backend_counties(api):
    import json
    geo = json.loads((ROOT / 'apps/frontend/assets/kenya_counties.geojson').read_text())
    boundaries = {feature['properties']['county'].replace('-', ' ') for feature in geo['features']}
    assert boundaries == set(api.get('/api/v1/predictions/counties').json())


def test_report_snapshot_is_private_and_does_not_rescore(api, example):
    result = api.post('/api/v1/predictions/from-inputs', json=example).json()
    request = {'inputs': example, 'expected_model_sha256': result['model_sha256'], 'expected_probability': result['model_probability']}
    assert api.post('/api/v1/reports/assessments', json={**request, 'expected_probability': 0.99999}).status_code == 409
    saved = api.post('/api/v1/reports/assessments', json=request)
    assert saved.status_code == 201, saved.text
    report = saved.json()
    url = f"/api/v1/reports/assessments/{report['id']}/pdf"
    assert api.get(url).status_code == 404
    assert api.get(url, headers={'X-Report-Token': 'incorrect'}).status_code == 404
    with patch.object(get_engine(), 'model', None):
        pdf = api.get(url, headers={'X-Report-Token': report['access_token']})
        assert pdf.status_code == 200
        assert pdf.content.startswith(b'%PDF')
    assert api.delete(f"/api/v1/reports/assessments/{report['id']}", headers={'X-Report-Token': report['access_token']}).status_code == 204
    assert api.get(url, headers={'X-Report-Token': report['access_token']}).status_code == 404


def test_what_if_uses_two_complete_vectors(api, example):
    alternative = {**example, 'rainfall_mm': example['rainfall_mm'] / 2}
    response = api.post('/api/v1/predictions/compare-inputs', json={'baseline': example, 'alternative': alternative})
    assert response.status_code == 200
    assert response.json()['alternative']['features']['rainfall_mm'] == alternative['rainfall_mm']
    assert response.json()['score_delta'] == response.json()['alternative']['score'] - response.json()['baseline']['score']
    assert api.post('/api/v1/predictions/compare-inputs', json={'baseline': example, 'alternative': {**alternative, 'county_name': 'Nakuru'}}).status_code == 422


def test_explanation_reconstructs_the_model_output(api, example):
    result = api.post('/api/v1/predictions/from-inputs', json=example).json()
    explanation = result['explanation']
    assert explanation is not None
    raw = explanation['baseline_log_odds'] + sum(item['contribution'] for item in explanation['values'])
    assert 1 / (1 + math.exp(-raw)) == pytest.approx(result['model_probability'], abs=1e-8)


def test_readiness_reports_an_unreachable_database(api):
    from services import health_service
    with patch.object(health_service, 'engine', None):
        response = api.get('/api/v1/health/ready')
        assert response.status_code == 503
        body = response.json()
        assert body['status'] == 'degraded'
        assert body['services']['database'] == 'not configured'
        assert any('DATABASE_URL' in problem for problem in body['problems'])


def test_documents_are_extracted_as_context_not_scored(api):
    from docx import Document
    from reportlab.pdfgen import canvas
    doc = Document()
    doc.add_paragraph('Field notes from Nakuru')
    buffer = io.BytesIO()
    doc.save(buffer)
    response = api.post('/api/v1/documents/extract', files={'file': ('notes.docx', buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert response.status_code == 200
    assert 'Field notes from Nakuru' in response.json()['text']
    assert 'score' not in response.json()
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(80, 700, 'Rainfall observation')
    pdf.save()
    response = api.post('/api/v1/documents/extract', files={'file': ('report.pdf', output.getvalue(), 'application/pdf')})
    assert response.status_code == 200
    assert 'Rainfall observation' in response.json()['text']
    assert api.post('/api/v1/documents/extract', files={'file': ('photo.png', b'fake', 'image/png')}).status_code == 400
    assert api.post('/api/v1/documents/extract', files={'file': ('bad.pdf', b'not a pdf', 'application/pdf')}).status_code == 422
    large = api.post('/api/v1/documents/extract', files={'file': ('notes.txt', b'x' * 5000, 'text/plain')}).json()
    assert len(large['text']) == 4000 and large['truncated']


def test_engine_never_invents_missing_historical_data():
    engine = get_engine()
    with pytest.raises(ValueError, match='No historical data'):
        engine._build_vector('Nakuru', '2099-01')
    with patch.object(engine, 'county_history', {}), patch.object(engine, 'available_months', []):
        assert engine.get_available_months() == []
        with pytest.raises(ValueError, match='No historical data'):
            engine._build_vector('Nakuru', '2025-02')
    with patch.object(engine, 'model', None):
        with pytest.raises(ValueError, match='No trained model'):
            engine._score('Nakuru', '2025-02', None)
    with pytest.raises(ValueError, match='No complete historical feature row'):
        engine._score('Nakuru', '2025-02', None)


def test_inputs_outside_the_training_range_are_rejected(api, example):
    """Tree models extrapolate confidently, so out-of-distribution input is refused."""
    result = api.post('/api/v1/predictions/from-inputs', json=example).json()
    assert result['training_range_check'] == 'checked'
    assert result['extrapolated'] is False

    unusual = {**example, 'rainfall_mm': 1000, 'rain_3m_sum': 1500}
    rejected = api.post('/api/v1/predictions/from-inputs', json=unusual)
    assert rejected.status_code == 422
    detail = str(rejected.json()['detail'])
    assert 'rainfall_mm' in detail and 'training range' in detail
    assert 'accept_extrapolation' in detail


def test_extrapolation_can_be_opted_into_and_is_flagged(api, example):
    unusual = {**example, 'rainfall_mm': 1000, 'rain_3m_sum': 1500, 'accept_extrapolation': True}
    response = api.post('/api/v1/predictions/from-inputs', json=unusual)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['extrapolated'] is True
    assert {'rainfall_mm', 'rain_3m_sum'} <= {item['feature'] for item in result['training_range_warnings']}
    assert 'extrapolation' in result['meaning']


def test_wrong_unit_entry_gets_a_targeted_hint(api, example):
    """The most common mistake: entering a percentage where a fraction is expected."""
    response = api.post('/api/v1/predictions/from-inputs',
                        json={**example, 'forage_dryness_index': 40})
    assert response.status_code == 422
    detail = str(response.json()['detail']).lower()
    assert 'forage_dryness_index' in detail
    assert 'not a percentage' in detail


def test_range_check_degrades_when_the_model_digest_differs(api, example):
    with patch.object(get_engine(), 'model_sha256', '0' * 64):
        result = api.post('/api/v1/predictions/from-inputs', json=example).json()
        assert result['training_range_check'] == 'unavailable'


def test_expired_reports_are_inaccessible_and_can_be_cleaned(api, example):
    from datetime import datetime, timedelta

    from database.connection import SessionLocal
    from database.models import AssessmentReportSnapshot
    from routers.snapshot_reports import cleanup_expired
    result = api.post('/api/v1/predictions/from-inputs', json=example).json()
    saved = api.post('/api/v1/reports/assessments', json={'inputs': example, 'expected_model_sha256': result['model_sha256'], 'expected_probability': result['model_probability']}).json()
    db = SessionLocal()
    try:
        db.get(AssessmentReportSnapshot, saved['id']).created_at = datetime.utcnow() - timedelta(days=8)
        db.commit()
        response = api.get(f"/api/v1/reports/assessments/{saved['id']}/pdf", headers={'X-Report-Token': saved['access_token']})
        assert response.status_code == 404
        assert cleanup_expired(db) >= 1
        db.commit()
        assert db.get(AssessmentReportSnapshot, saved['id']) is None
    finally:
        db.close()


def test_historical_detail_matches_map_and_shap(api):
    month = '2024-05'
    data = api.get('/api/v1/predictions/historical-observations', params={'month': month}).json()
    assert len(data['observations']) == 47
    detail = api.get('/api/v1/predictions/historical-detail', params={'county_name': 'Nakuru', 'month': month}).json()
    assert detail['score'] == next(x['score'] for x in data['observations'] if x['county'] == 'Nakuru')
    assert detail['period'] == month and detail['explanation']
    log_odds = detail['explanation']['baseline_log_odds'] + sum(x['contribution'] for x in detail['explanation']['values'])
    assert 1 / (1 + math.exp(-log_odds)) == pytest.approx(detail['model_probability'], abs=1e-8)
    assert api.get('/api/v1/predictions/historical-detail', params={'county_name': 'Nakuru', 'month': '2099-01'}).status_code == 404


def test_gria_uses_exact_evidence_and_fails_closed(api, example):
    from agents import gria_agent
    from langchain_core.messages import AIMessage
    class Agent:
        def invoke(self, data):
            prompt = data['messages'][0].content
            assert 'Nakuru' in prompt and '2024-05' in prompt
            assert 'contribution' in prompt and 'rainfall_mm' in prompt and 'counties_available' in prompt
            return {'messages': [AIMessage(content='A grounded explanation.') ]}
    with patch.object(gria_agent, 'agent_executor', Agent()):
        response = api.post('/api/v1/gria/analyze', json={'county_name': 'Nakuru', 'month': '2024-05'})
    assert response.status_code == 200, response.text
    assert response.json()['analysis'] == {'mode': 'ai', 'text': 'A grounded explanation.'}
    assert response.json()['evidence']['national']['counties_available'] == 47
    with patch.object(gria_agent, 'agent_executor', None):
        response = api.post('/api/v1/gria/analyze', json={'county_name': 'Nakuru', 'month': '2024-05'}).json()
        assert response['analysis']['mode'] == 'summary'
        assert 'not live' in response['analysis']['text']
        assert 'local agricultural' in response['analysis']['text']
    assert api.post('/api/v1/gria/analyze', json={'county_name': 'Nakuru', 'month': '2099-01'}).status_code == 404
    result = api.post('/api/v1/predictions/from-inputs', json=example).json()
    payload = {'inputs': example, 'expected_model_sha256': result['model_sha256'], 'expected_probability': result['model_probability']}
    assert api.post('/api/v1/gria/analyze', json={**payload, 'expected_probability': .999999}).status_code == 409
    with patch.object(gria_agent, 'agent_executor', None):
        result = api.post('/api/v1/gria/analyze', json=payload).json()
        assert result['evidence']['kind'] == 'user-provided'
        assert result['analysis']['mode'] == 'summary'


def test_branded_gria_report_is_stored_and_never_rescores(api):
    import json

    import pdfplumber
    from agents import gria_agent
    from database.connection import SessionLocal
    from database.models import AssessmentReportSnapshot
    with patch.object(gria_agent, 'agent_executor', None):
        response = api.post('/api/v1/reports/historical', json={'county_name': 'Nakuru', 'month': '2024-05'})
    assert response.status_code == 201, response.text
    saved = response.json()
    db = SessionLocal()
    try:
        snapshot = json.loads(db.get(AssessmentReportSnapshot, saved['id']).snapshot_json)
        assert snapshot['report_analysis']['mode'] == 'summary'
        assert snapshot['report_context']['national']['counties_available'] == 47
    finally:
        db.close()
    path = f"/api/v1/reports/assessments/{saved['id']}"
    assert api.get(path + '/pdf').status_code == 404
    with patch.object(get_engine(), 'model', None):
        pdf = api.get(path + '/pdf', headers={'X-Report-Token': saved['access_token']})
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    with pdfplumber.open(io.BytesIO(pdf.content)) as document:
        text = '\n'.join(page.extract_text() or '' for page in document.pages)
    for expected in ['AgriShield', 'Nakuru', '2024-05', 'Historical score trend', 'SHAP', 'SHA-256', 'not live']:
        assert expected in text
    assert api.delete(path, headers={'X-Report-Token': saved['access_token']}).status_code == 204


def test_map_all_months_have_the_47_matching_boundary_names(api):
    import json
    geo = json.loads((ROOT / 'apps/frontend/assets/kenya_counties.geojson').read_text())
    boundaries = {feature['properties']['county'].replace('-', ' ') for feature in geo['features']}
    months = api.get('/api/v1/predictions/historical-months').json()
    for month in months:
        response = api.get('/api/v1/predictions/historical-observations', params={'month': month})
        assert response.status_code == 200
        counties = {item['county'] for item in response.json()['observations']}
        assert len(counties) == 47 and counties == boundaries


def test_dashboard_historical_gria_and_report_flow(api):
    from agents import gria_agent
    from streamlit.testing.v1 import AppTest
    class ResponseAdapter:
        def __init__(self, response):
            self.response, self.ok, self.status_code, self.content = response, response.is_success, response.status_code, response.content
            self.headers = response.headers
        def json(self):
            return self.response.json()
    def bridge(method, url, **kwargs):
        kwargs.pop('timeout', None)
        return ResponseAdapter(api.request(method, '/api/v1' + url.split('/api/v1', 1)[1], **kwargs))
    with patch('shared.api_client.requests.request', side_effect=bridge), patch.object(gria_agent, 'agent_executor', None):
        dashboard = AppTest.from_file(str(ROOT / 'apps/frontend/streamlit_app.py'), default_timeout=60).run()
        dashboard.radio[0].set_value('Historical explorer').run(timeout=60)
        assert not dashboard.exception, [x.value for x in dashboard.exception]
        next(x for x in dashboard.button if x.label == 'Ask Gria to analyze this county').click().run(timeout=60)
        assert not dashboard.exception, [x.value for x in dashboard.exception]
        assert dashboard.session_state['history_analysis']['analysis']['mode'] == 'summary'
        next(x for x in dashboard.button if x.label == 'Prepare county PDF with Gria').click().run(timeout=60)
        assert not dashboard.exception, [x.value for x in dashboard.exception]
        assert dashboard.session_state['historical_pdf'].startswith(b'%PDF')


def test_manual_gria_report_keeps_original_generated_text(api, example):
    import pdfplumber
    from agents import gria_agent
    from langchain_core.messages import AIMessage
    class Agent:
        def invoke(self, data):
            return {'messages': [AIMessage(content='Check the field & consult local experts before acting.')]}
    result = api.post('/api/v1/predictions/from-inputs', json=example).json()
    payload = {'inputs': example, 'expected_model_sha256': result['model_sha256'], 'expected_probability': result['model_probability'], 'include_gria': True}
    with patch.object(gria_agent, 'agent_executor', Agent()):
        response = api.post('/api/v1/reports/assessments', json=payload)
    assert response.status_code == 201, response.text
    snapshot = response.json()
    path = f"/api/v1/reports/assessments/{snapshot['id']}"
    with patch.object(gria_agent, 'agent_executor', None), patch.object(get_engine(), 'model', None):
        pdf = api.get(path + '/pdf', headers={'X-Report-Token': snapshot['access_token']})
    assert pdf.status_code == 200
    with pdfplumber.open(io.BytesIO(pdf.content)) as doc:
        text = '\n'.join(page.extract_text() or '' for page in doc.pages)
    assert 'Gria AI analysis' in text and 'Check the field & consult local experts' in text
    assert api.delete(path, headers={'X-Report-Token': snapshot['access_token']}).status_code == 204


def test_private_history_restores_saved_result_and_isolates_keys(api, example):
    from datetime import datetime, timedelta

    from database.connection import SessionLocal
    from database.models import HistoryRecord
    from routers.history import purge_history
    first_key = api.post('/api/v1/history/key').json()['key']
    second_key = api.post('/api/v1/history/key').json()['key']
    result = api.post('/api/v1/predictions/from-inputs', json=example).json()
    payload = {'inputs': example, 'expected_model_sha256': result['model_sha256'], 'expected_probability': result['model_probability']}
    assert api.post('/api/v1/history/assessments', json=payload).status_code == 401
    assert api.post('/api/v1/history/assessments', headers={'X-History-Key': first_key}, json={**payload, 'expected_probability': .99999}).status_code == 409
    created = api.post('/api/v1/history/assessments', headers={'X-History-Key': first_key}, json=payload)
    assert created.status_code == 201
    record_id = created.json()['id']
    path = f'/api/v1/history/records/{record_id}'
    assert api.get(path, headers={'X-History-Key': second_key}).status_code == 404
    assert api.get('/api/v1/history/records', headers={'X-History-Key': second_key}).json()['records'] == []
    assert api.get('/api/v1/history/records', headers={'X-History-Key': first_key}).json()['records'][0]['id'] == record_id
    with patch.object(get_engine(), 'model', None):
        saved = api.get(path, headers={'X-History-Key': first_key})
        pdf = api.get(path + '/pdf', headers={'X-History-Key': first_key})
    assert saved.json()['model_probability'] == result['model_probability']
    assert pdf.content.startswith(b'%PDF')
    assert api.delete(path, headers={'X-History-Key': second_key}).status_code == 404
    db = SessionLocal()
    try:
        db.get(HistoryRecord, record_id).created_at = datetime.utcnow() - timedelta(days=91)
        db.commit()
        assert api.get(path, headers={'X-History-Key': first_key}).status_code == 404
        assert purge_history(db) >= 1
        db.commit()
    finally:
        db.close()


def test_live_weather_backend_rejects_stale_or_unavailable_data(api):
    from datetime import datetime, timedelta

    from routers import live
    now = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M')
    def data(timestamp):
        return [{'location_id': i, 'current': {'time': timestamp, 'interval': 900, 'temperature_2m': 23.0,
                   'relative_humidity_2m': 55, 'precipitation': 0.1, 'wind_speed_10m': 5}}
                for i in range(47)]
    class Response:
        def __init__(self, body): self.body = body
        def raise_for_status(self): pass
        def json(self): return self.body
    live.reset_cache()
    with patch('routers.live.httpx.get', return_value=Response(data(now))) as request:
        result = api.get('/api/v1/live/weather')
        assert result.status_code == 200
        assert len(result.json()['observations']) == 47
        assert result.json()['observations'][0]['county'] == 'Baringo'
        assert result.json()['observations'][0]['interval_seconds'] == 900
        assert api.get('/api/v1/live/weather').status_code == 200
        assert request.call_count == 1
    live.reset_cache()
    old = (datetime.now(UTC) - timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M')
    with patch('routers.live.httpx.get', return_value=Response(data(old))):
        assert api.get('/api/v1/live/weather').status_code == 503
    live.reset_cache()
    with patch('routers.live.httpx.get', side_effect=__import__('httpx').ConnectError('offline')):
        assert api.get('/api/v1/live/weather').status_code == 503


def test_live_map_and_history_ui_use_backend(api, example):
    from datetime import datetime

    from routers import live
    from seed_counties import COUNTY_METADATA
    from streamlit.testing.v1 import AppTest
    class ResponseAdapter:
        def __init__(self, response):
            self.response, self.ok, self.status_code, self.content = response, response.is_success, response.status_code, response.content
            self.headers = response.headers
        def json(self): return self.response.json()
    def bridge(method, url, **kwargs):
        kwargs.pop('timeout', None)
        return ResponseAdapter(api.request(method, '/api/v1' + url.split('/api/v1', 1)[1], **kwargs))
    now = datetime.now(UTC).isoformat()
    observations = [{'county': c, 'latitude': m['latitude'], 'longitude': m['longitude'], 'time_utc': now,
                     'temperature_c': 23.0, 'humidity_percent': 55, 'precipitation_mm': .1, 'wind_kmh': 5.0, 'interval_seconds': 900}
                    for c, m in sorted(COUNTY_METADATA.items())]
    response = {'source': 'Open-Meteo', 'retrieved_at': now, 'observations': observations}
    live.reset_cache()
    with patch('shared.api_client.requests.request', side_effect=bridge), patch('routers.live._retrieve_weather', return_value=response):
        dashboard = AppTest.from_file(str(ROOT / 'apps/frontend/streamlit_app.py'), default_timeout=60).run()
        dashboard.radio[0].set_value('Live conditions').run(timeout=60)
        assert not dashboard.exception, [x.value for x in dashboard.exception]
        assert any('47 / 47' in str(metric.value) for metric in dashboard.metric)
        dashboard.radio[0].set_value('History').run(timeout=60)
        next(b for b in dashboard.button if b.label == 'Create a new private history key').click().run(timeout=60)
        key = dashboard.session_state['history_key']
        result = api.post('/api/v1/predictions/from-inputs', json=example).json()
        api.post('/api/v1/history/assessments', headers={'X-History-Key': key}, json={'inputs': example, 'expected_model_sha256': result['model_sha256'], 'expected_probability': result['model_probability']})
        dashboard.run(timeout=60)
        assert not dashboard.exception, [x.value for x in dashboard.exception]
        assert any(m.label == 'Saved score' for m in dashboard.metric)
        next(b for b in dashboard.button if b.label == 'Delete this saved assessment').click().run(timeout=60)
        assert not dashboard.exception, [x.value for x in dashboard.exception]


def test_reported_maize_outcomes_are_not_proxy_or_live(api):
    years = api.get('/api/v1/outcomes/maize-years').json()
    assert years == [2020, 2018, 2017, 2016, 2015, 2014, 2013, 2012]
    assert api.get('/api/v1/outcomes/maize', params={'year': 2019}).status_code == 404
    result = api.get('/api/v1/outcomes/maize', params={'year': 2020}).json()
    assert len(result['observations']) == 47
    assert 'not a real-time' in result['source']
    bad = next(row for row in result['observations'] if row['county'] == 'Nairobi')
    assert bad['quality_flag'] == 'nonpositive_area' and bad['yield_tonnes_per_ha'] is None
    assert sum(row['yield_tonnes_per_ha'] is not None for row in result['observations']) == 46


def test_maize_dashboard_page_renders(api):
    from streamlit.testing.v1 import AppTest
    class ResponseAdapter:
        def __init__(self, response):
            self.response, self.ok, self.status_code, self.content = response, response.is_success, response.status_code, response.content
            self.headers = response.headers
        def json(self): return self.response.json()
    def bridge(method, url, **kwargs):
        kwargs.pop('timeout', None)
        return ResponseAdapter(api.request(method, '/api/v1' + url.split('/api/v1', 1)[1], **kwargs))
    with patch('shared.api_client.requests.request', side_effect=bridge):
        dashboard = AppTest.from_file(str(ROOT / 'apps/frontend/streamlit_app.py'), default_timeout=60).run()
        dashboard.radio[0].set_value('Reported maize yields').run(timeout=60)
        assert not dashboard.exception, [x.value for x in dashboard.exception]
        assert any('46 / 47' in str(m.value) for m in dashboard.metric)


def test_county_map_places_labels_without_overlap():
    """Every county gets a dot; labels never overlap each other or leave the frame."""
    import shared.county_map as county_map_module
    from shared.map_data import county_centroids

    class _Stub:
        def markdown(self, *args, **kwargs):
            return None

    county_map = county_map_module.county_map
    original = county_map_module.st
    county_map_module.st = _Stub()
    try:
        centroids = county_centroids.__wrapped__()
        assert len(centroids) == 47
        bands = ['Lower', 'Moderate', 'Elevated', 'High']
        rows = [
            {'county': name, **point, 'band': bands[index % 4]}
            for index, (name, point) in enumerate(sorted(centroids.items()))
        ]
        figure = county_map(rows, band_key='band')
    finally:
        county_map_module.st = original

    markers = [trace for trace in figure.data if getattr(trace, 'mode', '') == 'markers' and trace.text]
    assert sum(len(trace.text) for trace in markers) == 47  # no county dropped

    # Reconstruction uses the renderer's own constants, so the test cannot drift from it.
    char_width = county_map_module.CHAR_WIDTH
    line_height = county_map_module.LINE_HEIGHT
    pad = county_map_module.LABEL_PAD
    boxes = []
    for annotation in figure.layout.annotations:
        lines = annotation.text.split('<br>')
        width = char_width * max(len(line) for line in lines) + 2 * pad
        height = line_height * len(lines) + 2 * pad
        anchor_x, anchor_y = annotation.xanchor, annotation.yanchor
        x0 = annotation.x if anchor_x == 'left' else annotation.x - width if anchor_x == 'right' else annotation.x - width / 2
        y0 = annotation.y if anchor_y == 'bottom' else annotation.y - height if anchor_y == 'top' else annotation.y - height / 2
        boxes.append((x0, y0, x0 + width, y0 + height))

    for index, box in enumerate(boxes):
        assert box[0] >= 33.0 and box[2] <= 42.5, f'label clipped horizontally: {box}'
        for other in boxes[index + 1:]:
            assert (
                box[2] <= other[0] or box[0] >= other[2] or box[3] <= other[1] or box[1] >= other[3]
            ), f'labels overlap: {box} vs {other}'

    # The legend colours must be the score-band palette, not a rescaled gradient.
    from shared.scales import BAND_COLORS

    filled = {trace.marker.color for trace in markers}
    assert filled <= set(BAND_COLORS.values()) | {None}
