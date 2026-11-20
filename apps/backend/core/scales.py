"""Single source of truth for the vegetation-stress score scale.

The model returns an uncalibrated probability which is presented as a 0-100 score.
Bands are descriptive labels for that score. They are not operational alert
levels, and the score is not a calibrated probability of crop loss.

The frontend mirrors this contract in ``apps/frontend/shared/scales.py``; a test
checks that both copies agree, so change them together.
"""

from typing import Final

#: Upper bound is exclusive: a score of 25 is "Moderate", not "Lower".
BAND_THRESHOLDS: Final[tuple[tuple[int, str], ...]] = (
    (25, "Lower"),
    (50, "Moderate"),
    (75, "Elevated"),
)

#: Highest band, reached when no earlier threshold matched.
TOP_BAND: Final[str] = "High"

#: Display order, lowest to highest.
BAND_ORDER: Final[tuple[str, ...]] = ("Lower", "Moderate", "Elevated", "High")

BAND_COLORS: Final[dict[str, str]] = {
    "Lower": "#8cb77d",
    "Moderate": "#d7bc70",
    "Elevated": "#ce8a54",
    "High": "#ac5841",
}


def band_for_score(score: float) -> str:
    """Return the descriptive band for a 0-100 score."""
    for upper_bound, label in BAND_THRESHOLDS:
        if score < upper_bound:
            return label
    return TOP_BAND


def band_color(band: str) -> str:
    """Return the display colour for a band, defaulting to the lowest band."""
    return BAND_COLORS.get(band, BAND_COLORS[BAND_ORDER[0]])


def score_and_band(probability: float) -> tuple[int, str]:
    """Convert a model probability into the integer score and its band."""
    score = int(round(probability * 100))
    return score, band_for_score(score)
