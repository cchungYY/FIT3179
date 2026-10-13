#!/usr/bin/env python3
"""
Renders the draft page as one tall JPEG (draft-mockup.jpg) using matplotlib.

This is a STATIC MOCKUP of index.html, not a screenshot of it:
  * all text comes from index.html and all chart titles from specs/*.vl.json, so it stays in step with the page,
  * the charts are redrawn with matplotlib from the same data files (not rendered by Vega-Lite),
  * fonts are DejaVu (Fraunces / Source Sans 3 are not installed here),
  * the Australia outline is hand-drawn and approximate.
"""
import glob
import html as htmllib
import json
import math
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import PatchCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402
from matplotlib.patches import Ellipse, Polygon, Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = lambda f: pd.read_csv(os.path.join(ROOT, "data", f))  # noqa: E731

# ------------------------------------------------------------------ constants
W, DPI, X0 = 1280, 100, 100
SERIF, SANS = "DejaVu Serif", "DejaVu Sans"
INK, MUTED, TEAL, FARM, CORAL = "#0b2a3c", "#5d7384", "#0f6c7a", "#c8641f", "#e0803a"
MIST, SAND = "#eef4f7", "#f6f1e6"
STATUS = ["Sustainable", "Recovering", "Depleting", "Depleted"]
STATUS_C = ["#1f7a74", "#78b8a0", "#eaa83a", "#a63a32"]
CW = ["Healthy", "Uncertain", "Overfishing", "Overfished", "Not assessed"]
CW_C = ["#1f7a74", "#a3b4bf", "#eaa83a", "#a63a32", "#e9eef1"]
INTENSITY = ["Low", "Medium", "High"]
INTENSITY_C = ["#cfe6ee", "#4fa3b8", "#0b4f6c"]
FARM_CMAP = LinearSegmentedColormap.from_list("farm", [TEAL, "#6b7a64", FARM])

PAGE = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
SPECS = {os.path.basename(p)[:5]: json.load(open(p, encoding="utf-8"))
         for p in sorted(glob.glob(os.path.join(ROOT, "specs", "fig*.vl.json")))}


def pt(px):
    return px * 72 / DPI


# ------------------------------------------------------------------ reading text from the page
def strip(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def section_html(sec_id):
    return re.search(rf'<section class="[^"]*" id="{sec_id}">(.*?)</section>', PAGE, re.S).group(1)


def head_of(sec_id):
    s = section_html(sec_id)
    g = lambda pat: strip(re.search(pat, s, re.S).group(1))  # noqa: E731
    return g(r'<p class="step">(.*?)</p>'), g(r"<h2>(.*?)</h2>"), g(r'<p class="lede">(.*?)</p>')


def fig_block(prefix):
    """Items after a figure: [(kind, text, tbc)], and whether it carries the placeholder tag."""
    m = re.search(rf'id="vis-{prefix}-[^"]*"', PAGE)
    rest = PAGE[m.end():]
    cut = len(rest)
    for pat in (r'id="vis-fig\d\d', r"</section>"):
        n = re.search(pat, rest)
        if n:
            cut = min(cut, n.start())
    block = rest[:cut]
    head = re.split(r"<h3|<p", block)[0]
    items = []
    for tag_, attrs, inner in re.findall(r"<(h3|p)([^>]*)>(.*?)</\1>", block, re.S):
        kind = "h3" if tag_ == "h3" else ("how" if "how" in attrs else ("caption" if "caption" in attrs else "p"))
        items.append((kind, strip(inner), 'class="tbc"' in attrs or 'class="tbc"' in inner))
    return items, 'class="ph"' in head


# ------------------------------------------------------------------ drawing primitives (px, origin top-left)
fig = None
H = 0
_renderer = None


def P(x, y, w, h):
    ax = fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])
    ax.set_facecolor("none")
    return ax


def T(x, y, s, size=17, color=INK, weight="normal", family=SANS, ha="left", va="top", style="normal", **kw):
    return fig.text(x / W, 1 - y / H, s, fontsize=pt(size), color=color, fontweight=weight,
                    family=family, ha=ha, va=va, fontstyle=style, **kw)


