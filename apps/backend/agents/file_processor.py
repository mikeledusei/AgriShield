"""
File processor: reads, converts, and evaluates uploaded files (CSV, Excel, PDF, Word, Image)
against the LightGBM Champion Model (16-feature schema) and official county baseline.
"""
import io
import re
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import pdfplumber
from docx import Document
from PIL import Image

from core.config import settings
from schemas.pydantic_models import ModelInput, UploadResponse
from seed_counties import COUNTY_METADATA, normalize_county_name
from services import logging_service, prediction_service

COLUMN_ALIASES: Dict[str, List[str]] = {
    "county_name": ["county", "county_name", "name", "county name", "admin1", "location"],
    "month": ["month", "month_num", "target_month"],
    "rainfall_mm": [
        "rainfall_mm",
        "rainfall",
        "rain",
        "rainfall_sum",
        "precipitation",
        "precip_mm",
        "monthly_rainfall",
    ],
    "rain_3m_sum": ["rain_3m_sum", "rain_3m", "3m_rainfall", "cumulative_rainfall"],
    "rainfall_anomaly": [
        "rainfall_anomaly",
        "rainfall_anomaly_30d",
        "rain_anomaly",
        "rain anomaly",
    ],
    "temp_mean_c": [
        "temp_mean_c",
        "temperature_mean",
        "temperature",
        "temp",
        "temp_max",
        "temp_max_avg",
        "max_temp",
        "lst_mean",
    ],
    "soil_moisture": [
        "soil_moisture",
        "soil_moisture_mean",
        "volumetric_soil_water",
        "soil_water",
        "root_soil_moisture",
    ],
    "soil_moisture_deficit": [
        "soil_moisture_deficit",
        "moisture_deficit",
        "soil_deficit",
    ],
    "ndvi_lag1": [
        "ndvi_lag1",
        "ndvi_mean",
        "ndvi",
        "vegetation",
        "pasture",
        "ndvi_pasture_index",
        "pasture_index",
        "greenness",
    ],
    "ndvi_lag3": ["ndvi_lag3", "ndvi_3m_lag"],
    "ndvi_roll3_mean": ["ndvi_roll3_mean", "ndvi_rolling_mean", "ndvi_3m_mean"],
    "ndvi_roll3_std": ["ndvi_roll3_std", "ndvi_volatility", "ndvi_std"],
    "ndvi_anomaly": ["ndvi_anomaly", "vegetation_anomaly"],
    "forage_dryness_index": [
        "forage_dryness_index",
        "forage_dryness",
        "fdi",
        "pasture_dryness",
    ],
    "farming_ratio": ["farming_ratio", "farming_share"],
    "livestock_share": ["livestock_share", "livestock_ratio"],
    "irrigation_ratio": ["irrigation_ratio", "irrigation_share"],
}


def _match_column(columns: list, field: str):
    aliases = COLUMN_ALIASES.get(field, [field])
    for col in columns:
        if str(col).strip().lower() in aliases:
            return col
    return None


def _parse_tabular(file_bytes: bytes, file_ext: str) -> Tuple[Dict[str, Any], int]:
    if file_ext == "csv":
        df = pd.read_csv(io.BytesIO(file_bytes))
    else:
        df = pd.read_excel(io.BytesIO(file_bytes))

    row_count = len(df)
    extracted: Dict[str, Any] = {}
    if row_count == 0:
        return extracted, 0

    columns = list(df.columns)
    # Use the latest/last row if multiple time rows are uploaded for a county
    target_row = df.iloc[-1]

    county_col = _match_column(columns, "county_name")
    if county_col is not None and pd.notna(target_row[county_col]):
        extracted["county_name"] = normalize_county_name(str(target_row[county_col]))

    for field in COLUMN_ALIASES:
        if field == "county_name":
            continue
        col = _match_column(columns, field)
        if col is not None:
            series_num = pd.to_numeric(df[col], errors="coerce").dropna()
            if not series_num.empty:
                extracted[field] = float(series_num.iloc[-1])

    return extracted, row_count


