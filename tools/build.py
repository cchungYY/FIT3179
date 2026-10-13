#!/usr/bin/env python3
"""
Generates ALL the Vega-Lite chart specs in specs/ (and specs/theme.json).

All data is real and is written by two other scripts, never by this one:

    python3 tools/make_real_data.py <ABARES statistics workbook.xlsx>     charts 4 to 9
    python3 tools/make_map_and_status_data.py <rfl.zip> <fp.zip> <status.csv>   charts 1 to 3 and 10 to 12

Run from the project root:   python3 tools/build.py
The specs are plain JSON and can also be edited by hand.
"""
import json
import math
import os
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SPECS = os.path.join(ROOT, "specs")
os.makedirs(DATA, exist_ok=True)
os.makedirs(SPECS, exist_ok=True)

# ---------------------------------------------------------------- palette
INK = "#0b2a3c"
MUTED = "#5d7384"
TEAL = "#0f6c7a"      # wild-caught
FARM = "#c8641f"      # farmed / aquaculture
# SAFS national stock status (waffle, chart 9)
STATUS = ["Sustainable", "Recovering", "Depleting", "Depleted"]
STATUS_COLORS = ["#1f7a74", "#78b8a0", "#eaa83a", "#a63a32"]
# ABARES Commonwealth stock status, combined from biomass and fishing mortality (charts 10 to 12)
CW = ["Healthy", "Uncertain", "Overfishing", "Overfished", "Not assessed"]
CW_COLORS = ["#1f7a74", "#a3b4bf", "#eaa83a", "#a63a32", "#e9eef1"]
INTENSITY = ["Low", "Medium", "High"]
INTENSITY_COLORS = ["#cfe6ee", "#4fa3b8", "#0b4f6c"]

# ---------------------------------------------------------------- specs
SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"
TOPO = "https://cdn.jsdelivr.net/npm/vega-datasets@2/data/world-110m.json"


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def projection(w, h, lon0=111, lon1=163, lat0=-46, lat1=-8):
    s = min(w / math.radians(lon1 - lon0), h / (merc_y(lat1) - merc_y(lat0)))
    ymid = (merc_y(lat0) + merc_y(lat1)) / 2
    latc = math.degrees(2 * math.atan(math.exp(ymid)) - math.pi / 2)
    return {"type": "mercator", "scale": round(s, 1),
            "center": [(lon0 + lon1) / 2, round(latc, 3)], "translate": [w / 2, h / 2]}


def land_layers():
    src = {"url": TOPO, "format": {"type": "topojson", "feature": "countries"}}
    return [
        {"data": src, "transform": [{"filter": "indexof([360, 598, 554, 626], datum.id) >= 0"}],
         "mark": {"type": "geoshape", "fill": "#e9ecee", "stroke": "#c5ccd1", "strokeWidth": 0.5}},
        {"data": src, "transform": [{"filter": "datum.id == 36"}],
         "mark": {"type": "geoshape", "fill": "#f1e7d0", "stroke": "#9a8f78", "strokeWidth": 0.7}},
    ]


GRID = {"url": "data/fishing_intensity.geojson", "format": {"type": "json", "property": "features"}}


def intensity_color(legend=True):
    return {"field": "properties.intensity", "type": "ordinal",
            "scale": {"domain": INTENSITY, "range": INTENSITY_COLORS},
            "legend": ({"title": "Fishing intensity", "orient": "bottom-left", "offset": 8} if legend else None)}


def status_color(legend=True, orient="bottom", columns=4):
    return {"field": "status", "type": "nominal",
            "scale": {"domain": STATUS, "range": STATUS_COLORS},
            "legend": ({"title": "Stock status", "orient": orient, "columns": columns, "symbolType": "square"}
                       if legend else None)}


def cw_color(legend=True, orient="bottom", columns=5, include_unassessed=True):
    dom = CW if include_unassessed else CW[:4]
    rng = CW_COLORS if include_unassessed else CW_COLORS[:4]
    return {"field": "status", "type": "nominal",
            "scale": {"domain": dom, "range": rng},
            "legend": ({"title": "Stock status", "orient": orient, "columns": columns, "symbolType": "square"}
                       if legend else None)}


