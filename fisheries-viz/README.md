# Fishing the Australian ocean

FIT3179 Data Visualisation 2 (Semester 2, 2026). Single scrolling page built with Vega-Lite.

**Status: all 13 charts use real data.** Charts 4 to 9 come from the ABARES statistical tables and the SAFS 2024 stock counts.
Charts 1 to 3 come from the ABARES Fishery Status Reports 2025 map data, and charts 10 to 12 from its stock status history
(Commonwealth stocks only). The newest year in the statistics workbook, 2024-25, is preliminary and is labelled that way.

## Run it locally

```
python3 -m http.server 8000
```

Open <http://localhost:8000>. (Opening `index.html` by double-click will not work, because browsers
block `fetch` on `file://` pages.) `preview.html` is a single-file copy for quick looks only; delete it before submitting.

## Folder layout

| Path | What it is |
| --- | --- |
| `index.html` | Page structure, narrative text, credits |
| `css/style.css` | Layout and typography (Fraunces headings, Source Sans 3 body) |
| `js/main.js` | Loads each spec with vega-embed. `PLACEHOLDER_DATA` is now `false`, which hides the draft banner and tags |
| `specs/fig01…fig12*.vl.json` | One readable Vega-Lite JSON file per chart |
| `specs/theme.json` | Shared fonts and colours |
| `data/` | The data each spec loads |
| `tools/` | Helper scripts (see below) |

## Charts, idioms and data

| # | Chart | Idiom | Counts as | Data file | Data status |
| - | --- | --- | --- | --- | --- |
| 01 | Fishing intensity by year, with slider | Choropleth map (patches) | Map | `fishing_intensity.geojson` | Real (ALLFSY rfl) |
| 02 | Four-year snapshots | Small-multiple maps | Map | same | Real (ALLFSY rfl) |
| 03 | Area fished 2010 vs 2024, by ocean region | Dumbbell plot | Advanced | `area_fished_by_region.csv` | Real (ALLFSY fp) |
| 04 | Value of farmed vs wild seafood, 2010-11 to 2024-25 | Stacked area | Basic | `production_value.csv` | Real (Tables 3, 4) |
| 05 | Tonnes by species group, 2024-25 | Pareto (bars plus running share) | Advanced | `catch_by_group_latest.csv` | Real (Table 3) |
| 06 | Wild catch: tonnes vs dollars by year | Connected scatterplot | Advanced | `wild_catch_trend.csv` | Real (Table 3) |
| 07 | Production by state, farmed share | Proportional symbol map | Map | `production_by_state.csv` | Real (Tables 5 to 11) |
| 08 | Value vs tonnes per Commonwealth fishery | Scatterplot with price-per-kg lines | Basic | `fisheries.csv` | Real (Tables 1, 12) |
| 09 | Stock status 2024 (national, SAFS) | Waffle (unit) chart | Advanced | `waffle_2024.csv` | Real (SAFS, check counts) |
| 10 | Commonwealth stock status over time | Streamgraph | Advanced | `stock_status.csv` | Real (ABARES Appendix A) |
| 11 | Stock status 2008 vs 2024 | Slope chart | Advanced | same | Real (ABARES Appendix A) |
| 12 | Healthy share of stocks by fishery and year | Annotated heatmap | Advanced | `healthy_by_fishery.csv` | Real (ABARES Appendix A) |
| 13 | Years each part of the ocean was fished, 2010 to 2024 | Hexbin map | Map | `fishing_persistence_hex.geojson` | Real (ALLFSY fp) |

That is 13 charts and 4 map idioms (choropleth, small multiples, proportional symbol, hexbin; chart 13 sits after chart 3 on the page), plus 7 advanced non-map idioms (the brief asks for more than 10 charts,
at least 3 maps and at least 8 advanced idioms).

## Where the real data comes from

`tools/make_real_data.py` writes the real files from the workbook *Australian fisheries and aquaculture
statistics 2025* (ABARES, CC BY 4.0, DOI 10.25814/4w7h-cw80). It checks the label of every row it reads,
so it stops with an error if ABARES re-orders a table.

