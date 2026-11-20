"""Recompute the training-baseline low-NDVI proxy label, not agricultural losses."""
from data_pipeline.scripts.experiment import build_experiment, load_panel


def synthesize_targets(panel=None, train_end=2021):
    df = build_experiment(load_panel() if panel is None else panel, train_end=train_end)
    return df[df.year <= train_end].copy(), df[df.year > train_end].copy()