def title(text, sub, width=640):
    """Chart title with the subtitle split into lines that fit the chart width."""
    lines = textwrap.wrap(sub, max(24, int(width / 6.6)))
    return {"text": text, "subtitle": lines if len(lines) > 1 else lines[0], "anchor": "start", "offset": 8}


specs = {}

# ---- fig01: fishing intensity map with year slider ---------------------------------
W, H = 700, 560
TT_INT = [{"field": "properties.year", "title": "Year", "type": "quantitative", "format": "d"},
          {"field": "properties.intensity", "title": "Fishing intensity", "type": "ordinal"},
          {"field": "properties.range", "title": "Catch per km² (kg) in this class", "type": "nominal"}]
specs["fig01-fishing-intensity-map"] = {
    "$schema": SCHEMA, "width": W, "height": H,
    "title": title("Where Commonwealth fishing happens, by year",
                   "Each patch is an area of ocean where fishing was mapped. Drag the slider to change the year.", W),
    "projection": projection(W, H),
    "params": [{"name": "year_sel", "value": 2024,
                "bind": {"input": "range", "min": 2010, "max": 2024, "step": 1, "name": "Year  "}}],
    "layer": [
        {"data": GRID, "transform": [{"filter": "datum.properties.year == year_sel"}],
         "mark": {"type": "geoshape", "stroke": "#ffffff", "strokeWidth": 0.3},
         "encoding": {"color": intensity_color(), "tooltip": TT_INT}},
        *land_layers(),
        {"data": {"values": [
            {"lon": 138.5, "lat": -11.0, "t": "Gulf of Carpentaria"},
            {"lon": 130, "lat": -36.2, "t": "Great Australian Bight"},
            {"lon": 146.5, "lat": -40.9, "t": "Bass Strait"},
            {"lon": 156, "lat": -19, "t": "Coral Sea"},
            {"lon": 156, "lat": -35, "t": "Tasman Sea"}]},
         "mark": {"type": "text", "fontStyle": "italic", "fontSize": 11, "color": "#5a7280"},
         "encoding": {"longitude": {"field": "lon", "type": "quantitative"},
                      "latitude": {"field": "lat", "type": "quantitative"},
                      "text": {"field": "t", "type": "nominal"}}},
    ],
}

# ---- fig02: small-multiple maps ------------------------------------------------------
sw, sh = 235, 235


def small_map(year):
    return {
        "width": sw, "height": sh, "title": {"text": str(year), "anchor": "start", "fontSize": 14},
        "projection": projection(sw, sh),
        "layer": [
            {"data": GRID, "transform": [{"filter": f"datum.properties.year == {year}"}],
             "mark": {"type": "geoshape", "stroke": "#ffffff", "strokeWidth": 0.2},
             "encoding": {"color": {**intensity_color(),
                                    "legend": {"title": "Fishing intensity", "orient": "bottom",
                                               "direction": "horizontal"}},
                          "tooltip": TT_INT}},
            *land_layers(),
        ],
    }


specs["fig02-small-multiple-maps"] = {
    "$schema": SCHEMA,
    "title": title("Four snapshots of the same ocean",
                   "Same colours and the same map area. The cut-offs between low, medium and high change each year, so compare where the dark patches are, not how many there are.", 960),
    "resolve": {"scale": {"color": "shared"}},
    "hconcat": [small_map(y) for y in (2010, 2015, 2020, 2024)],
}