```
python3 tools/make_real_data.py path/to/02_DataTables_AustFishAquacStats_2025_v1.0.0_1.xlsx
```

Workbook layout: labels in column B, units in column C, one financial year per column from D (1998-99)
to AD (2024-25p). The figures use the 15 most recent years (2010-11 to 2024-25p); a year is stored as the
year it ends, so 2024-25 is 2025.

The waffle is **not** in the workbook. Its four counts (318 sustainable, 16 recovering, 13 depleting, 45 depleted)
are typed into `WAFFLE_COUNTS` at the top of `tools/make_real_data.py` from the SAFS 2024 page on
fish.gov.au. **Check them on the site before submitting.** The 39 "negligible" and 72 "undefined" stocks are
left out on purpose and the page says so.

## Maps and stock status (charts 1 to 3 and 10 to 12)

```
python3 tools/make_map_and_status_data.py ALLFSY_rfl_2010-2024.zip ALLFSY_fp_2010-2024.zip 32_FishStatus2025_FullHistoryStatus_1.0.0.csv
```

Things to know, because the page text depends on them:

- **Intensity classes change by year.** "Low" is under 60 kg of catch per km2 in 2010 and under 300 in 2024. Each patch keeps its
  cut-off in the `range` property, and the tooltip shows it. The page says to compare where the dark patches are, not how many.
- **Outlines are simplified** (Douglas-Peucker, about 3 km) so the file is about 0.7 MB. Exterior rings are written clockwise because
  d3 (and so Vega) needs that winding order.
- **The footprint layers have no fishery name**, so chart 3 groups the 1 degree squares into six ocean regions by the position of each
  square (see `REGIONS` in the script). That grouping is ours, and the page says so.
- **Stock status is Commonwealth-only** and is a different scheme from the national SAFS waffle. The script combines the two ABARES
  measures (biomass and fishing mortality) into one status per stock and year: Overfished if biomass is overfished; Overfishing if fishing
  mortality is too high; Healthy if neither; Uncertain if either is uncertain; Not assessed if both are. 2004 is the first year with
  both measures.
- **2024 has 46 of 102 stocks "Not assessed"**, so charts 11 and 12 use shares of assessed stocks and the page explains the gap.
- **Fisheries are grouped** for chart 12 (`group_of` in the script), for example all SESSF trawl and scalefish sectors together.

## Helper scripts

- `python3 tools/build.py` regenerates **all** the specs (it does not write data). Specs are plain JSON and can also be edited by hand.
- `python3 tools/make_map_and_status_data.py <rfl.zip> <fp.zip> <status.csv>` writes the data for charts 1 to 3 and 10 to 12 (see above).
- `python3 tools/make_real_data.py <workbook>` regenerates the real data files (see above).
- `python3 tools/check_specs.py` checks that every field a spec uses exists in its data.
- `python3 tools/check_facts.py` checks that every number quoted in the page text matches the data.
- `python3 tools/bundle_preview.py` rebuilds `preview.html`.
- `python3 tools/render_mockup.py` redraws `draft-mockup.jpg`, a static picture of the page (drawn with matplotlib,
  so fonts and the Australia outline differ from the real page).

## Still to do before submission

- [ ] Open the page in a browser (see "Run it locally") and check the console: no Vega-Lite chart has been drawn in a browser yet
- [ ] Check the SAFS counts for the waffle on fish.gov.au, and add URLs, download dates and licences for the SAFS, ALLFSY and stock status sources
- [ ] Check the layout against your submitted sketch (the brief says the page must adhere to it); chart 3 is now by ocean region, not by fishery
- [ ] Read the "What to take away" paragraph and make it yours
- [ ] Add your name and update the AI acknowledgement in the footer
- [ ] Check the page at about 1280 px wide: no sideways scrolling
- [ ] Host on GitHub Pages and confirm the specs and data are publicly reachable; delete `preview.html` and `draft-mockup.jpg`
- [ ] Moodle: page URL, sketch PDF URL, and the written What/Why/How description