def band(y0, h, color):
    fig.add_artist(Rectangle((0, 1 - (y0 + h) / H), 1, h / H, transform=fig.transFigure, fc=color, ec="none", zorder=-5))


def rect(x, y, w, h, **kw):
    fig.add_artist(Rectangle((x / W, 1 - (y + h) / H), w / W, h / H, transform=fig.transFigure, **kw))


def dot(cx, cy, d, **kw):
    fig.add_artist(Ellipse((cx / W, 1 - cy / H), d / W, d / H, transform=fig.transFigure, **kw))


def text_w(s, size, weight="normal", family=SANS, style="normal"):
    t = fig.text(0, 0, s, fontsize=pt(size), fontweight=weight, family=family, fontstyle=style)
    w = t.get_window_extent(_renderer).width
    t.remove()
    return w


def wrap_px(s, width, size, weight="normal", family=SANS, style="normal"):
    lines, cur = [], ""
    for word in s.split():
        trial = (cur + " " + word).strip()
        if cur and text_w(trial, size, weight, family, style) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    return lines


def para(x, y, s, width, size=17, color=INK, draw=True, lh=1.5, bg=None, **kw):
    lines = wrap_px(s, width, size, **{k: v for k, v in kw.items() if k in ("weight", "family", "style")})
    h = len(lines) * size * lh
    if draw:
        if bg:
            rect(x - 4, y - 2, width + 8, h + 2, fc=bg, ec="none")
        T(x, y, "\n".join(lines), size, color, linespacing=lh, **kw)
    return h


def tag(x, y):
    T(x, y, " PLACEHOLDER DATA ", 9, "#5c4500", "bold", ha="right",
      bbox=dict(boxstyle="round,pad=0.25", fc="#fff3cd", ec="#ecd58a", lw=0.8))


def text_col(x, y, items, w, draw=True):
    """The heading, body and 'how to read it' notes beside a chart. Returns its height."""
    cy = y
    for kind, text, tbc in items:
        bg = "#fff3cd" if tbc else None
        if kind == "h3":
            h = para(x, cy, text, w, 22, INK, draw, 1.25, weight="bold", family=SERIF)
            cy += h + 8
        elif kind == "p":
            cy += para(x, cy, text, w, 16, INK, draw, bg=bg) + 8
        elif kind == "how":
            h = para(x + 14, cy, text, w - 14, 14, MUTED, draw, 1.5)
            if draw:
                rect(x, cy, 3, h, fc=CORAL, ec="none")
            cy += h + 10
        elif kind == "caption":
            cy += para(x, cy, text, w, 16, "#29475a", draw, bg=bg) + 8
    return cy - y


def chart_head(x, y, key, width, ph):
    t = SPECS[key]["title"]
    T(x, y, t["text"], 17, INK, "bold", SERIF)
    sub = t.get("subtitle", [])
    sub = sub if isinstance(sub, list) else [sub]
    for i, line in enumerate(sub):
        T(x, y + 28 + i * 17, line, 12.5, MUTED)
    if ph:
        tag(x + width, y + 3)
    return 28 + len(sub) * 17 + 18


def style_axes(ax, left=True, bottom=True, grid=None):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_visible(left)
    ax.spines["bottom"].set_visible(bottom)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#b8c7d0")
    ax.tick_params(colors="#40586a", labelsize=pt(12), length=3, color="#b8c7d0")
    if grid:
        ax.grid(axis=grid, color="#e6edf1", lw=0.8)
        ax.set_axisbelow(True)


def axis_title(ax, xlabel=None, ylabel=None, color="#40586a"):
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=pt(12), color=color, fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=pt(12), color=color, fontweight="bold")


# ------------------------------------------------------------------ maps
def merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


LON0, LON1, LAT0, LAT1 = 111, 163, -48, -8
MAINLAND = [(142.5, -10.7), (143.5, -14), (145.3, -15), (146.3, -19), (149, -21.5), (151, -23.5),
            (153.2, -25), (153.6, -28.5), (153, -31), (151.2, -33.9), (150, -37), (149, -37.8),
            (146.5, -39), (144.5, -38.4), (141.5, -38.2), (139.5, -36), (138.5, -35.5), (137.5, -33),
            (135.5, -34.8), (134, -32.8), (131, -31.5), (126, -32.3), (123.5, -33.8), (118, -35),
            (115.2, -34.4), (115, -31), (113.5, -26), (114, -22), (118, -20), (122, -18),
            (125, -14.5), (129, -14.8), (131, -12), (136, -12), (136.5, -15), (140, -17.5), (141.5, -13)]
