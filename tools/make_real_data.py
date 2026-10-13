#!/usr/bin/env python3
"""
Writes the REAL data files in data/ from the ABARES statistical tables workbook.

    python3 tools/make_real_data.py path/to/DataTables_AustFishAquacStats_2025.xlsx

Source: Curtotti, R, Dylewski, M and Tuynman, H 2026, Australian fisheries and aquaculture
statistics 2025, ABARES, Canberra, September. DOI 10.25814/4w7h-cw80. CC BY 4.0.

Every row is read by its position AND checked against the label we expect to find there.
If ABARES re-orders a table, this script stops with an error instead of writing wrong numbers.

Years are Australian financial years (July to June). "2024-25" is stored as 2025 (the year it
ends). The newest year, 2024-25p, is preliminary.

The waffle chart is not in the workbook. It uses the SAFS 2024 stock counts (see WAFFLE_COUNTS)
copied from https://www.fish.gov.au - check them against the site before submitting.
"""
import csv
import os
import re
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
N_YEARS = 15  # the most recent 15 financial years: 2010-11 ... 2024-25p

# SAFS 2024 (6th edition) stock counts. NOT from the workbook - verify on fish.gov.au.
WAFFLE_COUNTS = {"Sustainable": 318, "Recovering": 16, "Depleting": 13, "Depleted": 45}

STATE_TABLES = {  # table, wild-caught total row, total production row (both in tonnes)
    "NSW": (5, 95, 108, 151.21, -33.87),
    "VIC": (6, 74, 86, 144.96, -37.81),
    "QLD": (7, 97, 110, 153.03, -27.47),
    "SA": (8, 78, 90, 138.60, -34.93),
    "WA": (9, 89, 100, 115.86, -31.95),
    "TAS": (10, 72, 80, 147.33, -42.88),
    "NT": (11, 64, 70, 130.84, -12.46),
}

# plain-English names for the Commonwealth fisheries (the workbook uses SESSF etc.)
FISHERY_NAMES = {
    "Northern Prawn": "Northern Prawn",
    "Torres Strait": "Torres Strait",
    "SESSF Commonwealth Trawl Sector": "South-east trawl",
    "SESSF Gillnet, Hook and Trap Sector": "South-east gillnet, hook and trap",
    "SESSF Great Australian Bight Trawl Sector": "Great Australian Bight trawl",
    "Eastern Tuna and Billfish": "Eastern tuna and billfish",
}
# Table 12 quantity-section headings -> Table 1 names
T12_HEADINGS = {
    "Northern Prawn": "Northern Prawn",
    "Torres Strait": "Torres Strait",
    "SESSF Commonwealth Trawl Sector": "SESSF Commonwealth Trawl Sector",
    "SESSF Gillnet, Hook and Trap Sector": "SESSF Gillnet, Hook and Trap Sector",
    "SESSF Great Australian Bight Trawl Sector": "SESSF Great Australian Bight Trawl Sector",
    "Southern Shark Fishery": None,
    "South East Non-trawl Fishery": None,
    "Eastern Tuna and Billfish – longline and minor line": "Eastern Tuna and Billfish",
    "Western Tuna and Billfish": None,
}


def clean(label):
    """Drop trailing footnote letters such as 'Australian Sardine b' and stray spaces."""
    s = str(label).strip()
    return re.sub(r"\s+[a-z]$", "", s).strip()


def num(x):
    return float(x) if isinstance(x, (int, float)) else None


class Sheet:
    def __init__(self, ws):
        # column A of every sheet is empty, so drop it: label is then column 0, unit column 1
        self.rows = [list(r)[1:] for r in ws.iter_rows(values_only=True)]
        header = self.rows[7]
        assert str(header[0]).startswith(("Commodity", "Category", "Apparent")), header[:3]
        self.years = [str(x).strip() for x in header[2:] if x not in (None, "")]
        self.n = len(self.years)

    def row(self, r, label, unit=None):
        """Excel row r (1-based). Returns the values aligned with self.years."""
        cells = self.rows[r - 1]
        got = clean(cells[0])
        assert got.lower().startswith(label.lower()), f"row {r}: expected '{label}', found '{got}'"
        if unit is not None:
            assert unit in str(cells[1]), f"row {r}: expected unit '{unit}', found '{cells[1]}'"
        return cells[2:2 + self.n]

    def find(self, lo, hi, unit):
        """label -> values for rows lo..hi that have numbers and the given unit."""
        out = {}
        for r in range(lo, hi + 1):
            cells = self.rows[r - 1]
            if cells[0] and cells[1] and unit in str(cells[1]):
                out[clean(cells[0])] = cells[2:2 + self.n]
        return out


def write(name, header, rows):
    path = os.path.join(DATA, name)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  wrote data/{name}  ({len(rows)} rows)")