# ---- fig03: dumbbell, area fished 2010 vs 2024, by ocean region ------------------------
specs["fig03-area-fished-dumbbell"] = {
    "$schema": SCHEMA, "width": 400, "height": 300,
    "title": title("How much ocean is fished in each region",
                   "Area of the 1° squares where fishing was recorded, in thousand square kilometres. 2010 compared with 2024.", 640),
    "data": {"url": "data/area_fished_by_region.csv"},
    "layer": [
        {"mark": {"type": "rule", "color": "#9fb4c0", "strokeWidth": 3},
         "encoding": {
             "y": {"field": "region", "type": "nominal",
                   "sort": {"field": "area_2010", "op": "max", "order": "descending"},
                   "axis": {"title": None, "labelLimit": 250, "domain": False, "ticks": False}},
             "x": {"field": "area_2010", "type": "quantitative", "axis": {"title": "Area fished (thousand km²)"}},
             "x2": {"field": "area_2024"}}},
        {"transform": [{"fold": ["area_2010", "area_2024"], "as": ["period", "area"]},
                       {"calculate": "datum.period == 'area_2010' ? '2010' : '2024'", "as": "year_label"}],
         "mark": {"type": "circle", "size": 120, "opacity": 1},
         "encoding": {
             "y": {"field": "region", "type": "nominal",
                   "sort": {"field": "area_2010", "op": "max", "order": "descending"}},
             "x": {"field": "area", "type": "quantitative"},
             "color": {"field": "year_label", "type": "nominal",
                       "scale": {"domain": ["2010", "2024"], "range": ["#94a9b6", TEAL]},
                       "legend": {"title": "Year", "orient": "top", "direction": "horizontal"}},
             "tooltip": [{"field": "region", "title": "Ocean region", "type": "nominal"},
                         {"field": "year_label", "title": "Year", "type": "nominal"},
                         {"field": "area", "title": "Area (thousand km²)", "type": "quantitative", "format": ",.0f"}]}},
    ],
}

# ---- fig13: hexbin map, how many years each part of the ocean was fished -----------------
HEX = {"url": "data/fishing_persistence_hex.geojson", "format": {"type": "json", "property": "features"}}
specs["fig13-fishing-persistence-hexbin"] = {
    "$schema": SCHEMA, "width": W, "height": H,
    "title": title("Which waters are fished year after year?",
                   "Each hexagon covers about five 1° squares. Colour is the typical number of years, out of 15, that a fished square inside it was fished.", W),
    "projection": projection(W, H, lon0=105, lat0=-48),
    "layer": [
        {"data": HEX,
         "mark": {"type": "geoshape", "stroke": "#ffffff", "strokeWidth": 0.6},
         "encoding": {
             "color": {"field": "properties.avg_years", "type": "quantitative",
                       "scale": {"domain": [1, 15], "range": ["#f4efd8", "#6fb1a0", "#0b4f6c"]},
                       "legend": {"title": "Typical years fished (of 15)", "orient": "bottom-left", "offset": 8,
                                  "gradientLength": 180, "values": [1, 5, 10, 15]}},
             "tooltip": [{"field": "properties.avg_years", "title": "Typical years fished (of 15)", "type": "quantitative", "format": ".1f"},
                         {"field": "properties.cells", "title": "1° squares ever fished here", "type": "quantitative"},
                         {"field": "properties.cells_every_year", "title": "Squares fished all 15 years", "type": "quantitative"}]}},
        *land_layers(),
    ],
}

# ---- fig04: production value by sector (REAL) -------------------------------------
specs["fig04-production-value"] = {
    "$schema": SCHEMA, "width": 620, "height": 300,
    "title": title("Farmed seafood has overtaken wild catch",
                   "Gross value of production in millions of dollars. Years end in June; 2025 is preliminary.", 640),
    "data": {"url": "data/production_value.csv"},
    "layer": [
        {"mark": {"type": "area", "line": {"strokeWidth": 1.5}, "opacity": 0.9},
         "encoding": {
             "x": {"field": "year", "type": "quantitative", "scale": {"domain": [2011, 2025], "nice": False},
                   "axis": {"format": "d", "title": None, "tickMinStep": 2, "grid": False}},
             "y": {"field": "value_aud_m", "type": "quantitative", "stack": "zero",
                   "axis": {"title": "Value (A$ millions)", "format": ",.0f"}},
             "color": {"field": "sector", "type": "nominal",
                       "scale": {"domain": ["Wild-catch fisheries", "Aquaculture"], "range": [TEAL, FARM]},
                       "legend": {"title": None, "orient": "top", "direction": "horizontal"}},
             "order": {"field": "sector_order", "type": "quantitative"},
             "tooltip": [{"field": "label", "title": "Year", "type": "nominal"},
                         {"field": "sector", "title": "Sector", "type": "nominal"},
                         {"field": "value_aud_m", "title": "A$ millions", "type": "quantitative", "format": ",.0f"}]}},
        {"data": {"values": [{"year": 2020}]},
         "mark": {"type": "rule", "strokeDash": [4, 3], "color": INK},
         "encoding": {"x": {"field": "year", "type": "quantitative"}}},
        {"data": {"values": [{"year": 2020, "t": "2019–20: farmed seafood moves ahead"}]},
         "mark": {"type": "text", "align": "right", "dx": -6, "fontSize": 12, "fontWeight": 600, "color": INK},
         "encoding": {"x": {"field": "year", "type": "quantitative"}, "y": {"value": 14},
                      "text": {"field": "t", "type": "nominal"}}},
    ],
}

