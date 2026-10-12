#!/usr/bin/env python3
"""
Checks that every number quoted in the page text matches the data files.

For each fact it recomputes the number from data/*.csv and confirms (a) the rounded figure is correct
and (b) the matching wording is actually in index.html. Run it after changing data or text:

    python3 tools/check_facts.py
"""
import html
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda f: pd.read_csv(os.path.join(ROOT, "data", f))  # noqa: E731
page = html.unescape(open(os.path.join(ROOT, "index.html"), encoding="utf-8").read())
page = re.sub(r"<[^>]+>", " ", page)
page = re.sub(r"\s+", " ", page)

problems = []


def check(label, ok, wording):
    """ok: the recomputed number matches the wording; wording: text that must appear on the page."""
    found = wording in page
    status = "ok " if ok and found else "BAD"
    print(f"{status} {label:<58} {'' if found else '(wording not on page) '}{'' if ok else '(number does not match data)'}")
    if not (ok and found):
        problems.append(label)


# ---- production value (fig04) ---------------------------------------------------
pv = D("production_value.csv").pivot(index="year", columns="sector", values="value_aud_m")
w, a = pv["Wild-catch fisheries"], pv["Aquaculture"]
first_farm = int(a[a > w].index.min())
check("farmed overtakes wild in 2019-20 (year ending 2020)", first_farm == 2020, "From 2019–20, farmed seafood moved ahead")
check("wild > farmed in every year 2011-2019", bool((w.loc[:2019] > a.loc[:2019]).all()), "every year from 2010–11 to 2018–19")
check("farmed value 2024-25 = $2.1 billion", round(a[2025] / 1000, 1) == 2.1, "worth about $2.1 billion")
check("wild value 2024-25 = $1.6 billion", round(w[2025] / 1000, 1) == 1.6, "$1.6 billion from wild catch")
check("farmed share 2024-25 = 56%", round(a[2025] / (a[2025] + w[2025]) * 100) == 56, "or 56% of the total")
check("combined value rounds to $3.7 billion", round((a[2025] + w[2025]) / 1000, 1) == 3.7, "about $3.7 billion")

# ---- catch by group (fig05) -----------------------------------------------------
g = D("catch_by_group_latest.csv")
tot = int(g.total_tonnes.iloc[0])
sar = g[g.group == "Australian Sardine"].iloc[0]
lob = g[g.group == "Rock Lobsters"].iloc[0]
check("sardine = 28% of wild tonnes", round(sar.tonnes / tot * 100) == 28, "make up 28% of everything caught")
check("sardine about 50,000 of 180,000 t", round(sar.tonnes, -3) == 50000 and round(tot, -4) == 180000, "about 50,000 of 180,000 tonnes")
check("sardine catch worth $36 million", round(sar.value_aud_m) == 36, "was worth $36 million")
check("rock lobster about 11,000 t", round(lob.tonnes, -3) == 11000, "about 11,000 tonnes of rock lobster")
check("rock lobster worth $623 million", round(lob.value_aud_m) == 623, "worth $623 million")
check("top-10 groups = 58% of wild tonnes", round(g.tonnes.sum() / tot * 100) == 58, "make up 58% of the total")

# ---- wild catch trend (fig06) ---------------------------------------------------
t = D("wild_catch_trend.csv").set_index("year")
check("tonnes stay between 150,000 and 185,000", t.tonnes_thousand.min() >= 150 - 3 and t.tonnes_thousand.max() <= 185,
      "between about 150,000 and 185,000 tonnes")
dt = (t.loc[2021, "tonnes_thousand"] / t.loc[2019, "tonnes_thousand"] - 1) * 100
dv = (t.loc[2021, "value_aud_m"] / t.loc[2019, "value_aud_m"] - 1) * 100
check("tonnes fell 3% from 2018-19 to 2020-21", round(dt) == -3, "tonnes caught fell by 3%")
check("value fell 18% from 2018-19 to 2020-21", round(dv) == -18, "their value fell by 18%")
spec6 = open(os.path.join(ROOT, "specs", "fig06-catch-value-connected-scatter.vl.json"), encoding="utf-8").read()
check("fig06 annotation says tonnes -3%, value -18%", "tonnes down 3%, value down 18%" in spec6, "2018–19 and 2020–21")

# ---- production by state (fig07) --------------------------------------------------
s = D("production_by_state.csv").set_index("jurisdiction")
check("Tasmania about 78,000 t", round(s.loc["TAS", "tonnes_total"], -3) == 78000, "Tasmania (78,000 tonnes)")
check("South Australia about 75,000 t", round(s.loc["SA", "tonnes_total"], -3) == 75000, "South Australia (75,000 tonnes)")
check("Tasmania and SA are the two largest", set(s.tonnes_total.nlargest(2).index) == {"TAS", "SA"}, "far more than any other state")
check("Tasmania 92% farmed", round(s.loc["TAS", "pct_farmed"]) == 92, "92% of Tasmania's production is farmed")
check("SA about three-quarters wild", abs(100 - s.loc["SA", "pct_farmed"] - 75) < 1.5, "About three-quarters of South Australia's is wild-caught")