def _extract_from_text(text: str) -> Dict[str, Any]:
    extracted: Dict[str, Any] = {}
    # Match any known Kenyan county mentioned in the text first
    lower_text = text.lower()
    for canonical in COUNTY_METADATA:
        if canonical.lower() in lower_text:
            extracted["county_name"] = canonical
            break

    if "county_name" not in extracted:
        county_match = re.search(
            r"county\s*[:\-]?\s*([A-Za-z][A-Za-z'\-\s]{1,28})",
            text,
            re.IGNORECASE,
        )
        if county_match:
            raw_c = county_match.group(1).splitlines()[0].strip()
            extracted["county_name"] = normalize_county_name(raw_c)

    patterns = {
        "rainfall_mm": r"rainfall(?:\s*\(mm\)|\s*mm)?\s*[:\-=]?\s*(\d+(?:\.\d+)?)",
        "rainfall_anomaly": r"rainfall\s*anomaly[^0-9\-]*(-?\d+(?:\.\d+)?)",
        "ndvi_lag1": r"ndvi[^0-9\-]*(0\.\d+)",
        "temp_mean_c": r"temp(?:erature)?[^0-9\-]*(\d+(?:\.\d+)?)",
        "soil_moisture": r"soil\s*moisture[^0-9\-]*(0\.\d+)",
        "soil_moisture_deficit": r"moisture\s*deficit[^0-9\-]*(\d+(?:\.\d+)?)",
        "forage_dryness_index": r"forage\s*dryness[^0-9\-]*(\d+(?:\.\d+)?)",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                extracted[field] = float(match.group(1))
            except ValueError:
                continue
    return extracted


def _parse_pdf(file_bytes: bytes) -> Dict[str, Any]:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return _extract_from_text(text)


def _parse_word(file_bytes: bytes) -> Dict[str, Any]:
    document = Document(io.BytesIO(file_bytes))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return _extract_from_text(text)


def _parse_image(file_bytes: bytes) -> Dict[str, Any]:
    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    pixels = np.array(image.resize((128, 128)))
    red = pixels[:, :, 0].mean()
    green = pixels[:, :, 1].mean()
    blue = pixels[:, :, 2].mean()
    green_ratio = green / (red + green + blue + 1e-6)
    ndvi_proxy = round(min(max((green_ratio - 0.28) * 2.1, 0.12), 0.80), 4)
    return {"ndvi_lag1": ndvi_proxy}


def _build_suggestions(
    county_name: str,
    upload_score: int,
    upload_level: str,
    base_score: int,
    base_level: str,
    converted: Dict[str, float],
    shap_items: List[Dict[str, Any]],
) -> List[str]:
    suggestions: List[str] = []
    delta = upload_score - base_score

    if delta >= 10:
        suggestions.append(
            f"Uploaded data indicates **{delta:+d} pts higher risk** ({upload_score}/100, {upload_level}) than {county_name}'s official baseline ({base_score}/100, {base_level})—trigger early field verification immediately."
        )
    elif delta <= -10:
        suggestions.append(
            f"Uploaded data shows **{abs(delta)} pts lower risk** ({upload_score}/100, {upload_level}) compared to {county_name}'s baseline ({base_score}/100, {base_level}), indicating localized moisture/pasture improvement."
        )
    else:
        suggestions.append(
            f"Uploaded field data closely aligns with {county_name}'s official LightGBM model baseline ({upload_score}/100 vs. {base_score}/100, {upload_level})."
        )

    rain_mm = converted.get("rainfall_mm", 65.0)
    rain_anom = converted.get("rainfall_anomaly", 0.0)
    soil_m = converted.get("soil_moisture", 0.25)
    fdi = converted.get("forage_dryness_index", 0.20)
    ndvi_val = converted.get("ndvi_lag1", 0.50)

    if rain_mm < 35.0 or rain_anom < -20.0:
        suggestions.append(
            f"**Crop Water Advisory:** Monthly rainfall ({rain_mm:.1f} mm, anomaly {rain_anom:+.1f} mm) is below crop requirements—recommend mulching, water harvesting, and drought-tolerant varieties (e.g., KAT B1 beans, DH04 maize)."
        )
    if fdi >= 0.40 or ndvi_val < 0.38:
        suggestions.append(
            f"**Livestock Forage Advisory:** Pasture greenness (NDVI {ndvi_val:.2f}) and Forage Dryness Index ({fdi:.2f}) signal rangeland depletion—activate hay/fodder supplementation and rotational grazing."
        )
    if soil_m < 0.20:
        suggestions.append(
            f"**Soil Moisture Alert:** Root-zone soil moisture ({soil_m:.2f} m³/m³) is critically low—avoid fertilizer top-dressing until soil moisture recovers above 0.25 m³/m³."
        )
    if shap_items:
        top = shap_items[0]
        suggestions.append(
            f"**Primary SHAP Model Driver:** Monitor **{top['label']}** (current value `{top['value']:g}`, SHAP impact `{top['shap_value']:+.2f}`) as the #1 lever influencing {county_name}'s forecast."
        )

    return suggestions


def process(file_name: str, file_ext: str, file_bytes: bytes) -> UploadResponse:
    extracted: Dict[str, Any] = {}
    row_count = 1

    if file_ext in ("csv", "xlsx", "xls"):
        extracted, row_count = _parse_tabular(file_bytes, file_ext)
        source_desc = f"tabular dataset ({row_count} row{'s' if row_count != 1 else ''})"
    elif file_ext == "pdf":
        extracted = _parse_pdf(file_bytes)
        source_desc = "PDF field report"
    elif file_ext == "docx":
        extracted = _parse_word(file_bytes)
        source_desc = "Word document"
    elif file_ext in ("png", "jpg", "jpeg"):
        extracted = _parse_image(file_bytes)
        source_desc = "canopy/pasture image (RGB greenness proxy)"
    else:
        source_desc = "uploaded file"

    raw_county = normalize_county_name(extracted.get("county_name"))
    target_county = raw_county if raw_county in COUNTY_METADATA else "Bungoma"
    display_county = raw_county if raw_county else f"{target_county} (Default Baseline)"

    engine = prediction_service.get_engine()

    # Convert extracted fields into the 16-feature Champion Model schema via forecast_future
    overrides: Dict[str, float] = {}
    for k in (
        "rainfall_mm",
        "rain_3m_sum",
        "rainfall_anomaly",
        "temp_mean_c",
        "soil_moisture",
        "ndvi_lag1",
        "ndvi_lag3",
        "ndvi_roll3_mean",
        "ndvi_roll3_std",
        "ndvi_anomaly",
        "forage_dryness_index",
        "farming_ratio",
        "livestock_share",
        "irrigation_ratio",
    ):
        if k in extracted and extracted[k] is not None:
            overrides[k] = float(extracted[k])

    # If user provided soil_moisture_deficit (0..100%) instead of volumetric soil_moisture (0..0.45), convert it
    if "soil_moisture" not in overrides and "soil_moisture_deficit" in extracted:
        def_val = float(extracted["soil_moisture_deficit"])
        if def_val > 1.0:
            overrides["soil_moisture"] = round(max(0.03, 0.45 - def_val / 100.0), 4)
        else:
            overrides["soil_moisture"] = round(max(0.03, 0.45 - def_val), 4)

    target_m = int(extracted.get("month", 2)) if "month" in extracted else 2
    forecast_res = engine.forecast_future(
        None,
        county_name=target_county,
        target_month=max(1, min(12, target_m)),
        auto_derive_indices=True,
        overrides=overrides,
    )

    baseline = forecast_res["baseline"]
    evaluated = forecast_res["forecast"]
    conv_features = evaluated.get("features") or {}
    shap_items = evaluated.get("shap_contributions") or []

    score = int(evaluated["risk_score"])
    level = str(evaluated["risk_level"])
    base_score = int(baseline["risk_score"])
    base_level = str(baseline["risk_level"])
    delta = score - base_score

    suggestions = _build_suggestions(
        target_county, score, level, base_score, base_level, conv_features, shap_items
    )

    comparison_narrative = (
        f"Gria converted your {source_desc} (`{file_name}`) into all 16 LightGBM Champion Model features for **{target_county} County**. "
        f"Your uploaded data produces a risk score of **{score}/100 ({level})** vs. the county's official baseline of **{base_score}/100 ({base_level})** "
        f"(a **{delta:+d} point** difference). Primary driver: **{evaluated.get('main_driver', 'N/A')}**."
    )

    logging_service.info(
        f"Processed upload '{file_name}' for {target_county} -> {score}% ({level}) [Baseline: {base_score}%]"
    )

    soil_def_pct = round(max(0.0, (0.45 - float(conv_features.get("soil_moisture", 0.25))) * 100.0), 2)
    model_input = ModelInput(
        county_name=display_county if raw_county else target_county,
        rainfall_anomaly_30d=round(float(conv_features.get("rainfall_anomaly", 0.0)), 2),
        ndvi_pasture_index=round(float(conv_features.get("ndvi_lag1", 0.5)), 4),
        temp_max_avg=round(float(conv_features.get("temp_mean_c", 25.0)), 2),
        soil_moisture_deficit=soil_def_pct,
    )

    return UploadResponse(
        file_name=file_name,
        file_type=file_ext,
        extracted_data=model_input,
        gria_summary=comparison_narrative,
        risk_score=float(score),
        risk_level=level,
        baseline_risk_score=float(base_score),
        baseline_risk_level=base_level,
        score_delta_vs_baseline=float(delta),
        model_used=evaluated.get("model_used", "lightgbm_v1"),
        main_driver=evaluated.get("main_driver"),
        converted_features=conv_features,
        shap_contributions=shap_items,
        suggestions=suggestions,
        comparison_narrative=comparison_narrative,
        row_count=row_count,
    )
