"""Predict from a complete, user-supplied feature vector, without fallback data."""
import csv
import io
import math
import json

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from xml.sax.saxutils import escape

from core.auth import get_current_user
from core.config import settings
from schemas.manual_prediction import ManualPredictionRequest, RawObservationRequest, CompareInputsRequest
from seed_counties import COUNTY_METADATA, normalize_county_name
from services.prediction_service import get_engine, ARTIFACT_DIR

router = APIRouter(prefix="/predictions", tags=["User observations"])

# The ordering here follows the saved model's feature_columns.json.
FEATURES = [
    {"key": "ndvi_lag1", "label": "Vegetation greenness last month", "unit": "NDVI", "group": "Vegetation", "help": "Satellite NDVI for the month before the selected month (−1 to 1)."},
    {"key": "ndvi_lag3", "label": "Vegetation greenness three months ago", "unit": "NDVI", "group": "Vegetation", "help": "Satellite NDVI from three months before the selected month."},
    {"key": "ndvi_roll3_mean", "label": "Average greenness over the previous 3 months", "unit": "NDVI", "group": "Vegetation", "help": "Mean NDVI for the three months before the selected month."},
    {"key": "ndvi_roll3_std", "label": "Variation in greenness over the previous 3 months", "unit": "NDVI", "group": "Vegetation", "help": "Sample standard deviation of NDVI over the previous three months."},
    {"key": "ndvi_anomaly", "label": "Last month's greenness compared with normal", "unit": "NDVI difference", "group": "Vegetation", "help": "Last month's NDVI minus the county's historical mean NDVI, using the model's training baseline."},
    {"key": "temp_mean_c", "label": "Average temperature this month", "unit": "°C", "group": "Weather & soil", "help": "Monthly mean temperature in degrees Celsius, matching the training source."},
    {"key": "rainfall_mm", "label": "Rainfall this month", "unit": "mm", "group": "Weather & soil", "help": "Total rainfall for the selected month in millimetres."},
    {"key": "soil_moisture", "label": "Average soil moisture this month", "unit": "m³/m³", "group": "Weather & soil", "help": "Monthly mean volumetric soil moisture as a fraction between 0 and 1, matching the training source."},
    {"key": "rainfall_anomaly", "label": "Rainfall compared with normal", "unit": "mm difference", "group": "Weather & soil", "help": "This month's rainfall minus the county's training-period average for the same calendar month, in mm."},
    {"key": "rain_3m_sum", "label": "Total rainfall over 3 months", "unit": "mm", "group": "Weather & soil", "help": "Rainfall in the selected month plus the two preceding months."},
    {"key": "forage_dryness_index", "label": "Forage dryness indicator", "unit": "index", "group": "Weather & soil", "help": "The engineered indicator used in training: 0.5 × positive NDVI drop in historical standard deviations + 0.5 × max(0, 0.45 − soil moisture) × (temperature / 25)."},
    {"key": "farming_ratio", "label": "Share of households farming", "unit": "fraction", "group": "County livelihoods", "help": "Farming households divided by total households plus one, matching training. Enter a fraction, not a percentage."},
    {"key": "livestock_share", "label": "Share of crop and livestock activities that are livestock", "unit": "fraction", "group": "County livelihoods", "help": "Livestock production households divided by crop plus livestock production households plus one."},
    {"key": "irrigation_ratio", "label": "Share of farming households using irrigation", "unit": "fraction", "group": "County livelihoods", "help": "Irrigation households divided by farming households plus one."},
]


def score_observation(req: ManualPredictionRequest) -> dict:
    county = normalize_county_name(req.county_name)
    if county not in COUNTY_METADATA:
        raise HTTPException(status_code=422, detail="Please select a recognised Kenyan county.")
    engine = get_engine()
    if engine.model is None or not engine.feature_cols:
        raise HTTPException(status_code=503, detail="The trained model is unavailable. No substitute score has been generated.")
    month = int(req.period[5:7])
    vector = req.model_dump(exclude={"county_name", "period"})
    vector["month_sin"] = round(math.sin(2 * math.pi * month / 12.0), 6)
    vector["month_cos"] = round(math.cos(2 * math.pi * month / 12.0), 6)
    return score_vector(county, req.period, vector)