# ---- fig05: Pareto, tonnes by species group (REAL) --------------------------------
specs["fig05-catch-pareto"] = {
    "$schema": SCHEMA, "width": 560, "height": 330,
    "title": title("One small fish dominates the catch by weight",
                   "Tonnes of wild-caught seafood in 2024–25 (preliminary). The line adds up each group's "
                   "share of all wild-caught tonnes.", 640),
    "data": {"url": "data/catch_by_group_latest.csv"},
    "transform": [
        {"window": [{"op": "sum", "field": "tonnes", "as": "cum"}],
         "sort": [{"field": "tonnes", "order": "descending"}], "frame": [None, 0]},
        {"calculate": "datum.cum / datum.total_tonnes", "as": "cum_pct"},
        {"calculate": "datum.tonnes / datum.total_tonnes", "as": "share"},
        {"joinaggregate": [{"op": "max", "field": "cum_pct", "as": "cum_max"}]}],
    "encoding": {"x": {"field": "group", "type": "nominal",
                       "sort": {"field": "tonnes", "op": "max", "order": "descending"},
                       "axis": {"title": None, "labelAngle": -35, "labelLimit": 150}}},
    "layer": [
        {"mark": {"type": "bar", "color": TEAL, "cornerRadiusTopLeft": 2, "cornerRadiusTopRight": 2},
         "encoding": {"y": {"field": "tonnes", "type": "quantitative",
                            "axis": {"title": "Tonnes caught", "format": ",.0f"}},
                      "tooltip": [{"field": "group", "title": "Species group", "type": "nominal"},
                                  {"field": "tonnes", "title": "Tonnes", "type": "quantitative", "format": ",.0f"},
                                  {"field": "share", "title": "Share of all wild catch", "type": "quantitative", "format": ".0%"},
                                  {"field": "value_aud_m", "title": "Value (A$ millions)", "type": "quantitative", "format": ",.0f"}]}},
        {"mark": {"type": "line", "color": "#2a2f36", "strokeWidth": 2.5,
                  "point": {"filled": True, "size": 50, "color": "#2a2f36"}},
         "encoding": {"y": {"field": "cum_pct", "type": "quantitative", "scale": {"domain": [0, 1]},
                            "axis": {"title": "Running share of all wild-caught tonnes", "format": "%",
                                     "orient": "right", "titleColor": "#2a2f36"}}}},
        {"transform": [{"filter": "datum.cum_pct == datum.cum_max"},
                       {"calculate": "'Top 10 groups = ' + format(datum.cum_pct, '.0%') + ' of all wild catch'", "as": "label"}],
         "mark": {"type": "text", "align": "right", "dx": -8, "dy": -14, "fontSize": 12, "fontWeight": 600, "color": "#2a2f36"},
         "encoding": {"y": {"field": "cum_pct", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": None},
                      "text": {"field": "label", "type": "nominal"}}},
    ],
    "resolve": {"scale": {"y": "independent"}},
}

# ---- fig06: connected scatterplot, wild-catch tonnes vs value (REAL) --------------
fx = {"field": "tonnes_thousand", "type": "quantitative", "scale": {"domain": [145, 190], "zero": False},
      "axis": {"title": "Wild-caught seafood (thousand tonnes)", "grid": False}}
fy = {"field": "value_aud_m", "type": "quantitative", "scale": {"domain": [1200, 1900], "zero": False},
      "axis": {"title": "Value (A$ millions)", "format": ",.0f"}}
specs["fig06-catch-value-connected-scatter"] = {
    "$schema": SCHEMA, "width": 560, "height": 340,
    "title": title("Same fish, different dollars",
                   "Each dot is one year of wild-caught seafood: tonnes caught across, dollar value up. "
                   "The line joins the years in order, darker dots are more recent.", 640),
    "data": {"url": "data/wild_catch_trend.csv"},
    "transform": [{"calculate": "datum.year == 2021 ? datum.value_aud_m - 45 : datum.value_aud_m + 40", "as": "label_y"}],
    "layer": [
        {"mark": {"type": "line", "color": "#9fb4c0", "strokeWidth": 2.5},
         "encoding": {"x": fx, "y": fy, "order": {"field": "year", "type": "quantitative"}}},
        {"mark": {"type": "circle", "size": 100, "opacity": 1, "stroke": "#ffffff", "strokeWidth": 1.5},
         "encoding": {"x": fx, "y": fy,
                      "color": {"field": "year", "type": "quantitative",
                                "scale": {"range": ["#a9d3de", "#0b3a4d"]}, "legend": None},
                      "tooltip": [{"field": "label", "title": "Year", "type": "nominal"},
                                  {"field": "tonnes_thousand", "title": "Thousand tonnes", "type": "quantitative", "format": ".0f"},
                                  {"field": "value_aud_m", "title": "A$ millions", "type": "quantitative", "format": ",.0f"}]}},
        {"transform": [{"filter": "indexof([2011, 2015, 2019, 2021, 2025], datum.year) >= 0"}],
         "mark": {"type": "text", "align": "center", "fontSize": 11, "fontWeight": 600, "color": INK},
         "encoding": {"x": {"field": "tonnes_thousand", "type": "quantitative"},
                      "y": {"field": "label_y", "type": "quantitative"},
                      "text": {"field": "label", "type": "nominal"}}},
        {"data": {"values": [{"x": 146, "y": 1870, "t": "2018–19 to 2020–21: tonnes down 3%, value down 18%"}]},
         "mark": {"type": "text", "align": "left", "fontSize": 12, "fontWeight": 600, "color": FARM},
         "encoding": {"x": {"field": "x", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"},
                      "text": {"field": "t", "type": "nominal"}}},
    ],
}

# ---- fig07: proportional symbol map, production by state (REAL) -------------------
STATE = {"url": "data/production_by_state.csv"}
specs["fig07-production-by-state-map"] = {
    "$schema": SCHEMA, "width": W, "height": H,
    "title": title("Where Australia's seafood is produced",
                   "Circle area shows tonnes produced in 2024–25 (preliminary), fished and farmed together. "
                   "Colour shows how much of it is farmed. Each circle sits on the state capital.", W),
    "projection": projection(W, H),
    "layer": [
        *land_layers(),
        {"data": STATE,
         "mark": {"type": "circle", "opacity": 0.92, "stroke": "#ffffff", "strokeWidth": 1.5},
         "encoding": {
             "longitude": {"field": "lon", "type": "quantitative"},
             "latitude": {"field": "lat", "type": "quantitative"},
             "size": {"field": "tonnes_total", "type": "quantitative", "scale": {"range": [250, 7000]},
                      "legend": {"title": "Tonnes produced", "orient": "bottom-left", "format": ",.0f"}},
             "color": {"field": "pct_farmed", "type": "quantitative",
                       "scale": {"domain": [0, 50, 100], "range": [TEAL, "#6b7a64", FARM]},
                       "legend": {"title": "Farmed share (%)", "orient": "bottom-left", "format": ".0f"}},
             "tooltip": [{"field": "jurisdiction", "title": "State or territory", "type": "nominal"},
                         {"field": "tonnes_total", "title": "Tonnes produced", "type": "quantitative", "format": ",.0f"},
                         {"field": "tonnes_wild", "title": "Wild-caught (t)", "type": "quantitative", "format": ",.0f"},
                         {"field": "tonnes_farmed", "title": "Farmed (t)", "type": "quantitative", "format": ",.0f"},
                         {"field": "pct_farmed", "title": "Farmed share (%)", "type": "quantitative", "format": ".0f"}]}},
        {"data": STATE,
         "mark": {"type": "text", "fontWeight": 700, "fontSize": 13, "color": "#ffffff"},
         "encoding": {"longitude": {"field": "lon", "type": "quantitative"},
                      "latitude": {"field": "lat", "type": "quantitative"},
                      "text": {"field": "jurisdiction", "type": "nominal"}}},
    ],
}

# ---- fig08: value vs tonnes per Commonwealth fishery, with price-per-kg lines (REAL) -
XMAX, YMAX = 20000, 90
ref_rows, ref_labels = [], []
for k in (5, 10, 20):
    x_end = YMAX * 1000 / k
    ref_rows += [{"line": f"${k} per kg", "tonnes": 0, "value": 0},
                 {"line": f"${k} per kg", "tonnes": x_end, "value": YMAX}]
    ref_labels.append({"line": f"${k} per kg", "tonnes": x_end, "value": YMAX})
sx = {"field": "tonnes", "type": "quantitative", "scale": {"domain": [0, XMAX]},
      "axis": {"title": "Tonnes caught", "format": ",.0f", "grid": False}}
sy = {"field": "value_aud_m", "type": "quantitative", "scale": {"domain": [0, YMAX]},
      "axis": {"title": "Value of the catch (A$ millions)"}}
specs["fig08-fishery-value-per-tonne"] = {
    "$schema": SCHEMA, "width": 560, "height": 340,
    "title": title("Fish are not all worth the same",
                   "Six Commonwealth fisheries in 2024–25 (preliminary). The dashed lines show a constant "
                   "price per kilogram.", 640),
    "layer": [
        {"data": {"values": ref_rows},
         "mark": {"type": "line", "strokeDash": [5, 4], "color": "#aab9c3", "strokeWidth": 1.5},
         "encoding": {"x": {"field": "tonnes", "type": "quantitative"}, "y": {"field": "value", "type": "quantitative"},
                      "detail": {"field": "line", "type": "nominal"}}},
        {"data": {"values": ref_labels},
         "mark": {"type": "text", "align": "right", "dx": -5, "dy": 10, "fontSize": 11, "color": MUTED},
         "encoding": {"x": {"field": "tonnes", "type": "quantitative"}, "y": {"field": "value", "type": "quantitative"},
                      "text": {"field": "line", "type": "nominal"}}},
        {"data": {"url": "data/fisheries.csv"},
         "mark": {"type": "circle", "size": 150, "color": TEAL, "opacity": 0.9, "stroke": "#ffffff", "strokeWidth": 1.5},
         "encoding": {"x": sx, "y": sy,
                      "tooltip": [{"field": "fishery", "title": "Fishery", "type": "nominal"},
                                  {"field": "tonnes", "title": "Tonnes", "type": "quantitative", "format": ",.0f"},
                                  {"field": "value_aud_m", "title": "Value (A$ millions)", "type": "quantitative", "format": ",.1f"},
                                  {"field": "value_per_kg", "title": "Dollars per kg", "type": "quantitative", "format": ".2f"}]}},
        {"data": {"url": "data/fisheries.csv"}, "transform": [{"filter": "datum.tonnes < 12000"}],
         "mark": {"type": "text", "align": "left", "dx": 10, "dy": -8, "fontSize": 12, "color": INK},
         "encoding": {"x": {"field": "tonnes", "type": "quantitative"}, "y": {"field": "value_aud_m", "type": "quantitative"},
                      "text": {"field": "fishery", "type": "nominal"}}},
        {"data": {"url": "data/fisheries.csv"}, "transform": [{"filter": "datum.tonnes >= 12000"}],
         "mark": {"type": "text", "align": "right", "dx": -10, "dy": 14, "fontSize": 12, "color": INK},
         "encoding": {"x": {"field": "tonnes", "type": "quantitative"}, "y": {"field": "value_aud_m", "type": "quantitative"},
                      "text": {"field": "fishery", "type": "nominal"}}},
    ],
}

# ---- fig09: waffle, stock status 2024 (REAL: SAFS counts) ---------------------------
specs["fig09-stock-status-waffle"] = {
    "$schema": SCHEMA, "width": 300, "height": 300,
    "title": title("Fish stocks in 2024, as 100 squares",
                   "One square is 1% of the 392 stocks with a known status.", 330),
    "data": {"url": "data/waffle_2024.csv"},
    "mark": {"type": "square", "size": 640, "opacity": 1},
    "encoding": {
        "x": {"field": "col", "type": "quantitative", "scale": {"domain": [-0.5, 9.5]}, "axis": None},
        "y": {"field": "row", "type": "quantitative", "scale": {"domain": [-0.5, 9.5], "reverse": True}, "axis": None},
        "color": status_color(legend=True, orient="bottom", columns=2),
        "tooltip": [{"field": "status", "title": "Stock status", "type": "nominal"}]},
}

# ---- fig10: streamgraph, Commonwealth stock status over time ----------------------------
specs["fig10-stock-status-stream"] = {
    "$schema": SCHEMA, "width": 960, "height": 320,
    "title": title("How the health of Commonwealth fish stocks has shifted",
                   "The thickness of each band is the number of stocks with that status. Stocks are counted from the year they first appear on the ABARES list.", 960),
    "data": {"url": "data/stock_status.csv"},
    "mark": {"type": "area", "interpolate": "monotone"},
    "encoding": {
        "x": {"field": "year", "type": "quantitative", "axis": {"format": "d", "title": None, "tickCount": 11, "grid": False}},
        "y": {"aggregate": "sum", "field": "stocks", "type": "quantitative", "stack": "center", "axis": None},
        "order": {"field": "status_order", "type": "quantitative"},
        "color": cw_color(),
        "tooltip": [{"field": "year", "title": "Year", "type": "quantitative", "format": "d"},
                    {"field": "status", "title": "Stock status", "type": "nominal"},
                    {"field": "stocks", "title": "Number of stocks", "type": "quantitative"}]},
}

# ---- fig11: slope chart, 2008 vs 2024 --------------------------------------------------
specs["fig11-stock-status-slope"] = {
    "$schema": SCHEMA, "width": 600, "height": 380,
    "title": title("Then and now: 2008 compared with 2024",
                   "Share of assessed Commonwealth stocks in each status. Stocks that were not assessed that year are left out.", 640),
    "data": {"url": "data/stock_status.csv"},
    "transform": [
        {"filter": "(datum.year == 2008 || datum.year == 2024) && datum.status != 'Not assessed'"},
        {"joinaggregate": [{"op": "sum", "field": "stocks", "as": "total"}], "groupby": ["year"]},
        {"calculate": "datum.stocks / datum.total", "as": "share"},
        {"calculate": "datum.status + '  ' + format(datum.share, '.0%')", "as": "label"},
        {"window": [{"op": "rank", "as": "label_rank"}], "sort": [{"field": "share", "order": "descending"}],
         "groupby": ["year"]}],
    "encoding": {
        "x": {"field": "year", "type": "quantitative", "scale": {"domain": [1999, 2033]},
              "axis": {"values": [2008, 2024], "format": "d", "title": None, "grid": False, "labelFontSize": 13}},
        "y": {"field": "share", "type": "quantitative", "axis": None},
        "color": cw_color(columns=4, include_unassessed=False)},
    "layer": [
        {"mark": {"type": "line", "strokeWidth": 3}, "encoding": {"detail": {"field": "status", "type": "nominal"}}},
        {"mark": {"type": "circle", "size": 90, "opacity": 1},
         "encoding": {"tooltip": [{"field": "status", "title": "Stock status", "type": "nominal"},
                                  {"field": "year", "title": "Year", "type": "quantitative", "format": "d"},
                                  {"field": "stocks", "title": "Number of stocks", "type": "quantitative"},
                                  {"field": "share", "title": "Share of assessed stocks", "type": "quantitative", "format": ".1%"}]}},
        {"transform": [{"filter": "datum.year == 2008 && datum.label_rank <= 3"}],
         "mark": {"type": "text", "align": "right", "dx": -10, "fontSize": 11, "fontWeight": 600},
         "encoding": {"text": {"field": "label", "type": "nominal"}, "color": {"value": INK}}},
        {"transform": [{"filter": "datum.year == 2024 && datum.label_rank <= 3"}],
         "mark": {"type": "text", "align": "left", "dx": 10, "fontSize": 11, "fontWeight": 600},
         "encoding": {"text": {"field": "label", "type": "nominal"}, "color": {"value": INK}}},
    ],
}

# ---- fig12: annotated heatmap, % healthy by fishery group ------------------------------------
specs["fig12-healthy-heatmap"] = {
    "$schema": SCHEMA, "width": 460, "height": 330,
    "title": title("Which fisheries have the healthiest stocks?",
                   "Percentage of assessed stocks that are healthy, by fishery and year. The number after each fishery is how many stocks it has.", 640),
    "data": {"url": "data/healthy_by_fishery.csv"},
    "transform": [{"calculate": "datum.fishery + ' (' + datum.stocks_listed + ')'", "as": "fishery_label"}],
    "encoding": {
        "x": {"field": "year", "type": "ordinal", "axis": {"title": None, "labelAngle": 0, "format": "d", "labelFontSize": 10}},
        "y": {"field": "fishery_label", "type": "nominal",
              "sort": {"field": "pct_healthy", "op": "mean", "order": "descending"},
              "axis": {"title": None, "domain": False, "ticks": False, "labelLimit": 260}}},
    "layer": [
        {"mark": {"type": "rect", "stroke": "#ffffff", "strokeWidth": 2},
         "encoding": {"color": {"field": "pct_healthy", "type": "quantitative",
                                "scale": {"domain": [0, 50, 100], "range": ["#f6e3c4", "#9fcbb8", "#0f5c57"]},
                                "legend": {"title": "% healthy", "orient": "bottom", "direction": "horizontal",
                                           "gradientLength": 200}},
                      "tooltip": [{"field": "fishery", "title": "Fishery", "type": "nominal"},
                                  {"field": "year", "title": "Year", "type": "quantitative", "format": "d"},
                                  {"field": "pct_healthy", "title": "% healthy", "type": "quantitative", "format": ".0f"},
                                  {"field": "assessed", "title": "Stocks assessed", "type": "quantitative"}]}},
        {"mark": {"type": "text", "fontSize": 9},
         "encoding": {"text": {"field": "pct_healthy", "type": "quantitative", "format": ".0f"},
                      "color": {"condition": {"test": "datum.pct_healthy > 55", "value": "#ffffff"}, "value": INK}}},
    ],
}

# ---------------------------------------------------------------- theme
theme = {
    "background": "transparent",
    "font": "Source Sans 3",
    "view": {"stroke": None},
    "title": {"font": "Fraunces", "fontSize": 17, "fontWeight": 600, "color": INK,
              "subtitleFont": "Source Sans 3", "subtitleFontSize": 12.5, "subtitleColor": MUTED,
              "subtitlePadding": 4},
    "axis": {"labelFont": "Source Sans 3", "titleFont": "Source Sans 3", "labelFontSize": 12,
             "titleFontSize": 12, "titleFontWeight": 600, "labelColor": "#40586a", "titleColor": "#40586a",
             "domainColor": "#b8c7d0", "tickColor": "#b8c7d0", "gridColor": "#e6edf1"},
    "legend": {"labelFont": "Source Sans 3", "titleFont": "Source Sans 3", "labelFontSize": 12,
               "titleFontSize": 12, "titleFontWeight": 600, "labelColor": "#40586a", "titleColor": "#40586a"},
    "text": {"font": "Source Sans 3", "color": INK},
    "concat": {"spacing": 16},
}

for old in os.listdir(SPECS):  # clear specs from earlier drafts so renamed charts do not linger
    if old.startswith("fig") and old.endswith(".vl.json"):
        os.remove(os.path.join(SPECS, old))
for name, spec in specs.items():
    with open(os.path.join(SPECS, f"{name}.vl.json"), "w") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
with open(os.path.join(SPECS, "theme.json"), "w") as f:
    json.dump(theme, f, indent=2)

print(f"{len(specs)} specs written")
