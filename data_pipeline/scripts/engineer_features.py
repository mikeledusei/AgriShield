"""Recompute the research feature matrix from a validated panel."""
from data_pipeline.scripts.experiment import build_experiment, load_panel


def engineer_features(panel=None, train_end=2021):
    """Return training and later rows with features fitted to the training period."""
    df = build_experiment(load_panel() if panel is None else panel, train_end=train_end)
    return df[df.year <= train_end].copy(), df[df.year > train_end].copy()