def score_vector(county: str, period: str, vector: dict) -> dict:
    """Score an already validated user vector or an exact packaged historical row."""
    engine = get_engine()
    if engine.model is None or not engine.feature_cols:
        raise HTTPException(status_code=503, detail="The trained model is unavailable. No substitute score has been generated.")
    if set(vector) != set(engine.feature_cols):
        raise HTTPException(status_code=503, detail="The loaded model's feature contract does not match this form.")
    try:
        frame = pd.DataFrame([[vector[c] for c in engine.feature_cols]], columns=engine.feature_cols)
        probability = float(engine.model.predict_proba(frame)[0][1])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("Model returned an invalid value")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The model could not evaluate these inputs. No substitute score has been generated.") from exc
    contributions = None
    try:
        if hasattr(engine.model, 'booster_'):
            raw = engine.model.booster_.predict(frame, pred_contrib=True)[0]
            if len(raw) == len(engine.feature_cols) + 1 and all(math.isfinite(float(v)) for v in raw):
                labels = {item['key']: item['label'] for item in FEATURES}
                contributions = {'baseline_log_odds': float(raw[-1]),
                                 'values': sorted([{'feature': name, 'label': labels.get(name, 'Time of year (sine)' if name == 'month_sin' else 'Time of year (cosine)' if name == 'month_cos' else name),
                                                    'value': float(vector[name]), 'contribution': float(value)}
                                                   for name, value in zip(engine.feature_cols, raw[:-1])],
                                                  key=lambda item: abs(item['contribution']), reverse=True)}
    except Exception:
        # Explanation failure must not become invented zero contributions.
        contributions = None
    range_warnings = []
    range_check = 'unavailable'
    try:
        reference = json.loads((ARTIFACT_DIR / 'training_feature_ranges.json').read_text())
        if reference['model_sha256'] == engine.model_sha256 and set(reference['ranges']) == set(engine.feature_cols):
            range_check = 'checked'
            labels = {item['key']: item['label'] for item in FEATURES}
            for key in engine.feature_cols:
                bounds = reference['ranges'][key]
                if not bounds['min'] <= vector[key] <= bounds['max']:
                    range_warnings.append({'feature': key, 'label': labels.get(key, 'Time of year'),
                                           'value': vector[key], 'training_min': bounds['min'], 'training_max': bounds['max']})
    except (OSError, KeyError, ValueError, TypeError):
        pass
    score = int(round(probability * 100))
    # Scores are uncalibrated model outputs; tiers are descriptive, not operational alerts.
    band = "Lower" if score < 25 else "Moderate" if score < 50 else "Elevated" if score < 75 else "High"
    return {
        "county_name": county, "period": period, "score": score,
        "model_probability": probability, "band": band, "model_used": engine.model_name,
        "features": {key: vector[key] for key in engine.feature_cols},
        "model_sha256": engine.model_sha256,
        "explanation": contributions,
        "training_range_check": range_check, "training_range_warnings": range_warnings,
        "meaning": "Model estimate of the training vegetation-stress proxy, not a confirmed crop loss or forage deficit. The score is not a calibrated probability or an operational warning.",
    }


@router.get("/counties")
def counties(user: dict = Depends(get_current_user)):
    return sorted(COUNTY_METADATA)


@router.get("/input-schema")
def input_schema(user: dict = Depends(get_current_user)):
    fields = ManualPredictionRequest.model_json_schema()["properties"]
    return {"features": [{**feature, "minimum": fields[feature["key"]].get("minimum"), "maximum": fields[feature["key"]].get("maximum")} for feature in FEATURES],
            "derived": ["month_sin", "month_cos"],
            "csv_columns": ["county_name", "period"] + [item["key"] for item in FEATURES]}