def main(xlsx):
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    t1, t3, t4, t12 = (Sheet(wb[f"Table {i}"]) for i in (1, 3, 4, 12))
    os.makedirs(DATA, exist_ok=True)

    last = t3.n - 1
    window = list(range(t3.n - N_YEARS, t3.n))
    fy = [t3.years[i] for i in window]
    assert fy[-1] == "2024–25p", f"latest year is {fy[-1]}; this script was written for 2024–25p"
    end_year = [int(s[:4]) + 1 for s in fy]
    prelim = [s.endswith("p") for s in fy]
    label = [s.rstrip("p") + (" (prelim.)" if p else "") for s, p in zip(fy, prelim)]
    print(f"years: {fy[0]} ... {fy[-1]}")

    # ---------------------------------------------------------------- fig04
    wild_v = t3.row(43, "Total wild-caught", "000")
    farm_v = t4.row(32, "Total value", "000")
    rows = []
    for k, i in enumerate(window):
        rows.append([end_year[k], label[k], "Wild-catch fisheries", 1, round(wild_v[i] / 1000, 1), int(prelim[k])])
        rows.append([end_year[k], label[k], "Aquaculture", 2, round(farm_v[i] / 1000, 1), int(prelim[k])])
    write("production_value.csv", ["year", "label", "sector", "sector_order", "value_aud_m", "preliminary"], rows)

    # ---------------------------------------------------------------- fig05
    species_t = t3.find(46, 77, "t")
    species_v = t3.find(11, 42, "000")
    total_t = t3.row(78, "Total wild-caught", "t")
    total_latest = total_t[last]
    named = {k: v for k, v in species_t.items() if not k.lower().startswith(("total", "other"))}
    top = sorted(named, key=lambda k: -named[k][last])[:10]
    rows = []
    for g in top:
        rows.append([g, round(named[g][last]), round(species_v[g][last] / 1000, 1), round(total_latest)])
    write("catch_by_group_latest.csv", ["group", "tonnes", "value_aud_m", "total_tonnes"], rows)
    print("   top 10:", ", ".join(f"{g} {r[1]:,}" for g, r in zip(top, rows)))
    print(f"   top-10 share of all wild-caught tonnes: {sum(r[1] for r in rows) / total_latest:.1%}")

    # ---------------------------------------------------------------- fig06
    rows = [[end_year[k], label[k], round(total_t[i] / 1000, 2), round(wild_v[i] / 1000, 1), int(prelim[k])]
            for k, i in enumerate(window)]
    write("wild_catch_trend.csv", ["year", "label", "tonnes_thousand", "value_aud_m", "preliminary"], rows)

    # ---------------------------------------------------------------- fig07
    rows = []
    for st, (tab, wild_row, tot_row, lon, lat) in STATE_TABLES.items():
        s = Sheet(wb[f"Table {tab}"])
        assert s.years[-1] == "2024–25p", (st, s.years[-1])
        wild = s.row(wild_row, "Total wild-caught", "t")[s.n - 1]
        tot = s.row(tot_row, "Total production", "t")[s.n - 1]
        rows.append([st, lon, lat, round(tot), round(wild), round(tot - wild), round((tot - wild) / tot * 100, 1)])
    write("production_by_state.csv",
          ["jurisdiction", "lon", "lat", "tonnes_total", "tonnes_wild", "tonnes_farmed", "pct_farmed"], rows)

    # ---------------------------------------------------------------- fig08
    value_by_fishery = {}
    for r in range(28, 42):
        cells = t1.rows[r - 1]
        v = num(cells[2 + last])
        value_by_fishery[clean(cells[0])] = v
    # quantity: last row labelled exactly "Total" (unit t) inside each fishery's block
    q0 = next(r for r in range(1, len(t12.rows) + 1) if clean(t12.rows[r - 1][0]) == "Quantity" and r > 100)
    heads = []
    for r in range(q0 + 1, len(t12.rows) + 1):
        cells = t12.rows[r - 1]
        name = clean(cells[0]) if cells[0] else ""
        if name in T12_HEADINGS and all(c in (None, "") for c in cells[1:6]):
            heads.append((r, name))
    assert len(heads) == len(T12_HEADINGS), [h[1] for h in heads]
    tonnes_by_fishery = {}
    for k, (r, name) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(t12.rows) + 1
        totals = [rr for rr in range(r + 1, end)
                  if clean(t12.rows[rr - 1][0]) == "Total" and str(t12.rows[rr - 1][1]).strip() == "t"]
        assert totals, name
        v = num(t12.rows[totals[-1] - 1][2 + last])
        if T12_HEADINGS[name] and v is not None:
            tonnes_by_fishery[T12_HEADINGS[name]] = v
    rows = []
    for wb_name, short in FISHERY_NAMES.items():
        v, t = value_by_fishery.get(wb_name), tonnes_by_fishery.get(wb_name)
        assert v is not None and t is not None, wb_name
        rows.append([short, round(t), round(v / 1000, 1), round(v / t, 2)])
    write("fisheries.csv", ["fishery", "tonnes", "value_aud_m", "value_per_kg"], rows)

    # ---------------------------------------------------------------- fig09
    total = sum(WAFFLE_COUNTS.values())
    raw = {k: v / total * 100 for k, v in WAFFLE_COUNTS.items()}
    sq = {k: int(r) for k, r in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - sq[k], reverse=True)[: 100 - sum(sq.values())]:
        sq[k] += 1
    rows, i = [], 0
    for status, n in sq.items():
        for _ in range(n):
            rows.append([i, i % 10, i // 10, status])
            i += 1
    write("waffle_2024.csv", ["cell", "col", "row", "status"], rows)
    print("   waffle squares:", sq, f"(of {total} rated stocks)")

    # a few headline numbers used in the page text, for checking
    t18 = Sheet(wb["Table 18"])
    print("   import share of seafood eaten:", t18.row(14, "Import share")[t18.n - 1], "%",
          "| apparent consumption (t):", round(t18.row(13, "Total apparent consumption")[t18.n - 1]))
    print("   total value of production ($m):", round(t1.row(42, "Total value")[last] / 1000))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
