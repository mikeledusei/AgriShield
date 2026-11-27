"""AgriShield's API-only Streamlit interface."""
import base64
import csv
import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from shared.api_client import APIError, ConfigurationError, get_client
from shared.county_map import county_map, legend_scores, map_caption
from shared.map_data import county_centroids
from shared.scales import BAND_COLORS, BAND_ORDER

st.set_page_config(page_title="AgriShield | Agricultural intelligence", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
ASSETS = Path(__file__).resolve().parent / "assets"
try:
    client = get_client()
except ConfigurationError as exc:  # fail visibly, not on the first click
    st.error(f"Dashboard configuration error: {exc}")
    st.stop()


def inject_style():
    image = base64.b64encode((ASSETS / "agrishield-landscape.jpg").read_bytes()).decode()
    st.markdown(f'''<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap');
    .stApp {{background:#f6f8f3;color:#203b2a;font-family:'DM Sans',sans-serif;}}
    [data-testid="stSidebar"] {{background:#173e2c;}}
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] p {{color:#eef5e9 !important;}}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {{padding:8px 0;}}
    .block-container {{padding-top:2rem;padding-bottom:4rem;max-width:1400px;}}
    h1,h2,h3 {{color:#173e2c;letter-spacing:-.035em;}}
    h1,h2 {{font-family:'DM Serif Display',serif;}}
    .hero {{min-height:278px;border-radius:18px;padding:38px 42px;display:flex;flex-direction:column;justify-content:center;color:white;background:linear-gradient(90deg,rgba(14,48,29,.92),rgba(20,55,32,.57) 54%,rgba(20,55,32,.08)),url("data:image/jpeg;base64,{image}") center 54%/cover;}}
    .hero h1 {{color:white;font-size:2.9rem;line-height:1.04;margin:10px 0 14px;max-width:590px;}}
    .hero p {{color:#edf5e8;max-width:560px;font-size:1rem;line-height:1.6;margin:0;}}
    .eyebrow {{color:#a8d79d;font-weight:700;font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;}}
    .section-label {{color:#628168;font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:.72rem;margin-top:1.5rem;}}
    .intro {{color:#6a7d6d;line-height:1.6;margin-top:-.4rem;}}
    .map-legend {{display:flex;flex-wrap:wrap;align-items:center;gap:4px 18px;margin:-6px 0 8px;font-size:.82rem;color:#33493a;}}
    .map-legend span {{display:inline-flex;align-items:center;gap:6px;}}
    .map-legend i {{width:11px;height:11px;border-radius:50%;border:1px solid rgba(32,54,42,.45);display:inline-block;}}
    .map-legend .muted {{color:#6b7d6f;font-size:.76rem;}}
    .feature-card {{background:white;border:1px solid #e4ebe0;border-radius:14px;padding:20px;min-height:145px;box-shadow:0 3px 14px rgba(30,65,40,.025);}}
    .feature-card .icon {{font-size:1.25rem;background:#edf4e8;border-radius:10px;padding:8px;display:inline-block;margin-bottom:12px;}}
    .feature-card strong {{display:block;font-size:1rem;color:#203d2a;margin-bottom:5px;}}
    .feature-card span {{font-size:.83rem;color:#6d8070;line-height:1.45;}}
    .soft-note {{background:#edf4e9;border:1px solid #d9e9d4;border-radius:12px;padding:15px 18px;color:#45664d;font-size:.85rem;line-height:1.5;}}
    [data-testid="stMetric"] {{background:#fff;border:1px solid #e3ebdf;border-radius:12px;padding:16px;}}
    [data-testid="stMetricValue"] {{color:#1d4b30;}}
    [data-testid="stForm"] {{background:white;border:1px solid #e1eadd;border-radius:16px;padding:24px;}}
    .stButton > button[kind="primary"], .stFormSubmitButton > button {{background:#2b6842;border:0;border-radius:9px;color:#fff;font-weight:700;}}
    .stButton > button, .stDownloadButton > button {{border-radius:9px;}}
    div[data-testid="stExpander"] {{background:white;border:1px solid #e1eadd;border-radius:12px;}}
    @media(max-width:640px) {{.hero {{padding:27px;min-height:250px}} .hero h1 {{font-size:2.1rem}}}}
    </style>''', unsafe_allow_html=True)


def _map_row(record, centroids):
    """Attach the county centroid to a result row, or drop it if it cannot be placed."""
    point = centroids.get(record.get('county'))
    if point is None:
        return None
    return {**record, **point}


def api(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except APIError as exc:
        st.error(str(exc))
        return None


def page_heading(kicker, title, description):
    st.markdown(f'<div class="section-label">{kicker}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="intro">{description}</p>', unsafe_allow_html=True)


def disclaimer():
    st.markdown('<div class="soft-note"><strong>About this research tool.</strong> The model estimates a vegetation-greenness stress proxy. It does not predict confirmed crop losses or forage shortages, and its scores are not calibrated probabilities or official warnings. Check results with local experts before acting.</div>', unsafe_allow_html=True)


def show_shap(explanation, key):
    if not explanation:
        st.info('SHAP contributions are unavailable for this model output.')
        return
    st.caption('SHAP shows how each input moves this model output relative to its baseline. It does not show causes or percentage-point changes.')
    rows = explanation['values'][:10]
    frame = pd.DataFrame([{'Input': x['label'],
                           'Contribution': x['contribution'],
                           'Direction': 'Raises model output' if x['contribution'] >= 0 else 'Lowers model output'} for x in rows])
    frame = frame.iloc[::-1]
    fig = px.bar(frame, x='Contribution', y='Input', color='Direction', orientation='h',
                 color_discrete_map={'Raises model output': '#b46041', 'Lowers model output': '#438059'},
                 labels={'Contribution': 'SHAP contribution (model log-odds)', 'Input': ''})
    fig.update_layout(height=max(300, len(rows) * 35 + 95), margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend_title_text='')
    st.plotly_chart(fig, width='stretch', key=key)


def show_analysis(analysis):
    st.markdown('#### Gria’s explanation' if analysis['mode'] == 'ai' else '#### Evidence summary')
    st.markdown(analysis['text'])
    st.caption('AI-generated text can contain mistakes; verify decisions with a local expert.' if analysis['mode'] == 'ai' else 'Gria AI is unavailable. This is a factual backend summary, not an AI-generated analysis.')


def assessment_payload(result, schema):
    return {'county_name': result['county_name'], 'period': result['period'], **{item['key']: result['features'][item['key']] for item in schema['features']}}


def remember_assessment(result):
    st.session_state.previous_assessment = st.session_state.get('last_successful_assessment')
    st.session_state.last_successful_assessment = result
    st.session_state.assessment = result


def show_result(result):
    st.markdown('### Your assessment')
    a, b, c = st.columns(3)
    a.metric('Vegetation-stress score', f"{result['score']} / 100")
    b.metric('Score band', result['band'])
    c.metric('Observation period', result['period'])
    st.caption(f"{result['county_name']} County · Model: {result['model_used']} · Calculated by the backend from the inputs below")
    disclaimer()
    if result.get('extrapolated'):
        st.error(
            'Extrapolation: ' + ', '.join(item['label'] for item in result['training_range_warnings'])
            + ' lie outside the model training range. This score is an extrapolation and should not be used for decisions.'
        )
    elif result.get('training_range_warnings'):
        st.warning('Some inputs are outside the range seen in training: ' + ', '.join(item['label'] for item in result['training_range_warnings']) + '. The model may be less reliable for these values.')
    elif result.get('training_range_check') != 'checked':
        st.info('Training-range checks are unavailable for this model.')
    else:
        st.caption('Inputs are within the individual ranges observed in training; this does not guarantee their combination is familiar or that the score is accurate.')
    if result.get('measurements'):
        with st.expander('See the original measurements'):
            st.dataframe(pd.DataFrame([{'Measurement': k, 'Value': v} for k, v in result['measurements'].items()]), hide_index=True, width='stretch')
    with st.expander('What influenced this score? (SHAP)', expanded=True):
        show_shap(result.get('explanation'), 'assessment_shap')
    st.caption('If you ask Gria to analyze this assessment or include its analysis in a report, the model inputs and score may be sent to the configured AI provider. Do not include sensitive information.')
    if st.button('Ask Gria to analyze this assessment', key='analyze_assessment'):
        schema = api(client.schema)
        if schema:
            with st.spinner('Analyzing the model evidence…'):
                response = api(client.analyze_assessment, assessment_payload(result, schema), result)
            if response:
                st.session_state.manual_analysis = {'key': (result['county_name'], result['period'], result['model_probability']), 'analysis': response['analysis']}
    stored_analysis = st.session_state.get('manual_analysis')
    if stored_analysis and stored_analysis['key'] == (result['county_name'], result['period'], result['model_probability']):
        show_analysis(stored_analysis['analysis'])
    with st.expander('See the exact model inputs'):
        st.dataframe(pd.DataFrame([{'Input': k, 'Value': v} for k, v in result['features'].items()]), hide_index=True, width='stretch')
    if st.button('Save assessment to history', key='save_assessment_history'):
        history_key = st.session_state.get('history_key')
        if not history_key:
            st.info('Create or enter your private key in History first.')
        else:
            schema = api(client.schema)
            if schema and api(client.save_history, history_key, assessment_payload(result, schema), result):
                st.success('Assessment saved to your private history for up to 90 days.')
    st.caption('Reports expire after 7 days and require a private access token. Expired records are cleaned up when a new report is saved. Do not include sensitive personal information.')
    include_gria = st.checkbox('Include a Gria analysis in the PDF (may send inputs to the AI provider)', key='include_gria_report')
    if include_gria:
        st.caption('A fresh analysis is generated when the report is saved; it may differ from the explanation above.')
    if st.button('Prepare PDF report', key='prepare_report'):
        schema = api(client.schema)
        if schema:
            payload = assessment_payload(result, schema)
            with st.spinner('Preparing the report…'):
                report = api(client.report, payload, result, include_gria)
            if report:
                st.session_state.report_pdf, st.session_state.report_snapshot = report
                st.session_state.setdefault('saved_reports', []).append({**st.session_state.report_snapshot, 'county': result['county_name'], 'period': result['period']})
                st.session_state.report_key = (result['county_name'], result['period'], result['model_sha256'], result['model_probability'])
    if st.session_state.get('report_key') == (result['county_name'], result['period'], result['model_sha256'], result['model_probability']):
        st.download_button('Download your report', st.session_state.report_pdf, file_name='agrishield-assessment.pdf', mime='application/pdf')
        if st.button('Delete saved report'):
            if api(client.delete_report, st.session_state.report_snapshot):
                st.session_state.report_key = None
                deleted_id = st.session_state.report_snapshot['id']
                st.session_state.saved_reports = [item for item in st.session_state.get('saved_reports', []) if item['id'] != deleted_id]
                st.success('Saved report deleted. Any PDF you already downloaded remains on your device.')
    previous = st.session_state.get('previous_assessment')
    if previous and (previous['county_name'], previous['period']) == (result['county_name'], result['period']):
        with st.expander('Compare with your previous assessment'):
            st.caption('A what-if comparison of two sets of inputs, recalculated using the current model. This is not a forecast or a causal estimate.')
            if st.button('Compare assessments'):
                schema = api(client.schema)
                if schema:
                    keys = [item['key'] for item in schema['features']]
                    def make_payload(item):
                        return {'county_name': item['county_name'], 'period': item['period'], **{k: item['features'][k] for k in keys}}
                    comparison = api(client.compare_inputs, make_payload(previous), make_payload(result))
                    if comparison:
                        st.metric('Change in proxy score', f"{comparison['alternative']['score']} / 100", delta=f"{comparison['score_delta']:+d} points")
                        st.caption(comparison['meaning'])


inject_style()
with st.sidebar:
    st.markdown('### 🌿 AgriShield')
    st.caption('AGRICULTURAL INTELLIGENCE')
    st.divider()
    page = st.radio('WORKSPACE', ['Overview', 'Live conditions', 'Reported maize yields', 'New assessment', 'Historical explorer', 'History', 'Ask Gria'], label_visibility='collapsed')
    st.divider()
    st.markdown('**Built for better decisions**')
    st.caption('Explore agricultural signals with clarity, context and care.')
    health = api(client.health)
    if health:
        if health.get('model_loaded'):
            # Show gria status inline when known
            gria_note = ""
            if health.get('gria_available') is True:
                gria_note = " · Gria AI ready"
            elif health.get('gria_available') is False:
                gria_note = " · Gria summary mode"
            st.success(f"Backend connected · model ready{gria_note}")
        else:
            st.warning('Backend connected · model unavailable')
            if health.get('problems'):
                st.caption(" · ".join(health['problems'][:2]))
    saved_reports = st.session_state.get('saved_reports', [])
    if saved_reports:
        st.divider()
        st.markdown('**Saved in this session**')
        for saved in list(saved_reports):
            st.caption(f"{saved['county']} · {saved['period']}")
            if st.button('Delete saved report', key='delete_' + saved['id']):
                if api(client.delete_report, saved):
                    st.session_state.saved_reports = [item for item in saved_reports if item['id'] != saved['id']]
                    if st.session_state.get('report_snapshot', {}).get('id') == saved['id']:
                        st.session_state.report_key = None
                    if st.session_state.get('historical_snapshot', {}).get('id') == saved['id']:
                        st.session_state.historical_pdf_key = None
                    st.rerun()
    st.caption('Research prototype · Kenya')

if page == 'Overview':
    st.markdown('''<div class="hero"><span class="eyebrow">🌱 &nbsp; AGRICULTURAL INTELLIGENCE FOR KENYA</span><h1>Better insight.<br>Stronger communities.</h1><p>Turn agricultural observations into a clearer picture of vegetation stress, and explore historical patterns across Kenya.</p></div>''', unsafe_allow_html=True)
    st.markdown('<div class="section-label">YOUR WORKSPACE</div>', unsafe_allow_html=True)
    st.subheader('A clearer view of the land')
    st.markdown('<p class="intro">Explore the tools designed to help you understand the signals behind changing conditions.</p>', unsafe_allow_html=True)
    cards = st.columns(3)
    for col, icon, title, desc in zip(cards, ['🌾', '🗺️', '✦'], ['Assess your observations', 'Explore historical patterns', 'Ask Gria'], ['Enter your own measurements and receive a model score.', 'Compare the project’s historical county data for a selected month.', 'Ask questions about a selected historical county assessment.'], strict=False):
        with col:
            st.markdown(f'<div class="feature-card"><div class="icon">{icon}</div><strong>{title}</strong><span>{desc}</span></div>', unsafe_allow_html=True)
    st.write('')
    disclaimer()
    st.markdown('#### How to get started')
    st.write('Choose **New assessment** in the sidebar, select a county and month, and enter the requested measurements. Every value sent to the model is shown with your result.')

elif page == 'Live conditions':
    page_heading('LIVE WEATHER', 'Current conditions across Kenya', 'Current weather at one representative point in each county, updated by Open-Meteo.')
    st.warning('Weather is modelled for a point, not a county average. This is not a live crop or forage risk map, field measurement, forecast of losses, or official warning.')
    @st.fragment(run_every=600)
    def live_map():
        data = api(client.live_weather)
        if not data:
            st.info('Live conditions are unavailable. The app will not substitute historical data. Try again later.')
            return
        df = pd.DataFrame(data['observations'])
        st.caption(f"Source: Open-Meteo · Last retrieved: {data['retrieved_at']} · Model times: {df['time_utc'].min()} to {df['time_utc'].max()} · Updates every 10 minutes")
        st.caption('Open-Meteo current conditions come from weather models; the free API is intended for non-commercial use. See https://open-meteo.com/ for attribution and terms.')
        st.metric('County locations available', f"{len(df)} / 47")
        options = {'Temperature (°C)': 'temperature_c', 'Relative humidity (%)': 'humidity_percent', 'Precipitation (mm per model interval)': 'precipitation_mm', 'Wind speed (km/h)': 'wind_kmh'}
        selected = st.selectbox('Weather indicator', list(options))
        column = options[selected]
        fig = county_map(
            df.to_dict('records'),
            band_key=None,
            value_key=column,
            value_label=selected,
            hover_lines=lambda row: (
                f"{row['temperature_c']} °C · {row['humidity_percent']}% humidity<br>"
                f"{row['precipitation_mm']} mm per interval · {row['wind_kmh']} km/h<br>"
                f"Model time {row['time_utc']}"
            ),
            height=580,
        )
        if fig is None:
            st.warning('The county map asset could not be loaded, so the map is unavailable.')
            st.dataframe(df, hide_index=True, width='stretch')
            return
        st.plotly_chart(fig, width='stretch')
        st.caption(map_caption(fig))
        st.dataframe(df.rename(columns={'county': 'County', 'temperature_c': 'Temperature °C', 'humidity_percent': 'Humidity %', 'precipitation_mm': 'Precipitation mm / interval', 'wind_kmh': 'Wind km/h', 'time_utc': 'Model time UTC', 'interval_seconds': 'Interval seconds'}), hide_index=True, width='stretch')
        st.caption('Coordinates are representative points from the project, not field stations. Precipitation is the amount over the provider’s stated model interval.')
    live_map()

elif page == 'Reported maize yields':
    page_heading('REPORTED CROP OUTCOMES', 'Maize production by county', 'Explore reported historical maize yields, separate from the vegetation proxy.')
    st.warning('These are historical reported annual maize yields, not a live risk map or a model prediction. The third-party workbook is attributed to Kilimodata/KNBS but its primary source has not been independently verified.')
    years = api(client.maize_years)
    if years:
        year = st.selectbox('Harvest year', years)
        data = api(client.maize_outcomes, year)
        if data:
            frame = pd.DataFrame(data['observations'])
            valid = frame[frame['quality_flag'] == 'ok']
            st.metric('Counties with usable records', f'{len(valid)} / 47')
            if len(valid) < 47:
                st.info('Some reported values are inconsistent or lack harvested area and are not shown as yields. See the table for flags.')
            centroids = county_centroids()
            plotted = [_map_row(record, centroids) for record in valid.to_dict('records')]
            plotted = [row for row in plotted if row is not None]
            fig = county_map(
                plotted,
                band_key=None,
                value_key='yield_tonnes_per_ha',
                value_label='Reported yield (t/ha)',
                hover_lines=lambda row: f"Reported yield: {row['yield_tonnes_per_ha']:.2f} t/ha",
                height=560,
            ) if plotted else None
            if fig is None:
                st.warning('No reported yields can be placed on the map.')
                st.dataframe(frame, hide_index=True, width='stretch')
            else:
                st.plotly_chart(fig, width='stretch')
                st.caption(map_caption(fig) + ' Dot colour is the reported yield, not a risk band.')
                st.caption('Dot indicators represent reported county yields (tonnes/ha), not crop failure or risk scores. Yields depend on crop type, planting, area, weather and other factors.')
            st.dataframe(frame.rename(columns={'county': 'County', 'yield_tonnes_per_ha': 'Yield (tonnes/ha)', 'harvested_area_ha': 'Harvested area (ha)', 'production_tonnes': 'Production (tonnes)', 'quality_flag': 'Quality flag'}), hide_index=True, width='stretch')
            st.markdown(f"Sources: [KNBS catalogue]({data['source_page']}) · [workbook mirror]({data['mirror']}). 2019 is not present in this workbook.")

elif page == 'New assessment':
    page_heading('01 / YOUR OBSERVATIONS', 'Create an assessment', 'Bring your own observations. All fields are required so the model never fills gaps with invented values.')
    disclaimer()
    schema = api(client.schema)
    counties = api(client.counties)
    if schema is not None and counties is not None:
        manual, raw_tab, csv_tab = st.tabs(['✎  Enter model inputs', '🌱  Calculate from measurements', '↑  Upload a CSV'])
        with manual:
            st.caption('A fraction is a value from 0 to 1: for example, 0.25 means 25%. Use measurements and definitions consistent with the model training data.')
            with st.form('assessment_form'):
                left, right = st.columns(2)
                county = left.selectbox('County', counties, index=None, placeholder='Choose a county')
                date = right.date_input('Observation month', value=None, help='Choose any day in the month your measurements describe.')
                values = {}
                for group in ['Weather & soil', 'Vegetation', 'County livelihoods']:
                    st.markdown(f'#### {group}')
                    fields = [f for f in schema['features'] if f['group'] == group]
                    for i in range(0, len(fields), 2):
                        cols = st.columns(2)
                        for col, field in zip(cols, fields[i:i+2], strict=False):
                            values[field['key']] = col.number_input(f"{field['label']} ({field['unit']})", min_value=float(field['minimum']), max_value=float(field['maximum']), value=None, step=0.01, format='%.6f', help=field['help'], key='feature_' + field['key'])
                st.caption('The model also uses two seasonal values. The backend calculates these from your selected month; you do not need to enter them.')
                accept_extrapolation = st.checkbox(
                    'Score even if a value is outside the model training range',
                    value=False,
                    help='The result will be labelled as an extrapolation and should not be used for decisions.',
                )
                submitted = st.form_submit_button('Generate assessment  →', type='primary', width='stretch')
            if submitted:
                st.session_state.assessment = None
                st.session_state.report_key = None
                missing = [f['label'] for f in schema['features'] if values[f['key']] is None]
                if not county or not date or missing:
                    st.error('Please choose a county and month and complete every measurement.' + (' Missing: ' + ', '.join(missing) if missing else ''))
                else:
                    payload = {'county_name': county, 'period': date.strftime('%Y-%m'), **values,
                               'accept_extrapolation': accept_extrapolation}
                    with st.spinner('Evaluating your observations…'):
                        result = api(client.predict, payload)
                    if result:
                        remember_assessment(result)
                        st.session_state.report_key = None
                        # Gria AI analysis and branded PDF report for the assessment
                        st.divider()
                        st.markdown('#### 🤖 Gria AI Analysis & Branded Report')
                        st.caption('The champion model predicts the score based on your assessment info. Gria AI can analyse this output and generate a branded PDF report.')
                        x, y = st.columns(2)
                        if x.button('Ask Gria to analyse this assessment'):
                            with st.spinner('Gria is analysing the model output…'):
                                try:
                                    analyzed = api(client.analyze_assessment, payload, result)
                                    st.session_state.assessment_analysis = analyzed['analysis']
                                    st.success('Analysis complete.')
                                except Exception as e:
                                    st.error(f'Gria analysis failed: {e}')
                        if y.button('Prepare branded PDF report'):
                            with st.spinner('Generating branded report…'):
                                try:
                                    pdf, snapshot = api(client.report, payload, result, include_gria=True)
                                    st.session_state.assessment_pdf = pdf
                                    st.session_state.assessment_snapshot = snapshot
                                    st.session_state.assessment_pdf_key = (county, date.strftime('%Y-%m'))
                                    st.success('Report generated successfully.')
                                except Exception as e:
                                    st.error(f'Report generation failed: {e}')
                        analysis = st.session_state.get('assessment_analysis')
                        if analysis:
                            st.markdown('#### Gria’s analysis of the assessment')
                            st.markdown(analysis)
                        if st.session_state.get('assessment_pdf_key') == (county, date.strftime('%Y-%m')):
                            st.download_button('Download assessment PDF', st.session_state.assessment_pdf, file_name='agrishield-assessment-report.pdf', mime='application/pdf')
        with raw_tab:
            st.write('Have the original measurements? Enter them below and the backend will calculate the indicators using the same formulas as model training.')
            st.caption('For the normal rainfall, use this county and calendar month’s 2015–2023 average. For normal NDVI and its variation, use the county’s 2015–2023 mean and sample standard deviation. The same training sources and definitions are needed for comparable results.')
            raw_groups = {
                'Rain, temperature & soil': [
                    ('rainfall_mm', 'Rainfall this month (mm)', 0., 5000.),
                    ('rain_previous_1', 'Rainfall last month (mm)', 0., 5000.),
                    ('rain_previous_2', 'Rainfall two months ago (mm)', 0., 5000.),
                    ('rain_normal', 'Normal rainfall for this calendar month (mm)', 0., 5000.),
                    ('temp_mean_c', 'Average temperature this month (°C)', -20., 60.),
                    ('soil_moisture', 'Average soil moisture this month (m³/m³)', 0., 1.),
                ],
                'Vegetation greenness': [
                    ('ndvi_lag1', 'NDVI last month', -1., 1.),
                    ('ndvi_lag2', 'NDVI two months ago', -1., 1.),
                    ('ndvi_lag3', 'NDVI three months ago', -1., 1.),
                    ('ndvi_historical_mean', 'County’s historical average NDVI', -1., 1.),
                    ('ndvi_historical_std', 'County’s historical NDVI variation', 0., 2.),
                ],
                'County households': [
                    ('total_households', 'Total households', 1, 100000000),
                    ('farming_households', 'Households farming', 0, 100000000),
                    ('crop_households', 'Households growing crops', 0, 100000000),
                    ('livestock_households', 'Households keeping livestock', 0, 100000000),
                    ('irrigation_households', 'Farming households using irrigation', 0, 100000000),
                ],
            }
            with st.form('measurement_form'):
                a, b = st.columns(2)
                raw_county = a.selectbox('County', counties, index=None, placeholder='Choose a county', key='raw_county')
                raw_date = b.date_input('Observation month', value=None, key='raw_date')
                raw_values = {}
                for group, fields in raw_groups.items():
                    st.markdown(f'#### {group}')
                    for i in range(0, len(fields), 2):
                        for col, (key, label, minimum, maximum) in zip(st.columns(2), fields[i:i+2], strict=False):
                            if isinstance(minimum, int):
                                raw_values[key] = col.number_input(label, min_value=minimum, max_value=maximum, value=None, step=1, key='raw_' + key)
                            else:
                                raw_values[key] = col.number_input(label, min_value=minimum, max_value=maximum, value=None, step=0.01, format='%.6f', key='raw_' + key)
                raw_submitted = st.form_submit_button('Calculate and assess  →', type='primary', width='stretch')
            if raw_submitted:
                st.session_state.assessment = None
                st.session_state.report_key = None
                if not raw_county or not raw_date or any(v is None for v in raw_values.values()):
                    st.error('Please choose a county and month and complete every measurement.')
                else:
                    payload = {'county_name': raw_county, 'period': raw_date.strftime('%Y-%m'), **raw_values,
                               'accept_extrapolation': False}
                    with st.spinner('Calculating indicators and evaluating your observations…'):
                        result = api(client.predict_measurements, payload)
                    if result:
                        remember_assessment(result)
        with csv_tab:
            st.write('Upload a UTF-8 CSV containing **one complete observation**. Column names and units must match the template. No missing values are filled in automatically.')
            st.caption('Values outside the model training range are rejected with the offending column. If you genuinely have such an observation, add an `accept_extrapolation` column set to `true`; the result is then labelled as an extrapolation.')
            buffer = io.StringIO()
            csv.writer(buffer).writerow(schema['csv_columns'] + ['accept_extrapolation'])
            st.download_button('Download empty CSV template', buffer.getvalue(), 'agrishield-template.csv', 'text/csv')
            with st.form('csv_form'):
                upload = st.file_uploader('Choose a CSV file', type=['csv'])
                csv_submit = st.form_submit_button('Assess uploaded data', type='primary')
            if csv_submit:
                st.session_state.assessment = None
                st.session_state.report_key = None
                if upload is None:
                    st.error('Choose a CSV file first.')
                else:
                    with st.spinner('Checking and evaluating your file…'):
                        result = api(client.predict_csv, upload.name, upload.getvalue())
                    if result:
                        remember_assessment(result)
                        st.session_state.report_key = None
        if st.session_state.get('assessment'):
            st.divider()
            show_result(st.session_state.assessment)

elif page == 'Historical explorer':
    page_heading('02 / HISTORICAL DATA', 'Explore Kenya', 'Compare scores calculated from the project’s historical county-month dataset. The dataset includes proxy and imputed values; this is not a live conditions map.')
    disclaimer()
    months = api(client.historical_months)
    if months is not None:
        if not months:
            st.warning('No historical dataset is available on the backend. Ask the administrator to provision the processed data.')
        else:
            month = st.selectbox('Historical observation month', sorted(months, reverse=True))
            data = api(client.historical, month)
            if data:
                df = pd.DataFrame(data['observations'])
                a, b, c = st.columns(3)
                a.metric('Counties with observations', len(df))
                b.metric('Average model score', f"{df['score'].mean():.1f} / 100")
                c.metric('Selected month', month)
                st.caption('The average is an unweighted mean of available county scores; it is not a regional impact estimate.')
                st.info(f"Historical data only · Latest packaged month: {max(months)}. This map is not connected to a live feed.")
                if len(df) < 47:
                    st.warning(f"Only {len(df)} of 47 counties have complete observations for this month; missing counties are not scored.")
                centroids = county_centroids()
                plotted = [_map_row(record, centroids) for record in df.to_dict('records')]
                plotted = [row for row in plotted if row is not None]
                name_all = st.toggle('Label every county', value=True, help='Off shows fewer names on the map; every name stays available on hover.')
                fig = county_map(plotted, band_key='band', height=600, label_all=name_all) if plotted else None
                if fig is not None:
                    st.plotly_chart(fig, width='stretch')
                    legend_scores()
                    st.caption(map_caption(fig) + ' Dot colour is the score band; the dot marks the county centre, not a station.')
                else:
                    st.warning('No scored counties could be placed on the map.')
                counts = df['band'].value_counts().reindex(list(BAND_ORDER), fill_value=0).reset_index()
                counts.columns = ['Score band', 'Counties']
                st.markdown('#### Counties by score band')
                bands = px.bar(counts, x='Score band', y='Counties', color='Score band', color_discrete_map=BAND_COLORS)
                bands.update_layout(height=260, showlegend=False, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(bands, width='stretch')
                st.caption('Bands are descriptive groupings of model scores, not official risk or warning categories.')
                region = st.selectbox('Filter table by region', ['All regions'] + sorted(df['region'].dropna().unique().tolist()))
                display = df if region == 'All regions' else df[df['region'] == region]
                st.dataframe(display.sort_values('score', ascending=False).rename(columns={'county': 'County', 'region': 'Region', 'score': 'Score / 100', 'band': 'Score band'}), hide_index=True, width='stretch')
                st.caption(f"Historical data · {month} · Model: {data['model_used']}. Scores reflect a research proxy, not verified losses.")
                st.markdown('#### Compare counties')
                chosen = st.multiselect('Choose counties to compare', sorted(df['county'].tolist()), max_selections=10, placeholder='Select up to ten counties')
                if chosen:
                    subset = df[df['county'].isin(chosen)].sort_values('score')
                    comparison = px.bar(subset, x='score', y='county', orientation='h', color='score', color_continuous_scale=['#aacb91', '#d8b77a', '#ac6547'], range_color=(0, 100), labels={'score': 'Model score / 100', 'county': 'County'})
                    comparison.update_layout(height=max(230, len(chosen) * 38 + 100), margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                    st.plotly_chart(comparison, width='stretch')
                st.markdown('#### County history')
                trend_county = st.selectbox('County for the historical trend and explanation', sorted(df['county'].tolist()))
                if trend_county:
                    trend = api(client.historical_trends, trend_county, month)
                    if trend:
                        series = pd.DataFrame(trend['observations'])
                        line = px.line(series, x='period', y='score', markers=True, labels={'period': 'Observation month', 'score': 'Model score / 100'})
                        line.update_traces(line_color='#39744a')
                        line.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_range=[0, 100])
                        st.plotly_chart(line, width='stretch')
                        st.caption('Up to 12 historical observations ending in the selected month. Scores are recomputed by the backend from the stored feature rows.')
                        rain_tab, vegetation_tab, moisture_tab = st.tabs(['Rainfall', 'Vegetation', 'Soil moisture'])
                        for tab, col, title, color in [(rain_tab, 'rainfall_mm', 'Rainfall (mm)', '#39744a'), (vegetation_tab, 'ndvi_lag1', 'Previous-month NDVI', '#78a159'), (moisture_tab, 'soil_moisture', 'Soil moisture (m³/m³)', '#4a8a9b')]:
                            with tab:
                                chart = px.line(series, x='period', y=col, markers=True, labels={'period': 'Observation month', col: title})
                                chart.update_traces(line_color=color)
                                chart.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                                st.plotly_chart(chart, width='stretch', key='history_' + col)
                        if trend_county:
                            detail = api(client.historical_detail, trend_county, month)
                            if detail:
                                st.markdown('#### What influenced this county score?')
                                show_shap(detail.get('explanation'), 'historical_shap')
                                st.caption('The following actions may send historical model evidence to the configured AI provider. No document content is included.')
                                x, y = st.columns(2)
                                if x.button('Ask Gria to analyze this county'):
                                    with st.spinner('Analyzing county evidence…'):
                                        analyzed = api(client.analyze_history, trend_county, month)
                                    if analyzed:
                                        st.session_state.history_analysis = {'key': (trend_county, month), 'analysis': analyzed['analysis']}
                                if st.button('Save this county assessment to history'):
                                    history_key = st.session_state.get('history_key')
                                    if not history_key:
                                        st.info('Create or enter your private key in History first.')
                                    elif api(client.save_historical_history, history_key, trend_county, month):
                                        st.success('Historical county assessment saved for up to 90 days.')
                                if y.button('Prepare county PDF with Gria'):
                                    with st.spinner('Preparing the county report…'):
                                        report = api(client.historical_report, trend_county, month)
                                    if report:
                                        st.session_state.historical_pdf, snapshot = report
                                        st.session_state.historical_snapshot = snapshot
                                        st.session_state.historical_pdf_key = (trend_county, month)
                                        st.session_state.setdefault('saved_reports', []).append({**snapshot, 'county': trend_county, 'period': month})
                                analysis = st.session_state.get('history_analysis')
                                if analysis and analysis['key'] == (trend_county, month):
                                    show_analysis(analysis['analysis'])
                                if st.session_state.get('historical_pdf_key') == (trend_county, month):
                                    st.download_button('Download county PDF', st.session_state.historical_pdf, file_name='agrishield-county-report.pdf', mime='application/pdf')
                        with st.expander('See historical weather and vegetation inputs'):
                            st.dataframe(series.rename(columns={'period': 'Month', 'score': 'Score / 100', 'rainfall_mm': 'Rainfall (mm)', 'ndvi_lag1': 'Previous month NDVI', 'soil_moisture': 'Soil moisture (m³/m³)'}), hide_index=True, width='stretch')

elif page == 'History':
    page_heading('SAVED ASSESSMENTS', 'Your private history', 'Return to assessments you chose to save and download their original results.')
    st.info('History is opt-in and kept for up to 90 days. Anyone with your private key can access and delete your history. Save the key securely: it cannot be recovered if lost. Existing reports made before you save an assessment here are not automatically imported.')
    if st.button('Create a new private history key'):
        created = api(client.new_history_key)
        if created:
            st.session_state.history_key = created['key']
            st.session_state.history_key_created = True
    if st.session_state.get('history_key_created') and st.session_state.get('history_key'):
        st.code(st.session_state.history_key)
        st.download_button('Download my private history key', st.session_state.history_key, file_name='agrishield-private-history-key.txt', mime='text/plain')
        st.caption('Store this key somewhere safe. Treat it like a password.')
    with st.form('history_key_form'):
        entered_key = st.text_input('Enter an existing private history key', type='password')
        open_history = st.form_submit_button('Open history')
    if open_history:
        if not entered_key:
            st.error('Enter your private history key.')
        else:
            st.session_state.history_key = entered_key.strip()
            st.session_state.history_key_created = False
    if st.session_state.get('history_key'):
        if st.button('Lock history on this device'):
            st.session_state.history_key = None
            st.session_state.history_key_created = False
            st.rerun()
        history = api(client.history, st.session_state.history_key)
        if history:
            records = history['records']
            if not records:
                st.info('No saved assessments. Use “Save assessment to history” on an assessment or in the historical explorer.')
            else:
                st.caption('Showing up to the latest 500 saved assessments; expired records cannot be accessed.')
                choices = {r['id']: f"{r['county']} · {r['period']} · {r['score']}/100 · saved {r['created_at']}" for r in records}
                selected_record = st.selectbox('Select a saved assessment', list(choices), format_func=lambda ident: choices[ident])
                saved = api(client.history_record, st.session_state.history_key, selected_record)
                if saved:
                    st.metric('Saved score', f"{saved['score']}/100", help='The original saved result, not a new calculation.')
                    st.caption(f"{saved['county_name']} · {saved['period']} · {saved.get('data_source', '')}")
                    show_shap(saved.get('explanation'), 'saved_history_shap')
                    with st.expander('Saved model inputs and details'):
                        st.dataframe(pd.DataFrame([{'Input': k, 'Value': v} for k, v in saved['features'].items()]), hide_index=True, width='stretch')
                        st.caption(f"Model {saved['model_used']} · SHA-256 {saved.get('model_sha256', 'unavailable')}")
                    if st.button('Prepare saved PDF'):
                        pdf = api(client.history_pdf, st.session_state.history_key, selected_record)
                        if pdf:
                            st.session_state.history_pdf = pdf
                            st.session_state.history_pdf_id = selected_record
                    if st.session_state.get('history_pdf_id') == selected_record:
                        st.download_button('Download saved PDF', st.session_state.history_pdf, file_name='agrishield-history.pdf', mime='application/pdf')
                    if st.button('Delete this saved assessment'):
                        if api(client.delete_history, st.session_state.history_key, selected_record):
                            st.session_state.history_pdf_id = None
                            st.rerun()

else:
    page_heading('03 / ASK GRIA', 'WhatsApp-style chat — Gria remembers your conversation', 'Ask Gria about a county and a historical month. Switch county/month anytime — Gria will see the new evidence.')
    disclaimer()
    st.caption('Messages are kept in this tab (WhatsApp-like) and can be optionally saved to your private history key (90 days, Neon). Questions may be sent to the AI provider when configured — do not include sensitive info.')

    counties, months = api(client.counties), api(client.historical_months)
    if counties is not None and months is not None:
        if not months:
            st.warning('Historical data not available — Gria cannot assess yet.')
        else:
            # --- Persistent chat state (session-first, opt-in Neon save) ---
            if "gria_messages" not in st.session_state:
                st.session_state.gria_messages = []  # [{role, content, county, month}]
            if "gria_county" not in st.session_state:
                st.session_state.gria_county = counties[0]
            if "gria_month" not in st.session_state:
                st.session_state.gria_month = sorted(months, reverse=True)[0]

            # Switchable context — changes apply to NEXT message, not previous history
            a, b = st.columns(2)
            county = a.selectbox('County (switch anytime)', counties, index=counties.index(st.session_state.gria_county) if st.session_state.gria_county in counties else 0, key="gria_county_sel")
            month = b.selectbox('Historical month (switch anytime)', sorted(months, reverse=True), index=sorted(months, reverse=True).index(st.session_state.gria_month) if st.session_state.gria_month in sorted(months, reverse=True) else 0, key="gria_month_sel")
            # Track switches for system notice
            switched = False
            if county != st.session_state.gria_county or month != st.session_state.gria_month:
                st.session_state.gria_county, st.session_state.gria_month = county, month
                switched = True
            if switched and st.session_state.gria_messages:
                st.caption(f"↻ Context switched to **{county} · {month}** — next reply will use new evidence. Previous turns stay in history.")
            st.session_state.gria_county, st.session_state.gria_month = county, month

            with st.expander('Add document context (optional)'):
                st.caption('PDF/DOCX/TXT ≤5 MB — extracted for your review. It is NOT model input. Checked “Share” on next message only.')
                with st.form('gria_doc_form'):
                    document = st.file_uploader('Choose a document', type=['pdf', 'docx', 'txt'])
                    extract = st.form_submit_button('Extract text')
                if extract:
                    st.session_state.document = None
                    if document is None:
                        st.error('Choose a document first.')
                    else:
                        extracted = api(client.extract_document, document.name, document.getvalue(), document.type or 'application/octet-stream')
                        if extracted:
                            st.session_state.document = extracted
                if st.session_state.get('document'):
                    st.caption('Review extracted text — if checked, it will be sent with your *next* message only.')
                    st.text_area('Extracted text', value=st.session_state.document['text'], height=120, disabled=True)
                    if st.session_state.document['truncated']:
                        st.warning('Shortened to 4,000 chars.')

            # Show opt-in save / restore row
            c1, c2, c3 = st.columns([1,1,1])
            if c1.button('Clear chat', help='Wipe this tab — not the saved copy'):
                st.session_state.gria_messages = []
                st.rerun()
            # Save to Neon if user has history_key
            if c2.button('Save chat to private history', help='Saves to Neon for 90 days — needs History key in History page'):
                hk = st.session_state.get('history_key')
                if not hk:
                    st.warning('Create/open a private history key in the History page first, then save.')
                elif not st.session_state.gria_messages:
                    st.info('No messages to save.')
                else:
                    res = api(client.save_gria_chat, hk, county, month, st.session_state.gria_messages)
                    if res:
                        st.success(f"Saved — {res['id'][:8]}… (90 days)")
            if c3.button('Load last saved chat', help='Restore last saved Gria chat from Neon'):
                hk = st.session_state.get('history_key')
                if not hk:
                    st.warning('Enter your History key first.')
                else:
                    lst = api(client.list_gria_chats, hk)
                    if lst and lst.get('conversations'):
                        last = lst['conversations'][0]
                        chat = api(client.get_gria_chat, hk, last['id'])
                        if chat and chat.get('messages'):
                            st.session_state.gria_messages = chat['messages']
                            st.session_state.gria_county = chat.get('county_name') or county
                            st.session_state.gria_month = chat.get('month') or month
                            st.rerun()
                        else:
                            st.info('No messages in last saved chat.')
                    else:
                        st.info('No saved Gria chats — save one first.')

            # --- Beautiful WhatsApp-like bubbles (fixed HTML bug + premium styling) ---
            # Inject premium chat CSS once
            st.markdown("""
            <style>
            /* Chat container — WhatsApp web vibes */
            [data-testid="stChatMessage"] {border-radius: 18px !important; padding: 14px 16px !important; box-shadow: 0 2px 12px rgba(23,62,44,0.07) !important; border: 1px solid rgba(23,62,44,0.06) !important; margin-bottom: 6px !important; max-width: 88%;}
            [data-testid="stChatMessage"] div[data-testid="stMarkdownContainer"] p {margin: 0; line-height: 1.55;}
            /* User bubble — warm green, right */
            div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {background: linear-gradient(135deg, #dcf8c6 0%, #c8f0b8 100%) !important; margin-left: auto !important; border-bottom-right-radius: 4px !important;}
            /* Assistant bubble — clean white, left */
            div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]) {background: #ffffff !important; margin-right: auto !important; border-bottom-left-radius: 4px !important;}
            .gria-meta {color: #6b7d6f; font-size: 0.72em; font-weight: 600; letter-spacing: 0.04em; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;}
            .gria-meta .dot {width:7px; height:7px; border-radius:50%; background:#2b6842; display:inline-block; animation: pulse 2s infinite;}
            @keyframes pulse {0%,100%{opacity:1} 50%{opacity:0.5}}
            .gria-header {background: linear-gradient(135deg, #173e2c 0%, #2b6842 100%); border-radius: 16px; padding: 16px 18px; color: white; display:flex; align-items:center; gap:14px; margin-bottom:12px;}
            .gria-header img {width:44px; height:44px; border-radius:50%; border:2px solid rgba(255,255,255,0.3);}
            .gria-header h4 {margin:0; color:white; font-family: 'DM Serif Display', serif;}
            .gria-chips {display:flex; gap:8px; flex-wrap:wrap; margin:10px 0;}
            .gria-chip {background: white; border: 1px solid #d9e9d4; border-radius: 20px; padding: 6px 12px; font-size: 0.82em; color: #2b6842; cursor: pointer;}
            </style>
            """, unsafe_allow_html=True)

            # Gria premium header
            st.markdown(f"""
            <div class="gria-header">
                <img src="https://api.dicebear.com/7.x/bottts/svg?seed=Gria&backgroundColor=b6e3f4" alt="Gria"/>
                <div>
                    <h4>🌿 Gria — AgriShield AI</h4>
                    <div style="font-size:0.85em; opacity:0.9;">Online · remembers history · {county} · {month} · {len(st.session_state.gria_messages)} messages</div>
                </div>
                <div style="margin-left:auto; text-align:right; font-size:0.78em; opacity:0.85;">⚡ Mistral-large-4<br>90s timeout</div>
            </div>
            """, unsafe_allow_html=True)

            # Quick chips — tap to ask
            chip_cols = st.columns(4)
            chips = ["Explain this score 🧠", "What should I do? 🌱", "Compare counties 📊", "Who built you? 👨‍💻"]
            for idx, label in enumerate(chips):
                if chip_cols[idx].button(label, key=f"gria_chip_{idx}", use_container_width=True):
                    st.session_state.gria_messages.append({"role": "user", "content": label, "county": county, "month": month})
                    st.rerun()

            # Render history as bubbles with proper HTML
            for m in st.session_state.gria_messages:
                with st.chat_message(m['role'], avatar="🧑‍🌾" if m['role']=="user" else "🌿"):
                    if m.get('county'):
                        st.markdown(f"<div class='gria-meta'><span class='dot'></span>{m.get('county')} · {m.get('month')} · {m.get('mode','ai') if m['role']=='assistant' else 'you'}</div>", unsafe_allow_html=True)
                    st.markdown(m['content'])

            # One-shot document toggle above input
            use_document = False
            if st.session_state.get('document'):
                use_document = st.checkbox('📎 Share reviewed document with next message (one-shot)', value=False, key='gria_share_doc')

            # Premium chat input
            if prompt := st.chat_input('Ask Gria — e.g. What does Busia 2025-12 score mean? Try "Who created AgriShield?"', max_chars=4000):
                st.session_state.gria_messages.append({"role": "user", "content": prompt, "county": county, "month": month})
                with st.chat_message('user', avatar="🧑‍🌾"):
                    st.markdown(f"<div class='gria-meta'>{county} · {month} · you</div>", unsafe_allow_html=True)
                    st.markdown(prompt)
                history_for_api = [{"role": h["role"], "content": h["content"]} for h in st.session_state.gria_messages[:-1]][-20:]
                with st.chat_message('assistant', avatar="🌿"):
                    with st.spinner('Gria is typing…'):
                        resp = api(client.chat, prompt, county, month,
                                   st.session_state.document['text'] if use_document and st.session_state.get('document') else None,
                                   st.session_state.document['file_name'] if use_document and st.session_state.get('document') else None,
                                   history=history_for_api if history_for_api else None)
                    if resp:
                        st.markdown(f"<div class='gria-meta'><span class='dot'></span>{county} · {month} · {resp.get('mode','ai')}</div>", unsafe_allow_html=True)
                        st.markdown(resp['reply'])
                        st.caption('🤖 AI-generated — verify with local extension officer' if resp.get('mode')=='ai' else '📋 Summary mode — factual backend, not AI')
                        st.session_state.gria_messages.append({"role": "assistant", "content": resp['reply'], "county": county, "month": month, "mode": resp.get('mode')})
                        if use_document:
                            st.session_state.document = None
                        st.rerun()
                    else:
                        st.error('No reply — check backend terminal for Gria catalog/mode')
            elif not st.session_state.gria_messages:
                st.info('👋 Hi! I’m **Gria**, built by **Edusei Mikel Lisamba & Team AgriShield**. Ask me about any county’s score, say "Who created AgriShield?", or tap a chip above. I remember our chat like WhatsApp — switch county/month anytime!')