@router.post("/from-inputs")
def predict_inputs(req: ManualPredictionRequest, user: dict = Depends(get_current_user)):
    return score_observation(req)


@router.post("/from-csv")
async def predict_csv(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")
    raw = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(raw) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The CSV file is too large.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("CSV headers must be present and unique.")
        rows = list(reader)
        if len(rows) != 1 or None in rows[0]:
            raise ValueError("Provide exactly one complete observation row.")
        req = ManualPredictionRequest.model_validate(rows[0])
    except (UnicodeDecodeError, csv.Error, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not read the observation: {exc}") from exc
    return score_observation(req)


def render_assessment_pdf(result: dict) -> io.BytesIO:
    """Render a branded report from a stored result; never run inference here."""
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.graphics.shapes import Drawing, String, Line, PolyLine, Circle

    green = colors.HexColor('#173e2c')
    medium = colors.HexColor('#2b6842')
    pale = colors.HexColor('#edf4e9')
    gold = colors.HexColor('#ca9b4c')
    styles = getSampleStyleSheet()
    body = ParagraphStyle('AgriBody', parent=styles['BodyText'], fontSize=9, leading=14, textColor=colors.HexColor('#263d30'), spaceAfter=8)
    small = ParagraphStyle('AgriSmall', parent=body, fontSize=8, leading=11)
    title = ParagraphStyle('AgriTitle', parent=styles['Title'], fontSize=22, leading=26, alignment=TA_LEFT, textColor=green, spaceAfter=12)
    heading = ParagraphStyle('AgriHeading', parent=styles['Heading2'], textColor=green, fontSize=13, spaceBefore=14, spaceAfter=7)

    def paragraph(text, style=body):
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)

    def header_footer(canvas, doc):
        w, h = A4
        canvas.saveState()
        canvas.setFillColor(green)
        canvas.rect(0, h - 58, w, 58, fill=1, stroke=0)
        # An original vector leaf-and-shield emblem and wordmark, not an external logo asset.
        canvas.setFillColor(colors.HexColor('#b8dc9c'))
        canvas.circle(40, h - 29, 15, fill=1, stroke=0)
        canvas.setFillColor(green)
        path = canvas.beginPath()
        path.moveTo(33, h - 31); path.curveTo(35, h - 20, 48, h - 20, 47, h - 25)
        path.curveTo(46, h - 33, 39, h - 38, 33, h - 31); canvas.drawPath(path, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor('#b8dc9c'))
        canvas.line(36, h - 34, 44, h - 25)
        canvas.setFillColor(colors.white); canvas.setFont('Helvetica-Bold', 15)
        canvas.drawString(64, h - 26, 'AgriShield')
        canvas.setFont('Helvetica', 8); canvas.drawString(65, h - 40, 'AGRICULTURAL INTELLIGENCE')
        canvas.setFillColor(colors.HexColor('#6a7d6d')); canvas.setFont('Helvetica', 8)
        canvas.drawString(36, 26, 'RESEARCH PROTOTYPE  |  Verify decisions with local experts')
        canvas.drawRightString(w - 36, 26, f'{doc.page}')
        canvas.restoreState()

    buffer = io.BytesIO()
    story = [paragraph('Vegetation assessment', title),
             paragraph(f"{result['county_name']} County  |  Observation: {result['period']}  |  Score: {result['score']}/100 ({result['band']})", heading),
             paragraph(result['meaning']),
             paragraph(result.get('data_source', 'User-provided inputs. Source and freshness have not been independently verified.'), small)]
    analysis = result.get('report_analysis')
    if analysis:
        label = 'Gria AI analysis' if analysis['mode'] == 'ai' else 'Evidence summary (AI unavailable)'
        story.append(paragraph(label, heading))
        story.append(paragraph('AI text may contain mistakes; verify it before acting.' if analysis['mode'] == 'ai' else 'This factual summary was generated without AI.', small))
        # Split into paragraphs so long provider responses can paginate.
        for part in analysis['text'].split('\n\n'):
            if part.strip():
                story.append(paragraph(part.strip().replace('**', '')))
    context = result.get('report_context') or {}
    if context.get('national'):
        national = context['national']
        story += [paragraph('County context', heading), paragraph(f"{national['counties_available']} counties have observations in {national['period']}; their unweighted average score is {national['mean_score']}/100. It is not a measure of regional impact.")]
    trend = context.get('trend') or []
    if len(trend) >= 2:
        story.append(paragraph('Historical score trend', heading))
        chart = Drawing(477, 130)
        chart.add(Line(40, 20, 460, 20, strokeColor=colors.HexColor('#b9cbbb')))
        chart.add(Line(40, 20, 40, 110, strokeColor=colors.HexColor('#b9cbbb')))
        chart.add(String(4, 18, '0', fontSize=8, fillColor=green))
        chart.add(String(4, 106, '100', fontSize=8, fillColor=green))
        points = []
        for i, row in enumerate(trend):
            x = 40 + i * 420 / (len(trend) - 1)
            y = 20 + row['score'] * .9
            points.extend([x, y])
            chart.add(Circle(x, y, 2, fillColor=medium, strokeColor=medium))
        chart.add(PolyLine(points, strokeColor=medium, strokeWidth=2))
        chart.add(String(40, 5, trend[0]['period'], fontSize=8, fillColor=green))
        chart.add(String(420, 5, trend[-1]['period'], fontSize=8, fillColor=green))
        story.append(chart)
        story.append(paragraph('Model scores from stored historical features; not a forecast.', small))
    explanation = result.get('explanation')
    story.append(paragraph('What influenced the model', heading))
    if explanation:
        story.append(paragraph('SHAP contributions describe model associations relative to its baseline; they are not causes or percentage-point changes.', small))
        rows = [['Input', 'Value', 'Model contribution']] + [[item['label'], f"{item['value']:.4g}", f"{item['contribution']:+.3f}"] for item in explanation['values'][:8]]
        table = Table(rows, colWidths=[300, 72, 105], repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), pale), ('TEXTCOLOR', (0, 0), (-1, 0), green), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('LINEBELOW', (0, 0), (-1, -1), .25, colors.HexColor('#dbe6d8'))]))
        story.append(table)
    else:
        story.append(paragraph('Model contributions were unavailable.'))
    warnings = result.get('training_range_warnings', [])
    if warnings:
        story.append(paragraph('Outside training ranges: ' + ', '.join(item['label'] for item in warnings) + '. The model may be less reliable.', small))
    elif result.get('training_range_check') != 'checked':
        story.append(paragraph('Training-range checks are unavailable for this model.', small))
    else:
        story.append(paragraph('Inputs are within individual training ranges; this does not guarantee accuracy.', small))
    story.append(paragraph('Model inputs and provenance', heading))
    labels = {f['key']: f['label'] for f in FEATURES}
    rows = [['Model input', 'Value']] + [[labels.get(k, k), f'{v:.6g}'] for k, v in result['features'].items()]
    table = Table(rows, colWidths=[360, 117], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), pale), ('TEXTCOLOR', (0, 0), (-1, 0), green), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LINEBELOW', (0, 0), (-1, -1), .25, colors.HexColor('#dbe6d8'))]))
    story.append(table)
    story.append(Spacer(1, 10))
    story.append(paragraph(f"Model: {result['model_used']} | SHA-256: {result.get('model_sha256') or 'not available'}", small))
    story.append(paragraph(f"Report snapshot created (UTC): {result.get('snapshot_created_at') or 'not saved'}", small))
    story.append(paragraph('This is a research proxy, not a live forecast, confirmed crop loss or forage deficit, calibrated probability, or official warning.', small))
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=78, bottomMargin=48, title='AgriShield vegetation assessment').build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    buffer.seek(0)
    return buffer


