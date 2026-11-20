# Research runs

Recorded outputs of the research experiments, kept so numbers quoted in the docs can be
traced to a run. Each subdirectory is one dated run:

| Directory | Contents |
| --- | --- |
| `2026_11_20/` | NDVI drought-risk experiment: `metrics.json`, per-county and per-month metrics, predictions |
| `maize_2026_11_20/` | Maize yield experiment: `metrics.json`, `model_panel.csv`, predictions, and a README recording the method and limitations |

## Why the model binaries are not here

Fitted `.joblib` artifacts from research runs are **not tracked in Git**. They are large
(up to ~5.6 MB each, and a single run fits four models), they are reproducible from the
notebooks, and they are never loaded by the served application. `.gitignore` ignores
`*.joblib` generally.

The one exception is the deployed champion: `apps/backend/ml_artifacts/*.joblib` is
explicitly allowlisted, because the API loads those files at startup and a clone must be
able to serve predictions without a training run.

The metrics, predictions and reports — the parts that are small and actually cited — are
tracked alongside the run that produced them.

## Reproducing

- NDVI drought-risk experiment: run `ml-models/notebooks/` in order, `00` → `05`.
- Maize yield experiment: it has no notebook equivalent. Use the archived copy at
  `ml-models/legacy_reference/maize_outcome_experiment.py.txt`.

Read `docs/DATA_MODEL_CARD.md` before interpreting any of these numbers: the target is a
synthesized NDVI proxy, the 2024–2025 period has been examined before, and none of it is
an independent forecast.