TASMANIA = [(144.7, -40.7), (148.3, -40.9), (148, -43), (146, -43.6), (145, -42)]


def chaikin(pts, n=3):
    pts = list(pts)
    for _ in range(n):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            out += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]),
                    (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        pts = out
    return pts


LAND = [[(math.radians(x), merc(y)) for x, y in chaikin(p)] for p in (MAINLAND, TASMANIA)]
GRID = json.load(open(os.path.join(ROOT, "data", "fishing_intensity.geojson")))["features"]


def map_axes(x, y, w):
    h = w * (merc(LAT1) - merc(LAT0)) / math.radians(LON1 - LON0)
    ax = P(x, y, w, h)
    ax.set_xlim(math.radians(LON0), math.radians(LON1))
    ax.set_ylim(merc(LAT0), merc(LAT1))
    ax.axis("off")
    return ax, h


def draw_land(ax, lw=0.8):
    for poly in LAND:
        ax.add_patch(Polygon(poly, closed=True, fc="#f1e7d0", ec="#9a8f78", lw=lw, zorder=5))


def draw_cells(ax, year, lw=0.25):
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    patches, colors = [], []
    for f in GRID:
        p = f["properties"]
        if p["year"] != year:
            continue
        for poly in f["geometry"]["coordinates"]:
            verts, codes = [], []
            for ring in poly:
                pts = [(math.radians(a), merc(b)) for a, b in ring]
                verts += pts
                codes += [Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY]
            patches.append(PathPatch(Path(verts, codes)))
            colors.append(INTENSITY_C[INTENSITY.index(p["intensity"])])
    ax.add_collection(PatchCollection(patches, fc=colors, ec="white", lw=lw, zorder=2))


def intensity_legend(x, y, horizontal=False):
    T(x, y, "Fishing intensity", 12, "#40586a", "bold")
    for i, (n, c) in enumerate(zip(INTENSITY, INTENSITY_C)):
        xx, yy = (x + i * 80, y + 22) if horizontal else (x, y + 22 + i * 20)
        rect(xx, yy, 13, 13, fc=c, ec="#9fb4c0", lw=0.5)
        T(xx + 19, yy - 1, n, 12, "#40586a")


def status_legend(x, y, cols, colw, names=None, colors=None):
    for i, (s, c) in enumerate(zip(names or STATUS, colors or STATUS_C)):
        xx, yy = x + (i % cols) * colw, y + (i // cols) * 22
        rect(xx, yy, 13, 13, fc=c, ec="none")
        T(xx + 19, yy - 1, s, 12, "#40586a")


# ====================================================================== charts (each returns its height)
def fig01(x, y, ph):
    h0 = chart_head(x, y, "fig01", 700, ph)
    ax, mh = map_axes(x, y + h0, 680)
    draw_cells(ax, 2024)
    draw_land(ax)
    for lon, lat, s in [(138.5, -11.0, "Gulf of Carpentaria"), (130, -36.2, "Great Australian Bight"),
                        (146.5, -40.9, "Bass Strait"), (156, -19, "Coral Sea"), (156, -35, "Tasman Sea")]:
        ax.text(math.radians(lon), merc(lat), s, fontsize=pt(11), color="#5a7280", style="italic", ha="center",
                va="center", zorder=8, path_effects=[pe.withStroke(linewidth=3, foreground="white")])
    intensity_legend(x + 6, y + h0 + mh - 92)
    sy = y + h0 + mh + 30
    T(x, sy - 10, "Year", 14, INK, "bold")
    rect(x + 52, sy - 1.5, 320, 3, fc=TEAL, ec="none")
    dot(x + 372, sy, 18, fc=TEAL, ec="white", lw=2)
    T(x + 392, sy - 10, "2024", 14, INK, "bold")
    return h0 + mh + 60


def fig02(x, y, ph):
    h0 = chart_head(x, y, "fig02", 1080, ph)
    mh = 0
    for i, yr in enumerate((2010, 2015, 2020, 2024)):
        mx = x + i * 251
        T(mx, y + h0, str(yr), 14, INK, "bold")
        ax, mh = map_axes(mx, y + h0 + 26, 235)
        draw_cells(ax, yr, 0.2)
        draw_land(ax, 0.6)
    intensity_legend(x + 440, y + h0 + 26 + mh + 14, horizontal=True)
    return h0 + 26 + mh + 62


def fig03(x, y, ph):
    h0 = chart_head(x, y, "fig03", 700, ph)
    fis = CSV("area_fished_by_region.csv").sort_values("area_2010", ascending=False).reset_index(drop=True)
    fis = fis.rename(columns={"region": "fishery"})
    ax = P(x + 255, y + h0 + 38, 400, 280)
    n = len(fis)
    for i, r in fis.iterrows():
        ax.plot([r.area_2010, r.area_2024], [i, i], color="#9fb4c0", lw=3, zorder=1)
    ax.scatter(fis.area_2010, range(n), s=pt(11) ** 2 * 2.2, color="#94a9b6", zorder=3, label="2010")
    ax.scatter(fis.area_2024, range(n), s=pt(11) ** 2 * 2.2, color=TEAL, zorder=3, label="2024")
    ax.set_yticks(range(n))
    ax.set_yticklabels([textwrap_label(s, 28) for s in fis.fishery], fontsize=pt(11))
    ax.invert_yaxis()
    axis_title(ax, "Area fished (thousand km²)")
    style_axes(ax, left=False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.7, 1.04), ncol=2, frameon=False, fontsize=pt(12), handletextpad=0.2)
    return h0 + 38 + 280 + 52


def fig13(x, y, ph):
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    h0 = chart_head(x, y, "fig13", 700, ph)
    ax, mh = map_axes(x, y + h0, 680)
    cmap = LinearSegmentedColormap.from_list("hx", ["#f4efd8", "#6fb1a0", "#0b4f6c"])
    norm = Normalize(1, 15)
    hexes = json.load(open(os.path.join(ROOT, "data", "fishing_persistence_hex.geojson")))["features"]
    for f in hexes:
        ring = f["geometry"]["coordinates"][0]
        ax.add_patch(Polygon([(math.radians(a), merc(b)) for a, b in ring], closed=True,
                             fc=cmap(norm(f["properties"]["avg_years"])), ec="white", lw=0.6, zorder=2))
    draw_land(ax)
    T(x + 6, y + h0 + mh - 80, "Typical years fished (of 15)", 12, "#40586a", "bold")
    cax = P(x + 6, y + h0 + mh - 54, 180, 12)
    cax.imshow(np.linspace(0, 1, 100)[None, :], aspect="auto", cmap=cmap)
    cax.axis("off")
    for v, xx in ((1, 6), (5, 6 + 180 * 4 / 14), (10, 6 + 180 * 9 / 14), (15, 186)):
        T(x + xx, y + h0 + mh - 36, str(v), 11, "#40586a", ha="center")
    return h0 + mh + 20


def textwrap_label(s, n):
    import textwrap
    return textwrap.fill(s, n)


def fig04(x, y, ph):
    h0 = chart_head(x, y, "fig04", 700, ph)
    pv = CSV("production_value.csv")
    wild = pv[pv.sector == "Wild-catch fisheries"].sort_values("year")
    farm = pv[pv.sector == "Aquaculture"].sort_values("year")
    ax = P(x + 62, y + h0 + 34, 620, 300)
    ax.stackplot(wild.year, wild.value_aud_m, farm.value_aud_m, colors=[TEAL, FARM], alpha=0.92)
    ax.set_xlim(2011, 2025)
    ax.set_xticks(range(2011, 2026, 2))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    axis_title(ax, ylabel="Value (A$ millions)")
    style_axes(ax, grid="y")
    ax.axvline(2020, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=5)
    ax.annotate("2019–20: farmed seafood moves ahead", xy=(2020, ax.get_ylim()[1]), xytext=(-6, -12),
                textcoords="offset pixels", ha="right", va="top", fontsize=pt(12), fontweight="bold", color=INK,
                zorder=6)
    for i, (lab, c) in enumerate([("Wild-catch fisheries", TEAL), ("Aquaculture", FARM)]):
        xx = x + 62 + i * 190
        rect(xx, y + h0 + 6, 13, 13, fc=c, ec="none")
        T(xx + 19, y + h0, lab, 12, "#40586a")
    return h0 + 34 + 300 + 50


def fig05(x, y, ph):
    h0 = chart_head(x, y, "fig05", 700, ph)
    cg = CSV("catch_by_group_latest.csv").sort_values("tonnes", ascending=False).reset_index(drop=True)
    tot = cg.total_tonnes.iloc[0]
    cg["cum"] = cg.tonnes.cumsum() / tot
    ax = P(x + 70, y + h0 + 20, 560, 300)
    ax.bar(range(len(cg)), cg.tonnes, color=TEAL, width=0.7, zorder=2)
    ax.set_xticks(range(len(cg)))
    ax.set_xticklabels(cg.group, rotation=35, ha="right", fontsize=pt(11.5))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    axis_title(ax, ylabel="Tonnes caught")
    style_axes(ax, grid="y")
    ax2 = ax.twinx()
    ax2.plot(range(len(cg)), cg.cum, color="#2a2f36", lw=2.5, marker="o", ms=6, zorder=4)
    ax2.set_ylim(0, 1)
    ax2.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax2.set_ylabel("Running share of all wild-caught tonnes", fontsize=pt(12), color="#2a2f36", fontweight="bold")
    ax2.tick_params(colors="#40586a", labelsize=pt(12), length=3)
    for s in ("top", "left", "bottom"):
        ax2.spines[s].set_visible(False)
    ax2.spines["right"].set_color("#b8c7d0")
    ax2.annotate(f"Top 10 groups = {cg.cum.iloc[-1]:.0%} of all wild catch", xy=(len(cg) - 1, cg.cum.iloc[-1]),
                 xytext=(-8, 14), textcoords="offset pixels", ha="right", va="bottom", fontsize=pt(12),
                 fontweight="bold", color="#2a2f36")
    return h0 + 20 + 300 + 100


def fig06(x, y, ph):
    h0 = chart_head(x, y, "fig06", 700, ph)
    t = CSV("wild_catch_trend.csv")
    ax = P(x + 70, y + h0 + 14, 560, 340)
    ax.plot(t.tonnes_thousand, t.value_aud_m, color="#9fb4c0", lw=2.5, zorder=2)
    cmap = LinearSegmentedColormap.from_list("yr", ["#a9d3de", "#0b3a4d"])
    ax.scatter(t.tonnes_thousand, t.value_aud_m, s=pt(10) ** 2 * 1.6, c=cmap(Normalize(t.year.min(), t.year.max())(t.year)),
               ec="white", lw=1.5, zorder=3)
    for r in t.itertuples():
        if r.year in (2011, 2015, 2019, 2021, 2025):
            dy = -45 if r.year == 2021 else 40
            ax.text(r.tonnes_thousand, r.value_aud_m + dy, r.label, ha="center", va="center", fontsize=pt(11),
                    fontweight="bold", color=INK, zorder=6)
    ax.text(146, 1870, "2018–19 to 2020–21: tonnes down 3%, value down 18%", ha="left", va="center", fontsize=pt(12),
            fontweight="bold", color=FARM)
    ax.set_xlim(145, 190)
    ax.set_ylim(1200, 1900)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    axis_title(ax, "Wild-caught seafood (thousand tonnes)", "Value (A$ millions)")
    style_axes(ax, grid="y")
    return h0 + 14 + 340 + 56


def fig07(x, y, ph):
    h0 = chart_head(x, y, "fig07", 700, ph)
    ax, mh = map_axes(x, y + h0, 680)
    draw_land(ax)
    st = CSV("production_by_state.csv")
    mx = st.tonnes_total.max()
    size = lambda v: 250 + (7000 - 250) * v / mx  # noqa: E731  (area in px^2, as in the spec)
    for r in st.itertuples():
        sx, sy = math.radians(r.lon), merc(r.lat)
        ax.scatter([sx], [sy], s=size(r.tonnes_total) * 0.5184, color=FARM_CMAP(r.pct_farmed / 100), alpha=0.92,
                   ec="white", lw=1.5, zorder=6)
        ax.text(sx, sy, r.jurisdiction, fontsize=pt(13), fontweight="bold", color="white", ha="center", va="center",
                zorder=9)
    ly = y + h0 + mh - 118
    T(x + 6, ly, "Tonnes produced", 12, "#40586a", "bold")
    for i, v in enumerate([mx / 4, mx / 2, mx]):
        rad = math.sqrt(size(v) / math.pi)
        cx = x + 34 + i * 82
        dot(cx, ly + 36 + 30, 2 * rad, fc="#9fb4c0", alpha=0.7, ec="white", lw=1)
        T(cx, ly + 36 + 30 + rad + 3, f"{int(round(v, -2)):,}", 11, "#40586a", ha="center")
    gx = x + 300
    T(gx, ly, "Farmed share (%)", 12, "#40586a", "bold")
    grad = P(gx, ly + 24, 180, 12)
    grad.imshow(np.linspace(0, 1, 100)[None, :], aspect="auto", cmap=FARM_CMAP)
    grad.axis("off")
    for v, ha in ((0, "left"), (50, "center"), (100, "right")):
        T(gx + 180 * v / 100, ly + 40, str(v), 11, "#40586a", ha=ha)
    return h0 + mh + 20


def fig08(x, y, ph):
    h0 = chart_head(x, y, "fig08", 700, ph)
    fs = CSV("fisheries.csv")
    ax = P(x + 75, y + h0 + 14, 560, 340)
    for k in (5, 10, 20):
        x_end = 90 * 1000 / k
        ax.plot([0, x_end], [0, 90], color="#aab9c3", lw=1.5, ls=(0, (5, 4)), zorder=1)
        ax.annotate(f"${k} per kg", (x_end, 90), xytext=(-5, -12), textcoords="offset pixels", ha="right",
                    va="top", fontsize=pt(11), color=MUTED)
    ax.scatter(fs.tonnes, fs.value_aud_m, s=pt(10) ** 2 * 2.6, color=TEAL, alpha=0.9, ec="white", lw=1.5, zorder=4)
    for r in fs.itertuples():
        right = r.tonnes >= 12000
        ax.annotate(r.fishery, (r.tonnes, r.value_aud_m), xytext=(-10 if right else 10, -14 if right else 8),
                    textcoords="offset pixels", ha="right" if right else "left", va="center", fontsize=pt(12),
                    color=INK, zorder=6)
    ax.set_xlim(0, 20000)
    ax.set_ylim(0, 90)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    axis_title(ax, "Tonnes caught", "Value of the catch (A$ millions)")
    style_axes(ax, grid="y")
    return h0 + 14 + 340 + 56


def fig09(x, y, ph):
    h0 = chart_head(x, y, "fig09", 340, ph)
    wf = CSV("waffle_2024.csv")
    ax = P(x, y + h0 + 6, 300, 300)
    for r in wf.itertuples():
        ax.add_patch(Rectangle((r.col - 0.46, r.row - 0.46), 0.92, 0.92, fc=STATUS_C[STATUS.index(r.status)], ec="none"))
    ax.set_xlim(-0.5, 9.5)
    ax.set_ylim(9.5, -0.5)
    ax.axis("off")
    status_legend(x, y + h0 + 6 + 316, 2, 150)
    return h0 + 6 + 316 + 50


def fig10(x, y, ph):
    h0 = chart_head(x, y, "fig10", 1080, ph)
    ss = CSV("stock_status.csv")
    yrs = sorted(ss.year.unique())
    series = [ss[ss.status == s].sort_values("year").stocks.values for s in CW]
    ax = P(x + 10, y + h0 + 10, 960, 320)
    ax.stackplot(yrs, series, baseline="sym", colors=CW_C)
    ax.set_xlim(min(yrs), max(yrs))
    ax.set_xticks(range(2004, 2025, 2))
    style_axes(ax, left=False)
    ax.set_yticks([])
    status_legend(x + 180, y + h0 + 10 + 320 + 34, 5, 130, CW, CW_C)
    return h0 + 10 + 320 + 70


def fig11(x, y, ph):
    h0 = chart_head(x, y, "fig11", 700, ph)
    ss = CSV("stock_status.csv")
    ss = ss[ss.status != "Not assessed"]
    ax = P(x, y + h0 + 6, 600, 380)
    shares = {}
    for s, c in zip(CW[:4], CW_C[:4]):
        d = ss[ss.status == s].set_index("year").stocks
        a, b = d[2008] / ss[ss.year == 2008].stocks.sum(), d[2024] / ss[ss.year == 2024].stocks.sum()
        shares[s] = (a, b, c)
        ax.plot([2008, 2024], [a, b], color=c, lw=3)
        ax.scatter([2008, 2024], [a, b], color=c, s=60, zorder=3)
    for k, (xx, ha) in enumerate([(2007.6, "right"), (2024.4, "left")]):
        last = None
        for s in sorted(shares, key=lambda q: -shares[q][k])[:3]:
            v = shares[s][k]
            ax.text(xx, v, f"{s}  {v:.0%}", ha=ha, va="center", fontsize=pt(11), color=INK, fontweight="bold")
    ax.set_xlim(1999, 2033)
    ax.set_xticks([2008, 2024])
    ax.set_yticks([])
    style_axes(ax, left=False)
    ax.tick_params(axis="x", labelsize=pt(13))
    status_legend(x + 60, y + h0 + 6 + 380 + 26, 4, 130, CW[:4], CW_C[:4])
    return h0 + 6 + 380 + 62


def fig12(x, y, ph):
    h0 = chart_head(x, y, "fig12", 700, ph)
    hm = CSV("healthy_by_fishery.csv")
    hm["label"] = hm.fishery + " (" + hm.stocks_listed.astype(str) + ")"
    piv = hm.pivot(index="label", columns="year", values="pct_healthy")
    piv = piv.loc[piv.mean(axis=1).sort_values(ascending=False).index]
    cmap = LinearSegmentedColormap.from_list("h", ["#f6e3c4", "#9fcbb8", "#0f5c57"])
    norm = Normalize(0, 100)
    ax = P(x + 235, y + h0 + 6, 460, 330)
    for i, g in enumerate(piv.index):
        for j, yr in enumerate(piv.columns):
            v = piv.loc[g, yr]
            if np.isnan(v):
                continue
            ax.add_patch(Rectangle((j, i), 1, 1, fc=cmap(norm(v)), ec="white", lw=2))
            ax.text(j + 0.5, i + 0.5, f"{v:.0f}", ha="center", va="center", fontsize=pt(9),
                    color="white" if v > 55 else INK)
    ax.set_xlim(0, len(piv.columns))
    ax.set_ylim(len(piv.index), 0)
    ax.set_xticks(np.arange(len(piv.columns)) + 0.5)
    ax.set_xticklabels(piv.columns, fontsize=pt(10))
    ax.set_yticks(np.arange(len(piv.index)) + 0.5)
    ax.set_yticklabels(piv.index, fontsize=pt(12))
    style_axes(ax, left=False, bottom=False)
    ax.tick_params(length=0)
    T(x + 235, y + h0 + 6 + 330 + 30, "% healthy", 12, "#40586a", "bold")
    cax = P(x + 235, y + h0 + 6 + 330 + 56, 200, 12)
    cax.imshow(np.linspace(0, 1, 100)[None, :], aspect="auto", cmap=cmap)
    cax.axis("off")
    T(x + 235, y + h0 + 6 + 330 + 72, "0", 11, "#40586a")
    T(x + 435, y + h0 + 6 + 330 + 72, "100", 11, "#40586a", ha="right")
    return h0 + 6 + 330 + 100


# ====================================================================== the page
def build(height):
    global fig, H, _renderer
    H = height
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor="white")
    _renderer = fig.canvas.get_renderer()
    y = 0

    # hero
    kicker = strip(re.search(r'<p class="kicker">(.*?)</p>', PAGE, re.S).group(1)).upper()
    h1 = strip(re.search(r"<h1>(.*?)</h1>", PAGE, re.S).group(1))
    stand = strip(re.search(r'<p class="standfirst">(.*?)</p>', PAGE, re.S).group(1))
    hero_top = y
    T(X0, y + 56, kicker, 14, "#9fd3dc", "bold")
    T(X0, y + 90, h1, 60, "white", "bold", SERIF)
    sh = para(X0, y + 180, stand, 640, 20, "#dcebf0")
    hero_h = 180 + sh + 56
    band(hero_top, hero_h, "#0d3a4d")
    y += hero_h

    sections = [
        ("where", "white", [("fig01", False, False), ("fig02", False, True), ("fig03", True, False), ("fig13", False, False)]),
        ("what", MIST, [("fig04", False, False), ("fig05", True, False), ("fig06", False, False),
                        ("fig07", True, False), ("fig08", False, False)]),
        ("sustainability", "white", [("fig09", False, False), ("fig10", False, True), ("fig11", True, False),
                                     ("fig12", False, False)]),
    ]
    charts = {"fig01": fig01, "fig02": fig02, "fig03": fig03, "fig13": fig13, "fig04": fig04, "fig05": fig05, "fig06": fig06,
              "fig07": fig07, "fig08": fig08, "fig09": fig09, "fig10": fig10, "fig11": fig11, "fig12": fig12}
    for sec_id, bg, figs in sections:
        sec_top = y
        step, h2, lede = head_of(sec_id)
        T(X0, y + 72, step.upper(), 13, TEAL, "bold")
        T(X0, y + 96, h2, 34, INK, "bold", SERIF)
        lh = para(X0, y + 152, lede, 640, 19, "#29475a")
        y += 152 + lh + 48
        for key, flip, full in figs:
            items, ph = fig_block(key)
            if full:
                ch = charts[key](X0, y, ph)
                cap = [i for i in items if i[0] == "caption"]
                th = text_col(X0, y + ch, cap, 680) if cap else 0
                y += ch + th + 56
            else:
                xc, xt = (X0 + 380, X0) if flip else (X0, X0 + 740)
                ch = charts[key](xc, y, ph)
                th = text_col(xt, y, items, 340, draw=False)
                text_col(xt, y + max(0, (ch - th) / 2), items, 340)
                y += max(ch, th) + 56
        y += 24
        band(sec_top, y - sec_top, bg)

    # takeaway
    tk = re.search(r'<section class="takeaway">(.*?)</section>', PAGE, re.S).group(1)
    top = y
    T(X0 + 180, y + 56, strip(re.search(r"<h2>(.*?)</h2>", tk, re.S).group(1)), 34, INK, "bold", SERIF)
    th = para(X0 + 180, y + 112, strip(re.search(r"<p[^>]*>(.*?)</p>", tk, re.S).group(1)), 720, 19, bg="#fff3cd")
    band(top, 112 + th + 56, SAND)
    y += 112 + th + 56

    # credits
    foot = re.search(r"<footer[^>]*>(.*?)</footer>", PAGE, re.S).group(1)
    top = y
    T(X0, y + 56, strip(re.search(r"<h2>(.*?)</h2>", foot, re.S).group(1)), 26, "white", "bold", SERIF)
    ends = []
    for k, (hd, ul) in enumerate(re.findall(r"<h3>(.*?)</h3>\s*<ul>(.*?)</ul>", foot, re.S)):
        cx = X0 + k * 560
        T(cx, y + 116, strip(hd).upper(), 13, "#9fd3dc", "bold")
        cy = y + 142
        for li in re.findall(r"<li>(.*?)</li>", ul, re.S):
            cy += para(cx, cy, "•  " + strip(li), 470 if k == 0 else 520, 14, "#dcebf0") + 8
        ends.append(cy)
    fh = max(ends) - y + 48
    band(top, fh, "#0b2a3c")
    return y + fh


def main():
    probe = build(30000)       # first pass on a tall canvas: measures the page height
    plt.close(fig)
    build(int(math.ceil(probe)))
    out = os.path.join(ROOT, "draft-mockup.jpg")
    fig.savefig(out, dpi=DPI, format="jpeg", pil_kwargs={"quality": 92})
    print(f"wrote {out}  ({W}x{int(math.ceil(probe))}px)")


if __name__ == "__main__":
    main()
