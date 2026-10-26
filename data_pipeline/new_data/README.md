# AgriShield 2015–2025 Datasets (`data_pipeline/new_data/`)

This directory contains the complete **2015–2025** raw, cleaned canonical, geospatial, and feature-engineered machine learning datasets aligned with **`AgriShield Project Proposal: Chapters 1–3`** (**Table 3.1**, **Section 3.3.1–3.3.5**, **Table 3.3**, and **Section 3.4**).

---

## 1. Datasets by Proposal Domain (Table 3.1 — Data Sources, 2015–2025)

### A. Meteorological Domain (`Open-Meteo API` / `CHIRPS v2.0` / `ECMWF ERA5-Land`)
- **`Metrological Cleaned Data 2.csv`** (`raw/` & root) — `6,204` rows (`47` counties × `132` months, `2015-01` to `2025-12`):
  - Columns: `county, year_month, temperature_mean, rainfall_sum, soil_moisture_mean`
- **`Weather_FINAL.csv`** (`processed/` & root) — `6,204` rows (`2015` to `2025`):
  - Columns: `county, year, month, temperature_mean, rainfall_sum, soil_moisture_mean`
- **External Source Exports (`external_sources_2015_2025/`)**:
  - `CHIRPS_WFP_Rainfall_Kenya_2015_2025.csv` (Dekadal subnational rainfall & anomalies across Kenya's 47 counties, `2015–2025`)
  - `ERA5_Land_Soil_Moisture_Kenya_2015_2025.csv` (Monthly root-zone volumetric soil moisture `0–7 cm` & rainfall, `2015–2025`)
  - `MODIS_LST_Temperature_Kenya_2015_2025.csv` (Monthly mean temperature °C & NDVI, `2015–2025`)

### B. Livestock & Forage Domain (`NASA MODIS NDVI`)
- **`NDVI_cleaned.csv`** (`raw/` & root) — `6,204` rows (`47` counties × `132` months, `2015-01` to `2025-12`):
  - Columns: `county, year_month, ndvi_mean, ndvi_anomaly_pct`
- **`NDVI_FINAL.csv`** (`processed/` & root) — `6,204` rows (`2015` to `2025`):
  - Columns: `county, year, month, ndvi_mean`
- **`county_ndvi_stats.csv`** (`processed/` & root) — `47` rows:
  - Columns: `county, ndvi_25th_pct, ndvi_mean_hist, ndvi_std_hist` (computed strictly on the `2015–2023` training window to prevent data leakage)
- **External Source Export (`external_sources_2015_2025/`)**:
  - `NASA_MODIS_WFP_NDVI_Kenya_2015_2025.csv` (Dekadal NASA MODIS v6.1 NDVI & anomalies across Kenya's 47 counties, `2015–2025`)

### C. Demographic & Crop Production Domain (`KNBS Open Data` & `FAOSTAT`, 2015–2025)
- **`Demographic_Crop Data_cleaned.csv`** (`raw/` & root) & **`Demographic_Crop_Activity_FINAL.csv`** (`processed/` & root) — `47` rows (all 47 Kenyan counties from KNBS 2019 Census Volume IV Table 2.19):
  - Columns: `county, total, farming, crop_production, livestock_production, aquaculture, fishing, irrigation`
- **`Historic Crop Production_cleaned.csv`** (`raw/` & root) & **`Crop_Production_WIDE_FINAL.csv`** (`processed/` & root) — `32` agricultural commodity series × `11` years (`2015–2025`)
- **`Crop_Production_LONG_FINAL.csv`** (`processed/` & root) — `352` rows (`2015–2025`):
  - Columns: `Commodity, year, production_value`
- **External Source Exports (`external_sources_2015_2025/`)**:
  - `FAOSTAT_KNBS_Crop_Production_Kenya_2015_2025.csv`
  - `KNBS_2019_Census_Demographic_Crop_Livestock_47_Counties.csv`

### D. Geospatial Domain (`UNOCHA / IEBC COD-AB`)
- **`kenya_counties.geojson`** (`geospatial/` & root) — 47 Kenyan County Admin1 polygon boundaries
- **`kenya_county_crosswalk.csv`** (`geospatial/` & root) — 47 counties mapped to `knbs_code` and `pcode` (`KE001`–`KE047`)

---

## 2. Model-Ready Training & Testing Datasets for the 4 Models (Proposal Table 3.3)

| Dataset Filename | Temporal Coverage | Rows | Used by Models |
|---|---|---:|---|
| **`master_full_2015_2025.csv`** | `2015-01` to `2025-12` (Full 11 Years) | `6,204` | Unified target-synthesized county-month master table (`rainfall_anomaly` + `target_risk`) |
| **`master_train_2015_2023.csv`** *(alias: `master_train_2020_2023.csv`)* | `2015-01` to `2023-12` (Train Split) | `5,076` | Target synthesis & EDA training split |
| **`master_test_2024_2025.csv`** | `2024-01` to `2025-12` (Test Split) | `1,128` | Target synthesis & EDA testing split |
| **`features_full_unscaled_2015_2025.csv`** | `2015-04` to `2025-12` (Full 11 Years) | `6,063` | Full unscaled engineered feature matrix (18 features + `forage_dryness_index` + `target_risk`) |
| **`features_train_unscaled.csv`** | `2015-04` to `2023-12` (Train Split) | `4,935` | **Trains the 3 Decision Tree Ensemble Models**: **Random Forest**, **XGBoost**, and **LightGBM** |
| **`features_test_unscaled.csv`** | `2024-01` to `2025-12` (Test Split) | `1,128` | **Evaluates the 3 Decision Tree Ensemble Models**: **Random Forest**, **XGBoost**, and **LightGBM** |
| **`features_full_scaled_2015_2025.csv`** | `2015-04` to `2025-12` (Full 11 Years) | `6,063` | Full `StandardScaler`-normalized feature matrix |
| **`features_train_scaled.csv`** | `2015-04` to `2023-12` (Train Split) | `4,935` | **Trains Model 1 (Baseline)**: **Logistic Regression** |
| **`features_test_scaled.csv`** | `2024-01` to `2025-12` (Test Split) | `1,128` | **Evaluates Model 1 (Baseline)**: **Logistic Regression** |
