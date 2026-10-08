#!/usr/bin/env python3
"""Check an exported item against Roblox's rigid-accessory rules.

    python3 tools/validate_ugc.py <slug>          # e.g. neko-bucket-hat
    python3 tools/validate_ugc.py --all

Reads ugc/<slug>/build/specs.json, obj/<Name>.obj, the textures and the FBX
files, prints a pass/fail table and exits non-zero if anything fails.
Limits come from https://create.roblox.com/docs/avatar/rigid-accessories/specifications
(see tools/ugclib/specs.py).
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ugclib.specs import ATTACHMENTS, MAX_TEXTURE, MAX_TRIANGLES, fit_report  # noqa: E402


def load_obj(path):
    V, VT, F, FT, mats = [], [], [], [], set()
    with open(path) as fh:
        for line in fh:
            p = line.split()
            if not p:
                continue
            if p[0] == "v":
                V.append([float(x) for x in p[1:4]])
            elif p[0] == "vt":
                VT.append([float(x) for x in p[1:3]])
            elif p[0] == "usemtl":
                mats.add(p[1])
            elif p[0] == "f":
                F.append([int(c.split("/")[0]) - 1 for c in p[1:]])
                FT.append([int(c.split("/")[1]) - 1 for c in p[1:]])
    return np.array(V), np.array(VT), F, FT, mats


def shells_of(F, nv):
    parent = list(range(nv))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for f in F:
        for v in f[1:]:
            ra, rb = find(f[0]), find(v)
            if ra != rb:
                parent[ra] = rb
    groups = defaultdict(list)
    for i, f in enumerate(F):
        groups[find(f[0])].append(i)
    return list(groups.values())


def validate(slug):
    out = os.path.normpath(os.path.join(HERE, "..", "ugc", slug))
    with open(os.path.join(out, "build", "specs.json")) as fh:
        specs = json.load(fh)
    name, asset_type = specs["name"], specs["asset_type"]
    V, VT, F, FT, mats = load_obj(os.path.join(out, "obj", f"{name}.obj"))
    results = []

    def check(name, ok, detail):
        results.append((name, bool(ok), detail))

    tris = sum(len(f) - 2 for f in F)
    check("Triangles <= 4000", tris <= MAX_TRIANGLES, f"{tris}")
    check("No n-gons (only tris/quads)", all(len(f) <= 4 for f in F),
          f"max {max(len(f) for f in F)} sides")
    check("Single material", len(mats) == 1, ", ".join(sorted(mats)))

    # Watertight: every directed edge has exactly one opposite twin.
    E = Counter()
    for f in F:
        for i in range(len(f)):
            E[(f[i], f[(i + 1) % len(f)])] += 1
    open_edges = sum(1 for (a, b), c in E.items() if c != 1 or E.get((b, a), 0) != 1)
    check("Watertight (no holes, consistent winding)", open_edges == 0,
          f"{open_edges} bad edges")

    # Every shell closed with outward normals (positive signed volume).
    shells = shells_of(F, len(V))
    vols = []
    for s in shells:
        vol = 0.0
        for fi in s:
            f = F[fi]
            for i in range(1, len(f) - 1):
                vol += np.dot(V[f[0]], np.cross(V[f[i]], V[f[i + 1]])) / 6.0
        vols.append(vol)
    check("All shells face outward (no backfaces)", all(v > 0 for v in vols),
          f"{len(shells)} shells")

    # Degenerate triangles.
    areas = []
    for f in F:
        for i in range(1, len(f) - 1):
            areas.append(np.linalg.norm(np.cross(V[f[i]] - V[f[0]], V[f[i + 1]] - V[f[0]])) / 2)
    check("No degenerate triangles", min(areas) > 1e-8, f"min area {min(areas):.2e} stud^2")

    check("UVs inside 0..1", VT.min() >= 0 and VT.max() <= 1,
          f"[{VT.min():.3f}, {VT.max():.3f}]")

    check("Attachment matches asset type",
          specs["attachment"] in ATTACHMENTS[asset_type][1],
          f"{specs['attachment']} for {asset_type}")
    for scale, (ok, need) in fit_report(V, asset_type).items():
        required = scale in ("Classic", specs.get("aft_body_scale", "Classic"))
        label = f"Fits {asset_type} box ({scale}{'' if required else ', optional'})"
        check(label, ok or not required, ("" if ok else "OUTSIDE  ") + need)

    pngs = sorted(glob.glob(os.path.join(out, "textures", f"{name}_*_Albedo.png")))
    check("One albedo per colourway", len(pngs) == len(specs["colourways"]),
          f"{len(pngs)} textures / {len(specs['colourways'])} colourways")
    for png in pngs:
        im = Image.open(png)
        ok = im.size[0] <= MAX_TEXTURE and im.size[1] <= MAX_TEXTURE and im.mode in ("RGB", "RGBA")
        check(f"Texture {os.path.basename(png)}", ok, f"{im.size[0]}x{im.size[1]} {im.mode}")

    fbxs = sorted(glob.glob(os.path.join(out, "fbx", f"{name}_*.fbx")))
    check("FBX files present (one per colourway)", len(fbxs) == len(specs["colourways"]),
          f"{len(fbxs)} files")
    for fbx in fbxs:
        with open(fbx, "rb") as fh:
            head = fh.read(23)
        check(f"FBX {os.path.basename(fbx)}", head.startswith(b"Kaydara FBX Binary"),
              f"{os.path.getsize(fbx) // 1024} KB, binary")

    width = max(len(r[0]) for r in results)
    failed = 0
    print(f"== {name} ({asset_type}, {specs['attachment']})")
    for label, ok, detail in results:
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label:<{width}}  {detail}")
    print(f"{len(results) - failed}/{len(results)} checks passed\n")
    return failed


def main():
    slugs = sys.argv[1:]
    if not slugs or slugs == ["--all"]:
        root = os.path.join(HERE, "..", "ugc")
        slugs = sorted(d for d in os.listdir(root)
                       if os.path.exists(os.path.join(root, d, "build", "specs.json")))
    failed = sum(validate(s) for s in slugs)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
