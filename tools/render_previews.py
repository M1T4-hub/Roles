#!/usr/bin/env python3
"""Render preview images of one item (three.js in headless Chromium).

    python3 tools/render_previews.py <slug>             # all colourways + views
    python3 tools/render_previews.py <slug> --quick     # first colourway, front only
    python3 tools/render_previews.py <slug> --out DIR   # write somewhere else

Uses the cameras in the item's PREVIEW dict (relative to its attachment).
Writes ugc/<slug>/previews/<Name>_<Colour>.png, <Name>_<view>.png for the
extra views of the first colourway, and coloris.png (all colourways side by
side). Needs `npm install` in tools/render once.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(HERE, "render")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--size", type=int, default=800)
    args = ap.parse_args()

    item_dir = os.path.normpath(os.path.join(HERE, "..", "ugc", args.slug))
    with open(os.path.join(item_dir, "build", "specs.json")) as fh:
        specs = json.load(fh)
    name, att = specs["name"], specs["attachment"]
    views = specs.get("preview") or {"front": {"cam": "2,0.8,-3", "target": "0,0,0"}}
    out = os.path.abspath(args.out or os.path.join(item_dir, "previews"))
    os.makedirs(out, exist_ok=True)
    colours = specs["colourways"][:1] if args.quick else specs["colourways"]

    def query(colour, view):
        v = views[view]
        return (f"item={args.slug}&albedo={name}_{colour}_Albedo.png&attach={att}"
                f"&cam={v['cam']}&target={v['target']}&w={args.size}&h={args.size}"
                + (f"&fov={v['fov']}" if "fov" in v else ""))

    jobs = []
    front = "front" if "front" in views else list(views)[0]
    for c in colours:
        jobs += [os.path.join(out, f"{name}_{c}.png"), query(c, front)]
    if not args.quick:
        for view in views:
            if view != front:
                jobs += [os.path.join(out, f"{name}_{colours[0]}_{view}.png"), query(colours[0], view)]
    subprocess.run(["node", os.path.join(RENDER, "render.mjs"), *jobs], check=True, cwd=RENDER)

    if len(colours) > 1:
        tiles = [os.path.join(out, f"{name}_{c}.png") for c in colours]
        subprocess.run(["convert", *tiles, "-resize", "400x400", "+append",
                        os.path.join(out, "coloris.png")], check=True)
    for f in os.listdir(out):
        if f.endswith(".png"):
            subprocess.run(["convert", os.path.join(out, f), "-strip", os.path.join(out, f)], check=True)
    print("\n".join(sorted(os.path.join(out, f) for f in os.listdir(out))))


if __name__ == "__main__":
    sys.exit(main())
