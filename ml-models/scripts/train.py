"""Train XGBoost champion model."""
import os
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from xgboost import XGBClassifier
from evaluate import evaluate


def train(X_train: pd.DataFrame, y_train: pd.Series) -> XGBClassifier:
    """Train XGBoost classifier."""
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="multi:softprob",
        num_class=4,
        eval_metric="mlogloss",
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def run_training_pipeline():
    """End-to-end training pipeline."""
    import os
    import joblib
    import pandas as pd
    from sklearn.model_selection import train_test_split

    train_data = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "data", "processed", "train_matrix.csv"))

    feature_cols = [c for c in train_data.columns if c not in ("county_name", "risk_label", "risk_score")]
    target_col = "risk_label"

    X = train_data[feature_cols]
    y = train_data[target_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = train(X_train, y_train)

    print("=== Evaluation ===")
    evaluate(model, X_test, y_test)

    model_path = os.path.join(os.path.dirname(__file__), "..", "models", "xgboost_agrishield_v1.joblib")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

    return model