@router.post("/inputs-pdf")
def inputs_pdf(req: ManualPredictionRequest, user: dict = Depends(get_current_user)):
    buffer = render_assessment_pdf(score_observation(req))
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=agrishield-observation.pdf"})

@router.get("/historical-months")
def historical_months(user: dict = Depends(get_current_user)):
    """Return only periods actually present in the packaged historical dataset."""
    return get_engine().available_months


@router.get("/historical-observations")
def historical_observations(month: str, user: dict = Depends(get_current_user)):
    engine = get_engine()
    if month not in engine.available_months:
        raise HTTPException(status_code=404, detail="No historical dataset is available for this period.")
    if engine.model is None or not engine.feature_cols:
        raise HTTPException(status_code=503, detail="The trained model is unavailable.")
    counties, vectors = [], []
    for county, history in sorted(engine.county_history.items()):
        rows = history[history["year_month"].astype(str) == month]
        if rows.empty or any(c not in rows.columns or pd.isna(rows.iloc[-1][c]) for c in engine.feature_cols):
            continue
        counties.append(county)
        vectors.append([float(rows.iloc[-1][c]) for c in engine.feature_cols])
    if not vectors:
        raise HTTPException(status_code=404, detail="No complete historical observations are available for this period.")
    try:
        probabilities = engine.model.predict_proba(pd.DataFrame(vectors, columns=engine.feature_cols))[:, 1]
        if any(not math.isfinite(float(v)) or not 0 <= float(v) <= 1 for v in probabilities):
            raise ValueError("Invalid model output")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Historical observations could not be scored.") from exc
    result = []
    for county, probability in zip(counties, probabilities):
        score = int(round(float(probability) * 100))
        result.append({"county": county, "region": COUNTY_METADATA.get(county, {}).get("region"),
                       "score": score, "band": "Lower" if score < 25 else "Moderate" if score < 50 else "Elevated" if score < 75 else "High"})
    return {"period": month, "model_used": engine.model_name, "observations": result}

