#!/usr/bin/env python3
"""
Writes the REAL map and stock-status data files in data/ from the ABARES Fishery Status Reports 2025 downloads.

    python3 tools/make_map_and_status_data.py ALLFSY_rfl_2010-2024.zip ALLFSY_fp_2010-2024.zip \
        32_FishStatus2025_FullHistoryStatus_1.0.0.csv

Inputs (all ABARES, Fishery Status Reports 2025):
  * ALLFSY_rfl_*.geojson  relative fishing intensity (Low / Medium / High), one file per year, 2010-2024
  * ALLFSY_fp_*.geojson   fishing footprint: the 1-degree cells where fishing was recorded, one file per year
  * 32_FishStatus2025_FullHistoryStatus.csv   Appendix A: status of Commonwealth stocks, 1992-2024

Outputs:
  data/fishing_intensity.geojson      fig01, fig02   (simplified, WGS84, exterior rings clockwise for d3)
  data/fishing_persistence_hex.geojson fig13        (hexagons: average years fished, 2010-2024)
  data/persistence_by_region.csv      (text checks only: squares fished every year / only once, by region)
  data/area_fished_by_region.csv      fig03          (thousand km2 of 1-degree cells, by ocean region and year)
  data/stock_status.csv               fig10, fig11   (Commonwealth stocks per year and status)
  data/healthy_by_fishery.csv         fig12          (% of assessed stocks that are healthy, by fishery group)

Notes
  * The intensity class limits change from year to year (e.g. "Low" is under 60 kg/km2 in 2010 and under 300 in
    2024). The limit for each polygon is kept in the `range` property and shown in the tooltip.
  * The footprint files do not say which fishery a cell belongs to, so area is grouped by OCEAN REGION using the
    centre of each cell. The region boundaries are our own approximate grouping (see REGIONS below).
"""
import csv
import glob
import io
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
EARTH_R = 6371.0  # km
SIMPLIFY_DEG = 0.03  # about 3 km; the map is drawn at roughly 12 km per pixel
MIN_RING_AREA = 0.00002  # square degrees (about 0.3 km2); drop only true slivers


