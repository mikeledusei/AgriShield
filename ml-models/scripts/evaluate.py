"""Evaluate ML model performance."""
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix, roc_auc_score,
)


def evaluate(model, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """Evaluate model and print metrics."""
    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision_macro": precision_score(y_test, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_test, y_pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y_test, y_pred, average="macro", zero_division=0),
    }

    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Precision (macro): {metrics['precision_macro']:.4f}")
    print(f"Recall (macro): {metrics['recall_macro']:.4f}")
    print(f"F1 (macro): {metrics['f1_macro']:.4f}")

    try:
        y_proba = model.predict_proba(X_test)
        auc = roc_auc_score(y_test, y_proba, multi_class="ovr", average="macro")
        metrics["auc_macro"] = auc
        print(f"AUC (macro): {auc:.4f}")
    except Exception:
        pass

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    return metrics


def compare_models(models: dict, X_test: pd.DataFrame, y_test: pd.Series) -> pd.DataFrame:
    """Compare multiple models."""
    results = []
    for name, model in models.items():
        metrics = evaluate(model, X_test, y_test)
        metrics["model"] = name
        results.append(metrics)
    return pd.DataFrame(results)