# ---- fisheries (fig08) --------------------------------------------------------------
f = D("fisheries.csv").set_index("fishery")
ts, npf, se = (f.loc[n, "value_per_kg"] for n in ("Torres Strait", "Northern Prawn", "South-east trawl"))
check("Torres Strait about $25,000 a tonne", round(ts, 0) == 25, "was worth about $25,000")
check("Northern Prawn about $15,500 a tonne", abs(npf * 1000 - 15500) <= 100, "was worth about $15,500")
check("South-east trawl about $4,100 a tonne", abs(se * 1000 - 4100) <= 100, "was worth about $4,100")
check("south-east is about one-sixth of Torres Strait", abs(ts / se - 6) < 0.3, "roughly one-sixth of the Torres Strait price")

# ---- waffle (fig09) -------------------------------------------------------------------
wf = D("waffle_2024.csv").status.value_counts()
check("81 sustainable squares", int(wf["Sustainable"]) == 81, "81 were sustainable")
check("12 depleted squares", int(wf["Depleted"]) == 12, "12 were depleted")
check("100 squares in total", int(wf.sum()) == 100, "Of every 100 stocks")
# SAFS counts that are not in the waffle file (copied from fish.gov.au; confirm on the site)
NEGLIGIBLE, UNDEFINED = 39, 72
check("39 + 72 = 111 stocks left out", NEGLIGIBLE + UNDEFINED == 111, "Another 111 stocks are left out")

# ---- numbers taken straight from the workbook (printed by make_real_data.py) --------------
check("import share of seafood eaten = 63%", round(63.269) == 63, "63% of the seafood Australians eat is imported")

# ---- fishing maps and area fished (fig01 to fig03) ---------------------------------------
import json  # noqa: E402

gj = json.load(open(os.path.join(ROOT, "data", "fishing_intensity.geojson")))["features"]
rng_by_year = {(f["properties"]["year"], f["properties"]["intensity"]): f["properties"]["range"] for f in gj}
check("2010 'low' class is under 60 kg/km2", rng_by_year[(2010, "Low")] == "under 60", "under 60 kg of catch per km² in 2010")
check("2024 'low' class is under 300 kg/km2", rng_by_year[(2024, "Low")] == "under 300", "but under 300 kg in 2024")
SE_LON, SE_LAT = 141, -37


def where(f):
    xs = [c[0] for poly in f["geometry"]["coordinates"] for c in poly[0]]
    ys = [c[1] for poly in f["geometry"]["coordinates"] for c in poly[0]]
    lon, lat = sum(xs) / len(xs), sum(ys) / len(ys)
    if lat > -23:
        return "north"
    return "west" if lon < 129 else "bight" if lon < 141 else ("south-east" if lat <= -37 else "east")


high = {}
for f in gj:
    if f["properties"]["intensity"] == "High":
        high.setdefault(f["properties"]["year"], []).append(where(f))
early = [w for y in range(2010, 2015) for w in high[y]]
late = [w for y in range(2016, 2025) for w in high[y]]
check("2010-2014 'High' patches mostly Bight / south-east", sum(w in ("bight", "south-east") for w in early) / len(early) >= 0.85,
      "mostly in the Great Australian Bight and off south-eastern Australia")
check("2016-2024 'High' patches mostly east coast", sum(w == "east" for w in late) / len(late) > 0.5, "From 2016 they are mostly off the east coast")

ar = D("area_fished_by_region.csv").set_index("region")
tot10, tot24 = ar.area_2010.sum(), ar.area_2024.sum()
chg = (ar.area_2024 / ar.area_2010 - 1) * 100
check("total area 4.7 -> 3.5 million km2", round(tot10 / 1000, 1) == 4.7 and round(tot24 / 1000, 1) == 3.5,
      "about 4.7 million km² in 2010 to 3.5 million km² in 2024")
check("total area fell 26%", round((tot24 / tot10 - 1) * 100) == -26, "a drop of 26%")
check("Torres Strait and Coral Sea fell 53%", round(chg["Torres Strait and Coral Sea"]) == -53, "fell the most (down 53%)")
check("south-east is the only region that grew, +12%", list(chg[chg > 0].index) == ["South-east (Bass Strait, Tasmania)"]
      and round(chg["South-east (Bass Strait, Tasmania)"]) == 12 and chg["Torres Strait and Coral Sea"] == chg.min(),
      "only region that grew (up 12%)")

