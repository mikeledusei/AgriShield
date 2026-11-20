"""Frontend copy of the backend score scale.

Mirrors ``apps/backend/core/scales.py``. The dashboard is a thin HTTP client, so
it cannot import the backend package; ``tests/test_scales.py`` asserts the two
definitions stay identical. Change both together.
"""

BAND_THRESHOLDS = ((25, "Lower"), (50, "Moderate"), (75, "Elevated"))
TOP_BAND = "High"
BAND_ORDER = ("Lower", "Moderate", "Elevated", "High")
BAND_COLORS = {
    "Lower": "#8cb77d",
    "Moderate": "#d7bc70",
    "Elevated": "#ce8a54",
    "High": "#ac5841",
}


def band_for_score(score):
    """Return the descriptive band for a 0-100 score."""
    for upper_bound, label in BAND_THRESHOLDS:
        if score < upper_bound:
            return label
    return TOP_BAND


def band_color(band):
    """Return the display colour for a band, defaulting to the lowest band."""
    return BAND_COLORS.get(band, BAND_COLORS[BAND_ORDER[0]])
