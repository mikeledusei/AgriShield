# County map design

The dashboard map is built by `apps/frontend/shared/county_map.py` and used by three
pages: Live conditions, Reported maize yields, and Historical explorer.

## Why not a tile basemap

Plotly 7 offers `Scattermap` / `Choroplethmap` with a MapLibre basemap. That would look
more like a conventional map product, but every tile is fetched by the **viewer's
browser** from a third-party tile server. Three consequences decide against it:

1. **It fails closed.** Behind a firewall, on a slow link, or offline, the basemap is
   blank and the page looks broken. The current map always renders.
2. **It adds a licence obligation.** OpenStreetMap tiles require attribution and are not
   licensed for heavy or commercial use; commercial providers need a key and terms review
   for a research deployment.
3. **It is not needed.** The county boundaries *are* the geography. A grey land layer with
   boundary lines communicates everything the basemap would.

If a basemap is ever required for a presentation, add it as a separate opt-in page rather
than changing these three.

## What is drawn

- **Land layer** — county polygons, flat `#eef3ea`, 0.7 px boundary lines.
- **Dots** — placed at each county's polygon centroid (computed at load; the GeoJSON has
  no coordinate properties). Colour is the score band, one trace per band so the legend
  maps exactly to the palette in `shared/scales.py`:

  | Band | Score | Colour |
  | --- | --- | --- |
  | Lower | < 25 | `#8cb77d` |
  | Moderate | 25–49 | `#d7bc70` |
  | Elevated | 50–74 | `#ce8a54` |
  | High | ≥ 75 | `#ac5841` |

  Weather and yield pages pass `band_key=None` and use a continuous green→terracotta
  scale instead, so a non-score value is never mistaken for a risk band.
- **Labels** — the county name at every dot, with a thin leader line when the name has to
  move clear of its own marker.
- **Legend** — band swatches plus the numeric thresholds, under the map.

## Label placement

Dense is the whole problem: 20+ counties sit inside two degrees of longitude in central
and western Kenya — narrower than the words. The placement is a greedy collision search
(`_plan_labels`):

1. All dot positions are registered **before** placement starts, so a label can never
   later be landed on by a marker of a county processed afterwards.
2. Each name is tried in eight directions around its dot, then progressively further out
   (1.0× to 2.9× the dot's edge). A position is accepted only if the label box overlaps
   neither another label, another dot, nor the map frame.
3. Long names wrap at the hyphen or space (`Elgeyo-Marakwet` → two lines) so the box is
   narrower.
4. Labels that still will not fit are dropped to hover text. The caption reports how many
   fit, so a name missing from the map is explained rather than looking like an omission.
   No county ever loses its dot.

The `Label every county` toggle on the Historical explorer switches between the wide
search (every name, more leader lines) and a snug search (fewer names, no clutter).

`tests/test_frontend.py::test_county_map_places_labels_without_overlap` rebuilds every
label box from the renderer's own constants and asserts no two boxes intersect and none
leaves the frame. It caught two real defects: an anchor placed on the wrong edge of the
label box (which shifted every label one line height onto its neighbour), and the
late-dot registration bug in step 1.

## Assets

| File | Vertices | Size | Used by |
| --- | --- | --- | --- |
| `assets/kenya_counties.geojson` | 166,547 | 6.8 MB | GIS use, high-detail exports |
| `assets/kenya_counties_simplified.geojson` | 8,043 | 323 KB | the dashboard |

Regenerate the simplified file after replacing the full one:

```bash
python apps/frontend/scripts/simplify_geojson.py
```

Douglas-Peucker at 0.01° (~1 km at the equator). The simplification is invisible at
dashboard scale and cuts the payload sent to the browser by ~95%.