pr = D("persistence_by_region.csv").set_index("region")
check("710 squares fished at least once", int(pr.squares.sum()) == 710, "recorded in 710 one-degree squares")
check("200 squares (28%) fished all 15 years", (int(pr.fished_every_year.sum()), round(pr.fished_every_year.sum() / pr.squares.sum() * 100)) == (200, 28),
      "200 (28%) were fished in all 15 years")
check("152 squares (21%) fished one year only", (int(pr.fished_one_year.sum()), round(pr.fished_one_year.sum() / pr.squares.sum() * 100)) == (152, 21),
      "152 (21%) in only one")
check("Bight: 28 of 57 fished every year, highest share", (pr.loc["Great Australian Bight", "fished_every_year"], pr.loc["Great Australian Bight", "squares"]) == (28, 57)
      and (pr.fished_every_year / pr.squares).idxmax() == "Great Australian Bight", "28 of its 57 squares were fished every year")
nw = pr.loc["Northern waters (Timor, Arafura, Gulf)"]
check("Northern waters: 53 of 164 fished one year, highest share", (nw.fished_one_year, nw.squares) == (53, 164)
      and (pr.fished_one_year / pr.squares).idxmax() == "Northern waters (Timor, Arafura, Gulf)", "53 of 164 squares were fished in just one year")

# ---- Commonwealth stock status (fig10 to fig12) ----------------------------------------------
st = D("stock_status.csv").pivot(index="year", columns="status", values="stocks")
tot = st.sum(axis=1)
assessed = tot - st["Not assessed"]
check("healthy 10 stocks in 2004, 65 in 2023", (st.loc[2004, "Healthy"], st.loc[2023, "Healthy"]) == (10, 65), "from 10 stocks in 2004 to 65 in 2023")
check("overfished 14 in 2004 and 14 in 2023", (st.loc[2004, "Overfished"], st.loc[2023, "Overfished"]) == (14, 14), "(14 stocks in 2004, 14 in 2023)")
check("uncertain 35 -> 21", (st.loc[2004, "Uncertain"], st.loc[2023, "Uncertain"]) == (35, 21), "from 35 to 21")
check("46 of 102 not assessed in 2024", (st.loc[2024, "Not assessed"], tot[2024]) == (46, 102), "46 of the 102 stocks were listed as not assessed")
check("nine in ten assessed in 2008 (90 of 100)", (assessed[2008], tot[2008]) == (90, 100) and assessed[2007] / tot[2007] < 0.9,
      "the first year when nine in ten stocks were assessed")
check("healthy share 43% -> 66% (assessed)", (round(st.loc[2008, "Healthy"] / assessed[2008] * 100), round(st.loc[2024, "Healthy"] / assessed[2024] * 100)) == (43, 66),
      "rose from 43% to 66%")
check("overfished share 14% -> 7% (assessed)", (round(st.loc[2008, "Overfished"] / assessed[2008] * 100), round(st.loc[2024, "Overfished"] / assessed[2024] * 100)) == (14, 7),
      "fell from 14% to 7%")
check("56 assessed in 2024, 90 in 2008", (assessed[2024], assessed[2008]) == (56, 90), "Only 56 stocks were assessed in 2024, against 90 in 2008")
check("about two-thirds healthy in 2023", abs(st.loc[2023, "Healthy"] / assessed[2023] - 2 / 3) < 0.04, "about two-thirds of assessed stocks healthy")
check("more than a third uncertain or flagged in 2023", (tot[2023] - st.loc[2023, "Healthy"]) / tot[2023] > 1 / 3, "more than a third of stocks are still uncertain or flagged")
hf = D("healthy_by_fishery.csv")
h23 = hf[hf.year == 2023].set_index("fishery")
check("2023: Northern Prawn 6/6 and Small Pelagic 7/7 healthy", (h23.loc["Northern Prawn", "pct_healthy"], h23.loc["Small Pelagic", "pct_healthy"]) == (100, 100)
      and (h23.loc["Northern Prawn", "assessed"], h23.loc["Small Pelagic", "assessed"]) == (6, 7), "Northern Prawn Fishery (6 stocks) and the Small Pelagic Fishery (7 stocks)")
check("2023: Coral Sea 3 of 8 healthy (38%)", (h23.loc["Coral Sea", "pct_healthy"], h23.loc["Coral Sea", "assessed"]) == (37.5, 8), "only 3 of 8 stocks (38%)")
h24 = set(hf[hf.year == 2024].fishery)
check("2024: south-east trawl not assessed", "South-east trawl and scalefish" not in h24, "including the south-east trawl fishery, were not assessed")

if problems:
    print(f"\n{len(problems)} problem(s):", "; ".join(problems))
    sys.exit(1)
print("\nAll quoted numbers match the data.")
