"""File processor: parses uploads and converts them into model features."""
import io
import re
import pandas as pd
import pdfplumber
from docx import Document
from PIL import Image
import numpy as np
from core.config import settings
from schemas.pydantic_models import ModelInput, UploadResponse
from services import prediction_service, logging_service

COLUMN_ALIASES = {
    "county_name": ["county", "county_name", "name", "county name"],
    "rainfall_anomaly_30d": ["rainfall", "rain", "rainfall_anomaly",
                              "rainfall_anomaly_30d", "precipitation", "rain anomaly"],
    "ndvi_pasture_index": ["ndvi", "vegetation", "pasture", "ndvi_pasture_index",
                            "pasture_index", "greenness"],
    "temp_max_avg": ["temperature", "temp", "temp_max", "temp_max_avg", "max_temp"],
    "soil_moisture_deficit": ["soil_moisture", "soil", "soil_moisture_deficit",
                               "moisture_deficit"],
}

def _merge_with_defaults(extracted: dict) -> dict:
    features = dict(settings.DEFAULT_FEATURES)
    for key in settings.FEATURE_COLUMNS:
        if key in extracted and extracted[key] is not None:
            features[key] = float(extracted[key])
    return features

def _match_column(columns: list, field: str):
    aliases = COLUMN_ALIASES[field]
    for col in columns:
        if str(col).strip().lower() in aliases:
            return col
    return None

def _parse_tabular(file_bytes: bytes, file_ext: str):
    if file_ext == "csv":
        df = pd.read_csv(io.BytesIO(file_bytes))
    else:
        df = pd.read_excel(io.BytesIO(file_bytes))

    extracted = {}
    columns = list(df.columns)

    county_col = _match_column(columns, "county_name")
    if county_col is not None and len(df) > 0:
        extracted["county_name"] = str(df[county_col].iloc[0])

    for field in settings.FEATURE_COLUMNS:
        col = _match_column(columns, field)
        if col is not None and len(df) > 0:
            value = pd.to_numeric(df[col].iloc[0], errors="coerce")
            if not pd.isna(value):
                extracted[field] = float(value)
    return extracted

def _extract_from_text(text: str) -> dict:
    extracted = {}
    county_match = re.search(r"county\s*[:\-]?\s*([A-Za-z][A-Za-z\s]+)", text, re.IGNORECASE)
    if county_match:
        extracted["county_name"] = county_match.group(1).strip()

    patterns = {
        "rainfall_anomaly_30d": r"rainfall[^0-9\-]*(-?\d+(?:\.\d+)?)",
        "ndvi_pasture_index": r"ndvi[^0-9\-]*(-?\d+(?:\.\d+)?)",
        "temp_max_avg": r"temp(?:erature)?[^0-9\-]*(-?\d+(?:\.\d+)?)",
        "soil_moisture_deficit": r"soil\s*moisture[^0-9\-]*(-?\d+(?:\.\d+)?)",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                extracted[field] = float(match.group(1))
            except ValueError:
                continue
    return extracted

def _parse_pdf(file_bytes: bytes) -> dict:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return _extract_from_text(text)

def _parse_word(file_bytes: bytes) -> dict:
    document = Document(io.BytesIO(file_bytes))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return _extract_from_text(text)

def _parse_image(file_bytes: bytes) -> dict:
    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    pixels = np.array(image.resize((128, 128)))
    red = pixels[:, :, 0].mean()
    green = pixels[:, :, 1].mean()
    blue = pixels[:, :, 2].mean()
    green_ratio = green / (red + green + blue + 1e-6)
    ndvi_proxy = round(min(max((green_ratio - 0.30) * 2.0, 0.10), 0.80), 2)
    return {"ndvi_pasture_index": ndvi_proxy}

def process(file_name: str, file_ext: str, file_bytes: bytes) -> UploadResponse:
    extracted = {}
    summary = ""

    if file_ext in ("csv", "xlsx", "xls"):
        extracted = _parse_tabular(file_bytes, file_ext)
        summary = "Gria read the spreadsheet and mapped its columns to model features."
    elif file_ext == "pdf":
        extracted = _parse_pdf(file_bytes)
        summary = "Gria extracted text from the PDF and identified agricultural indicators."
    elif file_ext == "docx":
        extracted = _parse_word(file_bytes)
        summary = "Gria read the Word document and identified agricultural indicators."
    elif file_ext in ("png", "jpg", "jpeg"):
        extracted = _parse_image(file_bytes)
        summary = "Gria analyzed the image and estimated vegetation greenness. Other indicators use regional defaults."
    else:
        summary = "Unsupported file structure. Regional defaults were used."

    county_name = extracted.get("county_name", "Unknown County")
    features = _merge_with_defaults(extracted)

    score = prediction_service.compute_score(features)
    level = prediction_service.get_risk_level(score)

    logging_service.info(f"Processed upload '{file_name}' -> {score}% ({level})")

    model_input = ModelInput(
        county_name=county_name,
        rainfall_anomaly_30d=features["rainfall_anomaly_30d"],
        ndvi_pasture_index=features["ndvi_pasture_index"],
        temp_max_avg=features["temp_max_avg"],
        soil_moisture_deficit=features["soil_moisture_deficit"],
    )

    return UploadResponse(
        file_name=file_name,
        file_type=file_ext,
        extracted_data=model_input,
        gria_summary=summary,
        risk_score=score,
        risk_level=level,
    )