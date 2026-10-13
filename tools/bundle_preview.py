#!/usr/bin/env python3
"""
Builds preview.html: index.html with the CSS, JS, specs and data inlined so the
whole page works from a single file (handy for a quick look before pushing to GitHub).
The GitHub version of the site does NOT use this file - it loads specs/ and data/ directly.
"""
import copy
import glob
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def inline(node):
    if isinstance(node, dict):
        data = node.get("data")
        if isinstance(data, dict) and str(data.get("url", "")).startswith("data/"):
            path = os.path.join(ROOT, data["url"])
            if path.endswith(".csv"):
                node["data"] = {"values": json.loads(pd.read_csv(path).to_json(orient="records"))}
            else:
                with open(path) as f:
                    node["data"] = {"values": json.load(f), "format": data["format"]}
        for v in node.values():
            inline(v)
    elif isinstance(node, list):
        for v in node:
            inline(v)


bundle = {}
with open(os.path.join(ROOT, "specs", "theme.json")) as f:
    bundle["theme"] = json.load(f)
for p in sorted(glob.glob(os.path.join(ROOT, "specs", "fig*.vl.json"))):
    with open(p) as f:
        spec = json.load(f)
    inline(spec)
    bundle[os.path.basename(p).replace(".vl.json", "")] = spec

html = open(os.path.join(ROOT, "index.html")).read()
css = open(os.path.join(ROOT, "css", "style.css")).read()
js = open(os.path.join(ROOT, "js", "main.js")).read()

html = html.replace('<link rel="stylesheet" href="css/style.css">', f"<style>\n{css}\n</style>")
payload = json.dumps(bundle, separators=(",", ":")).replace("</", "<\\/")
html = html.replace(
    '<script src="js/main.js"></script>',
    f"<script>window.__BUNDLE__ = {payload};</script>\n<script>\n{js}\n</script>",
)
with open(os.path.join(ROOT, "preview.html"), "w") as f:
    f.write(html)
print(f"preview.html written ({len(html) / 1024:.0f} KB)")
