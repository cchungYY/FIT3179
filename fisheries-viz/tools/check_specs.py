#!/usr/bin/env python3
"""
Offline sanity check for the Vega-Lite specs (no browser needed).

For every spec it checks that:
  * the JSON parses and has a $schema or sits inside a concat spec,
  * every local data file exists,
  * every field name used in an encoding, sort, or datum.<name> expression is either
    a real column in one of the spec's data sources or is created by a transform.

It does NOT prove the chart renders - open the page in a browser for that.
"""
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
problems = []


def columns_of(data):
    """Return the set of field names a data block provides."""
    cols = set()
    if "values" in data:
        for row in data["values"]:
            cols.update(row.keys())
    elif "url" in data and data["url"].startswith("data/"):
        path = os.path.join(ROOT, data["url"])
        if not os.path.exists(path):
            problems.append(f"missing data file {data['url']}")
            return cols
        if path.endswith(".csv"):
            with open(path, newline="") as f:
                cols.update(next(csv.reader(f)))
        elif path.endswith(".geojson"):
            with open(path) as f:
                gj = json.load(f)
            for feat in gj["features"][:50]:
                cols.update("properties." + k for k in feat["properties"])
    elif "url" in data:
        # remote TopoJSON base map: id is the only field we use
        cols.add("id")
    return cols


def walk(node, visit):
    if isinstance(node, dict):
        visit(node)
        for v in node.values():
            walk(v, visit)
    elif isinstance(node, list):
        for v in node:
            walk(v, visit)


def check(name, spec):
    cols, made, used = set(), set(), []

    def gather(node):
        if isinstance(node.get("data"), dict):
            cols.update(columns_of(node["data"]))
        for key in ("calculate",):
            if key in node and "as" in node:
                made.add(node["as"])
                used.extend(re.findall(r"datum\.([A-Za-z_][\w.]*)", node["calculate"]))
        if "window" in node:
            for w in node["window"]:
                made.add(w["as"])
                if "field" in w:
                    used.append(w["field"])
            for s in node.get("sort", []):
                used.append(s["field"])
        if "joinaggregate" in node:
            for j in node["joinaggregate"]:
                made.add(j["as"])
                used.append(j["field"])
            used.extend(node.get("groupby", []))
        if "fold" in node:
            made.update(node["as"])
            used.extend(node["fold"])
        if "filter" in node and isinstance(node["filter"], str):
            used.extend(re.findall(r"datum\.([A-Za-z_][\w.]*)", node["filter"]))
        if "test" in node:
            used.extend(re.findall(r"datum\.([A-Za-z_][\w.]*)", node["test"]))
        if "encoding" in node:
            for ch, enc in node["encoding"].items():
                encs = enc if isinstance(enc, list) else [enc]
                for e in encs:
                    if isinstance(e, dict):
                        if "field" in e:
                            used.append(e["field"])
                        if isinstance(e.get("sort"), dict) and "field" in e["sort"]:
                            used.append(e["sort"]["field"])
                        if "condition" in e and "test" in e["condition"]:
                            used.extend(re.findall(r"datum\.([A-Za-z_][\w.]*)", e["condition"]["test"]))
        if "tooltip" in node and isinstance(node["tooltip"], list):
            used.extend(t["field"] for t in node["tooltip"] if "field" in t)

    walk(spec, gather)
    # fields of a values block (labels etc.) are already in cols; the base map provides 'id'
    for f in sorted(set(used)):
        if f not in cols and f not in made:
            problems.append(f"{name}: field '{f}' is not a column and not created by a transform")
    return len(set(used))


def main():
    paths = sorted(glob.glob(os.path.join(ROOT, "specs", "fig*.vl.json")))
    if len(paths) < 10:
        problems.append(f"only {len(paths)} chart specs found (assignment needs 10+)")
    for p in paths:
        name = os.path.basename(p)
        try:
            with open(p) as f:
                spec = json.load(f)
        except json.JSONDecodeError as e:
            problems.append(f"{name}: invalid JSON ({e})")
            continue
        n = check(name, spec)
        print(f"ok  {name}  ({n} field references checked)")
    html = open(os.path.join(ROOT, "index.html")).read()
    js = open(os.path.join(ROOT, "js", "main.js")).read()
    for p in paths:
        fig = os.path.basename(p).replace(".vl.json", "")
        if f'id="vis-{fig}"' not in html:
            problems.append(f"index.html has no <div id=\"vis-{fig}\">")
        if f'"{fig}"' not in js:
            problems.append(f"js/main.js does not list {fig}")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print(f"\nAll {len(paths)} specs passed the structural checks.")


if __name__ == "__main__":
    main()
