"""County map rendering for the dashboard.

One builder serves every page so the map looks and behaves the same everywhere:
county boundaries, a coloured dot at each county's centre, the county name, and a
legend that follows the score-band palette.

Why ``Scattergeo`` with our own GeoJSON rather than a tile basemap
(``Scattermap``/``Choroplethmap``): a tile basemap needs outbound requests from the
*viewer's browser* to a tile provider. That fails behind firewalls and offline, and it
adds a third-party licence and attribution obligation to a research prototype. The
bundled simplification of the county boundaries needs no network, so the map always
renders. See ``docs/MAP_DESIGN.md``.
"""
from __future__ import annotations

import streamlit as st

from shared.map_data import load_geojson
from shared.scales import BAND_COLORS, BAND_ORDER

# Colours for a value scale that is not a score band (reported yields, weather).
VALUE_SCALE = [[0.0, '#e9f0e2'], [0.25, '#c3d8a8'], [0.5, '#e8d79a'], [0.75, '#d29a63'], [1.0, '#a9553d']]

SILHOUETTE = '#eef3ea'
BOUNDARY = '#9fb3a0'
LABEL_INK = '#16291d'
CONNECTOR = 'rgba(120,140,122,0.55)'

# Label geometry, in degrees, calibrated for the rendered chart (see docs/MAP_DESIGN.md).
# The map is ~50 px per degree at the default height, so a 7.8 px glyph is ~0.09 deg wide.
CHAR_WIDTH = 0.083
LINE_HEIGHT = 0.17
LABEL_PAD = 0.06
DOT_HALF_WIDTH = 0.09
DOT_HALF_HEIGHT = 0.075
# The map's own data extent is 33.91..41.90 x -4.65..5.47; the extra margin on the west
# gives crowded counties somewhere to put their name without covering a neighbour.
BOUNDS = (33.25, -5.05, 42.05, 5.62)
LEADER_THRESHOLD = 0.30


def _country_trace(geo: dict, *, show_boundaries: bool = True):
    """The county polygons as a flat land layer under the markers."""
    import plotly.graph_objects as go

    return go.Choropleth(
        geojson=geo,
        locations=[(feature.get('properties') or {}).get('county') for feature in geo.get('features', [])],
        z=[0] * len(geo.get('features', [])),
        featureidkey='properties.county',
        colorscale=[[0, SILHOUETTE], [1, SILHOUETTE]],
        showscale=False,
        marker_line_color=BOUNDARY if show_boundaries else SILHOUETTE,
        marker_line_width=0.7 if show_boundaries else 0,
        hoverinfo='skip',
        name='Kenya',
    )


