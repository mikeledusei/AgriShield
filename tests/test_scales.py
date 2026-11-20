"""The dashboard mirrors the score scale; the two copies must not drift."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "apps" / "backend", ROOT / "apps" / "frontend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import core.scales as backend  # noqa: E402
import shared.scales as frontend  # noqa: E402


def test_thresholds_and_labels_match():
    assert frontend.BAND_THRESHOLDS == backend.BAND_THRESHOLDS
    assert frontend.TOP_BAND == backend.TOP_BAND
    assert frontend.BAND_ORDER == backend.BAND_ORDER
    assert frontend.BAND_COLORS == backend.BAND_COLORS


def test_frontend_bands_agree_across_the_range():
    for score in range(0, 101):
        assert frontend.band_for_score(score) == backend.band_for_score(score), score


def test_every_band_has_a_colour():
    for band in backend.BAND_ORDER:
        assert backend.band_color(band) == backend.BAND_COLORS[band]
    # Unknown bands fall back rather than raising in a chart.
    assert backend.band_color("unknown") == backend.BAND_COLORS[backend.BAND_ORDER[0]]
