# AgriShield ML Model Training & Evaluation Report (2015–2025)

## 1. Executive Summary
- **Dataset Coverage:** All **47 Kenyan Counties**, monthly from **January 2015 to December 2025** (`6,204` county-month records).
- **Chronological Split (Leakage-Free):**
  - **Training Set (`2015–2023`):** `5,076` county-months (`9` years).
  - **Unseen Holdout Test Set (`2024–2025`):** `1,128` county-months (`2` years).
- **Selected Champion Model:** **LightGBM** (`Accuracy = 94.06%`, `Recall = 100.00%`, `F1 = 0.5677`, `ROC-AUC = 0.9869`).

## 2. Holdout Test Set Performance (`2024–2025`, Unseen Data)

| Rank | Model | Accuracy | Precision | Recall | F1-Score | ROC-AUC |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | **LightGBM** | 0.9406 | 0.3964 | 1.0000 | 0.5677 | 0.9869 |
| 2 | **XGBoost** | 0.9344 | 0.3729 | 1.0000 | 0.5432 | 0.9884 |
| 3 | **Random Forest** | 0.9211 | 0.3308 | 1.0000 | 0.4972 | 0.9812 |
| 4 | **Logistic Regression** | 0.9034 | 0.2759 | 0.9091 | 0.4233 | 0.9685 |

## 3. Key Findings Aligned with Project Proposal (Table 3.3)
1. **Decision Tree Ensembles vs. Linear Baseline:** All three tree-based models (`LightGBM`, `XGBoost`, and `Random Forest`) achieved **`100.0%` Recall (`1.0000`)** on the unseen `2024–2025` test data, outperforming the `Logistic Regression` baseline (`Recall = 90.91%`, `F1 = 0.4233`).
2. **Top Ranking Models:** `LightGBM` achieved the highest overall Accuracy (`94.06%`) and F1-Score (`0.5677`), while `XGBoost` achieved the highest ROC-AUC (`0.9884`).
3. **Engineered Proposal Indicators:** Both the **30-Day Rainfall Anomaly Index (`rainfall_anomaly`)** and the **Forage Dryness Index (`forage_dryness_index`)** from Section 3.3.2 of the proposal were engineered without target leakage and saved in `feature_columns.json`.