def legend_scores() -> None:
    """Explain the band palette once, under the map."""
    st.markdown(
        '<div class="map-legend">'
        + ''.join(
            f'<span><i style="background:{BAND_COLORS[band]}"></i>{band}</span>'
            for band in BAND_ORDER
        )
        + '<span class="muted">Lower &lt; 25 · Moderate 25–49 · Elevated 50–74 · High ≥ 75 (score / 100)</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def _wrap(name: str) -> list[str]:
    """Split long county names so the label is never wider than ~0.8 degrees.

    "Elgeyo-Marakwet" at 15 characters is wider than several counties side by side;
    two short lines fit where one long line cannot.
    """
    if len(name) <= 10 or '-' not in name and ' ' not in name:
        return [name]
    separator = '-' if '-' in name else ' '
    head, _, tail = name.partition(separator)
    if not tail or '-' in tail:
        return [name]
    return [head, tail]


def _plan_labels(rows, *, max_distance: float = 1.7) -> tuple[list[dict], list[tuple[float, float, float, float]]]:
    """Decide where each county name goes, and which need a leader line.

    Central and western Kenya pack 20+ counties into two degrees of longitude, which is
    narrower than the names themselves. A name is tried in eight directions around its
    dot and accepted only if it overlaps neither another name, another dot, nor the map
    edge. The dot a label belongs to is excluded from that test — the gap already clears
    it — otherwise every label would be rejected by its own marker.
    """
    label_boxes: list[tuple[float, float, float, float]] = []
    # Every marker position is known before placement starts. Registering them all first
    # means a label cannot later be landed on by a dot from a county processed afterwards.
    dot_boxes: list[tuple[str, tuple[float, float, float, float]]] = [
        (
            row['county'],
            (
                row['longitude'] - DOT_HALF_WIDTH, row['latitude'] - DOT_HALF_HEIGHT,
                row['longitude'] + DOT_HALF_WIDTH, row['latitude'] + DOT_HALF_HEIGHT,
            ),
        )
        for row in rows
    ]
    annotations: list[dict] = []
    connectors: list[tuple[float, float, float, float]] = []

    # Text metrics differ slightly between the browser and these estimates, so boxes are
    # inflated before testing: a near-miss in the model would be an overlap on screen.
    margin = 0.09

    def overlaps(box, *, own: str) -> bool:
        if box[0] < BOUNDS[0] or box[1] < BOUNDS[1] or box[2] > BOUNDS[2] or box[3] > BOUNDS[3]:
            return True
        padded = (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)
        for other in label_boxes:
            if not (padded[2] < other[0] or padded[0] > other[2]
                    or padded[3] < other[1] or padded[1] > other[3]):
                return True
        for name, other in dot_boxes:
            if name == own:
                continue
            if not (padded[2] < other[0] or padded[0] > other[2]
                    or padded[3] < other[1] or padded[1] > other[3]):
                return True
        return False

    for row in sorted(rows, key=lambda item: item['county']):
        name = row['county']
        x, y = row['longitude'], row['latitude']

        lines = _wrap(name)
        width = CHAR_WIDTH * max(len(line) for line in lines) + 2 * LABEL_PAD
        height = LINE_HEIGHT * len(lines) + 2 * LABEL_PAD
        gap_x = width / 2 + DOT_HALF_WIDTH + margin + 0.02
        gap_y = height / 2 + DOT_HALF_HEIGHT + margin + 0.02

        found = None
        for distance in (1.0, 1.2, 1.45, 1.7, 2.0, 2.4, 2.9):
            if distance > max_distance:
                break
            for direction in ('top center', 'bottom center', 'middle right', 'middle left',
                              'top right', 'top left', 'bottom right', 'bottom left'):
                dx, dy = _OFFSETS[direction]
                centre_x = x + dx * gap_x * distance
                centre_y = y + dy * gap_y * distance
                box = (centre_x - width / 2, centre_y - height / 2,
                       centre_x + width / 2, centre_y + height / 2)
                if not overlaps(box, own=name):
                    found = (direction, centre_x, centre_y, box)
                    break
            if found:
                break
        if not found:
            continue

        direction, _, _, box = found
        label_boxes.append(box)
        anchor_x, anchor_y = _anchor_on_box(direction, box)
        annotations.append(dict(
            x=anchor_x, y=anchor_y, text='<br>'.join(lines), showarrow=False,
            font=dict(size=7.4, color=LABEL_INK, family='Inter, system-ui, sans-serif'),
            xanchor='left' if direction in ('middle right', 'top right', 'bottom right') else
                    'right' if direction in ('middle left', 'top left', 'bottom left') else 'center',
            yanchor='bottom' if direction.startswith('top') else
                    'top' if direction.startswith('bottom') else 'middle',
            bgcolor='rgba(246,248,243,0.70)', borderpad=1,
        ))
        # A leader line only when the name had to travel clear of its own county.
        anchor_centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        if ((anchor_centre[0] - x) ** 2 + (anchor_centre[1] - y) ** 2) ** 0.5 > LEADER_THRESHOLD:
            connectors.append((x, y, anchor_x, anchor_y))
    return annotations, connectors


_OFFSETS = {
    'top center': (0.0, 1.0), 'bottom center': (0.0, -1.0),
    'middle right': (1.0, 0.0), 'middle left': (-1.0, 0.0),
    'top right': (1.0, 1.0), 'top left': (-1.0, 1.0),
    'bottom right': (1.0, -1.0), 'bottom left': (-1.0, -1.0),
}


def _anchor_on_box(direction: str, box) -> tuple[float, float]:
    """The point on the label box nearest its dot, used as the text anchor.

    Plotly grows text *away* from its anchor in the direction named by ``yanchor`` /
    ``xanchor``: an annotation anchored ``bottom`` extends upwards. The anchor must
    therefore be the box edge that faces the dot, which is the opposite edge from the
    one the label sits on. Getting this backwards shifts every label by one line height
    and puts it on top of its neighbour, which is what the collision-free placement was
    meant to prevent.
    """
    left, bottom, right, top = box
    centre_x = (left + right) / 2
    centre_y = (bottom + top) / 2
    if direction == 'top center':
        return centre_x, bottom
    if direction == 'bottom center':
        return centre_x, top
    if direction == 'middle right':
        return left, centre_y
    if direction == 'middle left':
        return right, centre_y
    if direction == 'top right':
        return left, bottom
    if direction == 'top left':
        return right, bottom
    if direction == 'bottom right':
        return left, top
    return right, top


def county_map(
    rows,
    *,
    band_key: str | None = 'band',
    value_key: str | None = None,
    value_label: str = '',
    hover_lines=None,
    height: int = 560,
    show_scale: bool = True,
    label_all: bool = True,
):
    """Build the county map.

    ``rows`` is a list of dicts with ``county``, ``latitude`` and ``longitude``. When
    ``band_key`` is set the dot colour comes from the score-band palette; otherwise
    ``value_key`` drives a continuous scale. Counties without a row are counted in the
    legend so a gap is visible instead of silently missing.
    """
    import plotly.graph_objects as go

    geo = load_geojson()
    if geo is None:
        return None

    figure = go.Figure(_country_trace(geo))
    plotted = [row for row in rows if row.get('latitude') is not None]
    # Every county is named by default; a name that cannot sit beside its dot gets a thin
    # leader line to its own marker rather than covering a neighbour. ``label_all=False``
    # keeps only names that fit snugly, for viewers who prefer an uncluttered map.
    annotations, connectors = _plan_labels(plotted, max_distance=2.9 if label_all else 1.25)

    if connectors:
        figure.add_trace(go.Scattergeo(
            lon=[value for lon_a, _, lon_b, _ in connectors for value in (lon_a, lon_b, None)],
            lat=[value for _, lat_a, _, lat_b in connectors for value in (lat_a, lat_b, None)],
            mode='lines',
            line=dict(color=CONNECTOR, width=0.7),
            hoverinfo='skip',
            name='',
            showlegend=False,
        ))

    missing = [name for name in _geo_names(geo) if name not in {row['county'] for row in plotted}]

    if plotted:
        names = [row['county'] for row in plotted]
        custom = [hover_lines(row) if callable(hover_lines) else '' for row in plotted]
        marker_common = dict(
            size=[10 + 3 * float(row.get('emphasis', 0) or 0) for row in plotted],
            line=dict(width=1.1, color='#20362a'),
            opacity=0.95,
        )

        if band_key:
            # One trace per band keeps the dots crisp and lets the legend be exact.
            for band in BAND_ORDER:
                subset = [index for index, row in enumerate(plotted) if row.get(band_key) == band]
                if not subset:
                    continue
                figure.add_trace(go.Scattergeo(
                    lon=[plotted[index]['longitude'] for index in subset],
                    lat=[plotted[index]['latitude'] for index in subset],
                    text=[names[index] for index in subset],
                    customdata=[custom[index] for index in subset],
                    mode='markers',
                    marker=dict(color=BAND_COLORS[band], **marker_common),
                    name=band,
                    legendgroup=band,
                    hovertemplate='<b>%{text}</b><br>%{customdata}<extra></extra>',
                ))
        else:
            figure.add_trace(go.Scattergeo(
                lon=[row['longitude'] for row in plotted],
                lat=[row['latitude'] for row in plotted],
                text=names,
                customdata=custom,
                mode='markers',
                marker=dict(
                    color=[row.get(value_key) for row in plotted],
                    colorscale=VALUE_SCALE,
                    showscale=show_scale,
                    colorbar=dict(title=value_label, thickness=12, len=0.6, outlinewidth=0),
                    cmin=0,
                    **marker_common,
                ),
                name=value_label or 'Value',
                hovertemplate='<b>%{text}</b><br>%{customdata}<extra></extra>',
            ))

    if missing:
        figure.add_trace(go.Scattergeo(
            lon=[], lat=[], mode='markers',
            marker=dict(color=SILHOUETTE, size=10, line=dict(width=1, color=BOUNDARY)),
            name=f'Not scored ({len(missing)})',
            hoverinfo='skip',
        ))

    figure.update_geos(
        visible=False,
        showcountries=False,
        showland=False,
        showocean=False,
        # Kenya sits on the equator; a mild extent keeps it centred, upright and unclipped.
        projection_type='mercator',
        lataxis_range=[-5.35, 5.85],
        lonaxis_range=[33.35, 42.45],
    )
    figure.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=show_scale,
        legend=dict(
            orientation='h', yanchor='bottom', y=1.0, xanchor='left', x=0,
            bgcolor='rgba(250,252,248,0.9)', bordercolor='#d4ddcd', borderwidth=1,
            font=dict(size=11), itemsizing='constant',
        ),
        font=dict(family='Inter, system-ui, sans-serif', size=12),
        dragmode='pan',
        annotations=annotations,
    )
    figure._label_info = {'labelled': len(annotations), 'unlabelled': len(plotted) - len(annotations)}
    return figure


def map_caption(figure, *, what: str = 'county') -> str:
    """A caption naming how many labels fit, so a missing name is never a mystery."""
    info = getattr(figure, '_label_info', {}) or {}
    labelled, hidden = info.get('labelled', 0), info.get('unlabelled', 0)
    if not hidden:
        return f'Every {what} is labelled. Hover a dot for its values.'
    return (
        f'{labelled} of {labelled + hidden} {what} names fit at this map size; the rest are '
        'shown on hover. Every county keeps its dot — no county is omitted.'
    )


def _geo_names(geo: dict) -> list[str]:
    return [
        (feature.get('properties') or {}).get('county')
        for feature in geo.get('features', [])
        if (feature.get('properties') or {}).get('county')
    ]