@router.get('/historical-detail')
def historical_detail(county_name: str, month: str, user: dict = Depends(get_current_user)):
    """Score the exact stored county-month feature row, including model contributions."""
    engine = get_engine()
    county = normalize_county_name(county_name)
    history = engine.county_history.get(county)
    if history is None or county not in COUNTY_METADATA:
        raise HTTPException(status_code=404, detail='No historical data is available for this county.')
    rows = history[history['year_month'].astype(str) == month]
    if rows.empty:
        raise HTTPException(status_code=404, detail='No historical data is available for this county and period.')
    if engine.model is None or not engine.feature_cols:
        raise HTTPException(status_code=503, detail='The trained model is unavailable.')
    row = rows.iloc[-1]
    if any(col not in row.index or pd.isna(row[col]) for col in engine.feature_cols):
        raise HTTPException(status_code=503, detail='Historical features are incomplete for this period.')
    try:
        vector = {col: float(row[col]) for col in engine.feature_cols}
        if not all(math.isfinite(value) for value in vector.values()):
            raise ValueError('Non-finite historical value')
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail='Historical features are invalid for this period.') from exc
    result = score_vector(county, month, vector)
    result['data_source'] = 'Packaged historical county-month dataset; not a live feed.'
    return result


@router.post("/from-measurements")
def predict_measurements(req: RawObservationRequest, user: dict = Depends(get_current_user)):
    """Build model features using the exact transformations in the training notebook."""
    import statistics
    vegetation = [req.ndvi_lag1, req.ndvi_lag2, req.ndvi_lag3]
    dry_soil = round(max(0.0, 0.45 - req.soil_moisture), 4)
    ndvi_drop = max(0.0, req.ndvi_historical_mean - req.ndvi_lag1) / (req.ndvi_historical_std + 1e-6)
    vector = {
        "county_name": req.county_name, "period": req.period,
        "rainfall_mm": req.rainfall_mm,
        "rain_3m_sum": round(req.rainfall_mm + req.rain_previous_1 + req.rain_previous_2, 4),
        "rainfall_anomaly": round(req.rainfall_mm - req.rain_normal, 4),
        "temp_mean_c": req.temp_mean_c, "soil_moisture": req.soil_moisture,
        "ndvi_lag1": req.ndvi_lag1, "ndvi_lag3": req.ndvi_lag3,
        "ndvi_roll3_mean": statistics.mean(vegetation),
        "ndvi_roll3_std": statistics.stdev(vegetation),
        "ndvi_anomaly": round(req.ndvi_lag1 - req.ndvi_historical_mean, 6),
        "forage_dryness_index": round(0.5 * ndvi_drop + 0.5 * dry_soil * (req.temp_mean_c / 25.0), 4),
        "farming_ratio": round(req.farming_households / (req.total_households + 1.0), 4),
        "livestock_share": round(req.livestock_households / (req.crop_households + req.livestock_households + 1.0), 4),
        "irrigation_ratio": round(req.irrigation_households / (req.farming_households + 1.0), 4),
    }
    try:
        validated = ManualPredictionRequest.model_validate(vector)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"The measurements produce model inputs outside the supported ranges: {exc}") from exc
    result = score_observation(validated)
    result['measurements'] = req.model_dump(exclude={'county_name', 'period'})
    return result