# ------------------------------------------------------------------ geometry helpers
def signed_area(ring):
    """Planar signed area in lon/lat (positive = counter-clockwise with y up)."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2


def dp(points, tol):
    """Douglas-Peucker simplification (iterative)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = points[a], points[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best, idx = -1.0, None
        for i in range(a + 1, b):
            px, py = points[i]
            d = math.hypot(px - ax, py - ay) if norm == 0 else abs(dy * (px - ax) - dx * (py - ay)) / norm
            if d > best:
                best, idx = d, i
        if best > tol and idx is not None:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


def clean_ring(ring, exterior):
    raw = [tuple(p[:2]) for p in ring]
    tol = min(SIMPLIFY_DEG, 0.12 * math.sqrt(abs(signed_area(raw))))  # small shapes keep more detail
    pts = [(round(x, 3), round(y, 3)) for x, y in dp(raw, tol)]
    out = [pts[0]]
    for p in pts[1:]:
        if p != out[-1]:
            out.append(p)
    if out[0] != out[-1]:
        out.append(out[0])
    if len(out) < 4:
        return None
    a = signed_area(out)
    if abs(a) < (MIN_RING_AREA if exterior else MIN_RING_AREA / 2):
        return None
    # d3 (and so Vega) wants exterior rings clockwise and holes counter-clockwise
    if (exterior and a > 0) or (not exterior and a < 0):
        out.reverse()
    return [list(p) for p in out]


def sphere_area_km2(rings):
    """Exact spherical area of lon/lat rings (cylindrical equal-area shoelace); holes are rings[1:]."""
    def ring_area(r):
        s = 0.0
        for (x1, y1), (x2, y2) in zip(r, r[1:]):
            s += math.radians(x1) * math.sin(math.radians(y2)) - math.radians(x2) * math.sin(math.radians(y1))
        return abs(s) / 2 * EARTH_R ** 2
    return ring_area(rings[0]) - sum(ring_area(h) for h in rings[1:])


def centre(rings):
    xs = [p[0] for p in rings[0]]
    ys = [p[1] for p in rings[0]]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


# ------------------------------------------------------------------ ocean regions (our own grouping)
REGIONS = ["Northern waters (Timor, Arafura, Gulf)", "Torres Strait and Coral Sea",
           "East coast (NSW, southern Qld)", "South-east (Bass Strait, Tasmania)",
           "Great Australian Bight", "Western waters"]


def region(lon, lat):
    if lat > -23:
        return REGIONS[0] if lon < 142 else REGIONS[1]
    if lon < 129:
        return REGIONS[5]
    if lon < 141:
        return REGIONS[4]
    return REGIONS[3] if lat <= -37 else REGIONS[2]


# ------------------------------------------------------------------ fig01 / fig02: intensity polygons
def pretty_range(r):
    r = str(r).strip().replace("_", "-")
    m = re.match(r"^<\s*([\d.]+)$", r)
    if m:
        return f"under {int(float(m.group(1))):,}"
    m = re.match(r"^([\d.]+)\s*-\s*([\d.]+)$", r)
    if m:
        return f"{int(float(m.group(1))):,} to {int(float(m.group(2))):,}"
    return r


def read_zip_geojson(zpath, pattern):
    out = {}
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():
            m = re.search(pattern, n)
            if m and n.endswith(".geojson"):
                out[int(m.group(1))] = json.loads(z.read(n))
    return out


def build_intensity(rfl_zip):
    years = read_zip_geojson(rfl_zip, r"_rfl_(\d{4})\.geojson$")
    assert sorted(years) == list(range(2010, 2025)), sorted(years)
    feats = []
    for y in sorted(years):
        for f in years[y]["features"]:
            p = {k.lower(): v for k, v in f["properties"].items()}
            level = p["relativeintensity"]
            assert level in ("Low", "Medium", "High"), level
            assert str(y) in str(p["season"]), (y, p["season"])
            polys = []
            for poly in f["geometry"]["coordinates"]:
                rings = []
                for i, ring in enumerate(poly):
                    r = clean_ring(ring, exterior=(i == 0))
                    if r is None and i == 0:
                        rings = []
                        break
                    if r is not None:
                        rings.append(r)
                if rings:
                    polys.append(rings)
            if polys:
                feats.append({"type": "Feature",
                              "properties": {"year": y, "intensity": level, "range": pretty_range(p["range"])},
                              "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    path = os.path.join(DATA, "fishing_intensity.geojson")
    with open(path, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, separators=(",", ":"))
    print(f"  wrote data/fishing_intensity.geojson  ({len(feats)} polygons, {os.path.getsize(path) / 1e6:.2f} MB)")
    by_year = Counter(f["properties"]["year"] for f in feats)
    print("   polygons per year:", dict(sorted(by_year.items())))
    return feats


# ------------------------------------------------------------------ fig03: area fished by region
def build_area(fp_zip):
    years = read_zip_geojson(fp_zip, r"_fp_(\d{4})\.geojson$")
    assert sorted(years) == list(range(2010, 2025)), sorted(years)
    area = defaultdict(lambda: defaultdict(float))
    for y, d in years.items():
        for f in d["features"]:
            assert str(f["properties"]["TotalAreaFished"]).strip() == str(y)
            for poly in f["geometry"]["coordinates"]:
                lon, lat = centre(poly)
                area[region(lon, lat)][y] += sphere_area_km2(poly)
    rows = []
    for reg in REGIONS:
        rows.append([reg] + [round(area[reg][y] / 1000, 1) for y in range(2010, 2025)])
    path = os.path.join(DATA, "area_fished_by_region.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["region"] + [f"area_{y}" for y in range(2010, 2025)])
        w.writerows(rows)
    tot = {y: sum(r[1 + y - 2010] for r in rows) for y in (2010, 2024)}
    print(f"  wrote data/area_fished_by_region.csv  ({len(rows)} rows)")
    print("   total area (thousand km2):", tot, f"-> change {(tot[2024] / tot[2010] - 1):.1%}")
    for r in rows:
        print("   ", f"{r[0]:<42}", r[1], "->", r[-1])


# ------------------------------------------------------------------ fig10-12: Commonwealth stock status
CW = ["Healthy", "Uncertain", "Overfishing", "Overfished", "Not assessed"]


def combine(fm, bm):
    """One status from fishing mortality (fm) and biomass (bm) for a stock in a year."""
    if fm in ("", None) and bm in ("", None):
        return None  # stock not in the list yet
    if bm == "Overfished":
        return "Overfished"
    if fm == "Subject to overfishing":
        return "Overfishing"
    if bm == "Not overfished" and fm == "Not subject to overfishing":
        return "Healthy"
    if bm in ("Not assessed", "") and fm in ("Not assessed", ""):
        return "Not assessed"
    return "Uncertain"


def group_of(first_col0, col0_all):
    t = first_col0
    full = " ".join(c for c in col0_all if c).replace("  ", " ")
    if t.startswith("Northern Prawn"):
        return "Northern Prawn"
    if t.startswith("Small Pelagic"):
        return "Small Pelagic"
    if t.startswith("Coral Sea"):
        return "Coral Sea"
    if t.startswith("Torres Strait"):
        return "Torres Strait"
    if t.startswith("Eastern Tuna"):
        return "Eastern tuna and billfish"
    if t.startswith("Western Tuna"):
        return "Western tuna and billfish"
    if t.startswith(("Heard Island", "CCAMLR", "Macquarie", "South Tasman")):
        return "Southern Ocean (toothfish, icefish)"
    if t.startswith("SESSF"):
        if "Great Australian Bight" in full:
            return "Great Australian Bight trawl"
        if "Shark" in full:
            return "South-east sharks"
        return "South-east trawl and scalefish"
    return "Other fisheries"


def build_status(csv_path):
    rows = list(csv.reader(open(csv_path, encoding="utf-8-sig")))
    assert rows[2][2] == "1992" and rows[2][11] == "2004" and rows[2][51] == "2024", "column layout changed"
    assert rows[3][11] == "Fishing mortality" and rows[3][12] == "Biomass"
    years = list(range(2004, 2025))
    stocks = []
    i = 5
    while i < len(rows):
        r = rows[i]
        if sum(1 for c in r[2:] if c) >= 1:
            j = i + 1
            cont = [r[0]]
            while j < len(rows) and sum(1 for c in rows[j][2:] if c) == 0 and (rows[j][0] or rows[j][1]):
                if rows[j][0].startswith("Stocks in fisheries"):
                    break
                cont.append(rows[j][0])
                j += 1
            joint = i >= 155
            status = {}
            for y in years:
                k = 11 + 2 * (y - 2004)
                status[y] = combine(r[k], r[k + 1])
            stocks.append({"name": r[1], "group": group_of(r[0], cont), "joint": joint, "status": status})
            i = j
        else:
            i += 1
    print(f"  parsed {len(stocks)} stocks ({sum(s['joint'] for s in stocks)} in jointly managed fisheries)")

    # stream / slope: stocks by status and year (stocks not yet on the list are left out)
    out = []
    for y in years:
        c = Counter(s["status"][y] for s in stocks if s["status"][y])
        for n, st in enumerate(CW, 1):
            out.append([y, st, n, c.get(st, 0)])
    path = os.path.join(DATA, "stock_status.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "status", "status_order", "stocks"])
        w.writerows(out)
    print("  wrote data/stock_status.csv")
    for y in (2004, 2008, 2012, 2016, 2020, 2023, 2024):
        c = Counter(s["status"][y] for s in stocks if s["status"][y])
        print("   ", y, {k: c.get(k, 0) for k in CW}, "total", sum(c.values()))

    # heatmap: % healthy among assessed stocks, by fishery group
    rows_out = []
    groups = defaultdict(list)
    for s in stocks:
        groups[s["group"]].append(s)
    for g, ss in groups.items():
        for y in range(2010, 2025):
            listed = [s for s in ss if s["status"][y]]
            assessed = [s for s in listed if s["status"][y] != "Not assessed"]
            if not assessed:
                continue
            healthy = sum(1 for s in assessed if s["status"][y] == "Healthy")
            rows_out.append([g, y, round(healthy / len(assessed) * 100, 1), len(assessed), len(ss)])
    path = os.path.join(DATA, "healthy_by_fishery.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fishery", "year", "pct_healthy", "assessed", "stocks_listed"])
        w.writerows(rows_out)
    print(f"  wrote data/healthy_by_fishery.csv  ({len(rows_out)} rows; groups:",
          ", ".join(f"{g} ({len(v)})" for g, v in groups.items()) + ")")


# ------------------------------------------------------------------ fig13: hexbin map of fishing persistence
HEX_R = math.radians(1.5)  # hexagon circumradius, in Mercator units (about 1.5 degrees)


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def inv_merc(y):
    return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


def hex_of(lon, lat):
    """Pointy-top hexagon (axial q, r) containing a point, on a regular grid in Mercator space."""
    x, y = math.radians(lon), merc_y(lat)
    q = (math.sqrt(3) / 3 * x - y / 3) / HEX_R
    r = (2 / 3 * y) / HEX_R
    qf, rf, sf = q, r, -q - r
    rq, rr, rs = round(qf), round(rf), round(sf)
    dq, dr, ds = abs(rq - qf), abs(rr - rf), abs(rs - sf)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def hex_polygon(q, r):
    cx = HEX_R * math.sqrt(3) * (q + r / 2)
    cy = HEX_R * 1.5 * r
    pts = []
    for k in range(6):
        a = math.radians(30 + 60 * k)
        pts.append([round(math.degrees(cx + HEX_R * math.cos(a)), 3), round(inv_merc(cy + HEX_R * math.sin(a)), 3)])
    pts.append(pts[0])
    if signed_area(pts) > 0:  # exterior rings clockwise for d3
        pts.reverse()
    return pts


def build_hex(fp_zip):
    years = read_zip_geojson(fp_zip, r"_fp_(\d{4})\.geojson$")
    assert sorted(years) == list(range(2010, 2025)), sorted(years)
    cell_years = defaultdict(set)
    for y, d in years.items():
        for f in d["features"]:
            for poly in f["geometry"]["coordinates"]:
                lon, lat = centre(poly)
                cell_years[(math.floor(lon), math.floor(lat))].add(y)
    hexes = defaultdict(list)
    for (lo, la), ys in cell_years.items():
        hexes[hex_of(lo + 0.5, la + 0.5)].append(len(ys))
    feats = []
    for (q, r), counts in sorted(hexes.items()):
        feats.append({"type": "Feature",
                      "properties": {"avg_years": round(sum(counts) / len(counts), 1), "cells": len(counts),
                                     "cells_every_year": sum(1 for c in counts if c == 15)},
                      "geometry": {"type": "Polygon", "coordinates": [hex_polygon(q, r)]}})
    path = os.path.join(DATA, "fishing_persistence_hex.geojson")
    with open(path, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, separators=(",", ":"))
    by_reg = defaultdict(lambda: [0, 0, 0])  # squares, fished every year, fished one year only
    for (lo, la), ys in cell_years.items():
        c = by_reg[region(lo + 0.5, la + 0.5)]
        c[0] += 1
        c[1] += len(ys) == 15
        c[2] += len(ys) == 1
    with open(os.path.join(DATA, "persistence_by_region.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["region", "squares", "fished_every_year", "fished_one_year"])
        for reg in REGIONS:
            w.writerow([reg] + by_reg[reg])
    allc = [len(v) for v in cell_years.values()]
    print(f"  wrote data/fishing_persistence_hex.geojson  ({len(feats)} hexagons, {os.path.getsize(path) / 1e3:.0f} KB)")
    print(f"   1-degree squares fished at least once: {len(allc)}; every year (15): {sum(c == 15 for c in allc)}; "
          f"only one year: {sum(c == 1 for c in allc)}; 10+ years: {sum(c >= 10 for c in allc)}")


def main(rfl_zip, fp_zip, status_csv):
    os.makedirs(DATA, exist_ok=True)
    build_intensity(rfl_zip)
    build_area(fp_zip)
    build_hex(fp_zip)
    build_status(status_csv)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