@router.get('/historical-trends')
def historical_trends(county_name: str, through: str, user: dict = Depends(get_current_user)):
    """Score up to twelve actual historical feature rows through the selected month."""
    engine = get_engine()
    county = normalize_county_name(county_name)
    history = engine.county_history.get(county)
    if history is None or through not in set(history['year_month'].astype(str)):
        raise HTTPException(status_code=404, detail='No historical data is available for this county and period.')
    if engine.model is None or not engine.feature_cols:
        raise HTTPException(status_code=503, detail='The trained model is unavailable.')
    rows = history[history['year_month'].astype(str) <= through].sort_values('year_month').tail(12)
    if any(col not in rows.columns for col in engine.feature_cols) or rows[engine.feature_cols].isna().any().any():
        raise HTTPException(status_code=503, detail='Historical features are incomplete for this period.')
    try:
        scores = engine.model.predict_proba(rows[engine.feature_cols])[:, 1]
        if any(not math.isfinite(float(v)) or not 0 <= float(v) <= 1 for v in scores):
            raise ValueError('Invalid model output')
    except Exception as exc:
        raise HTTPException(status_code=503, detail='Historical observations could not be scored.') from exc
    return {'county_name': county, 'through': through, 'model_used': engine.model_name,
            'observations': [{'period': str(row['year_month']), 'score': int(round(float(score) * 100)),
                              'rainfall_mm': float(row['rainfall_mm']), 'ndvi_lag1': float(row['ndvi_lag1']),
                              'soil_moisture': float(row['soil_moisture'])}
                             for (_, row), score in zip(rows.iterrows(), scores)]}

@router.post('/compare-inputs')
def compare_inputs(req: CompareInputsRequest, user: dict = Depends(get_current_user)):
    baseline = score_observation(req.baseline)
    alternative = score_observation(req.alternative)
    if baseline['county_name'] != alternative['county_name'] or baseline['period'] != alternative['period']:
        raise HTTPException(status_code=422, detail='Both observations must use the same county and month.')
    return {'baseline': baseline, 'alternative': alternative,
            'score_delta': alternative['score'] - baseline['score'],
            'meaning': 'A what-if comparison of supplied inputs, not a forecast or a causal estimate.'}
