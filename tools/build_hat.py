#!/usr/bin/env python3
"""Build every deliverable of the Neko Bucket Hat UGC.

    python3 tools/build_hat.py            # all colourways
    python3 tools/build_hat.py --only Fraise

Writes into ugc/neko-bucket-hat/:
    obj/NekoBucketHat.obj / .mtl                 source mesh (studs, Roblox axes)
    textures/NekoBucketHat_<Colour>_Albedo.png   1024 px colour maps (plastic)
    build/hat.json                               geometry for the previewer
    build/specs.json                             measured stats

The Studio-ready FBX files (fbx/) are then made by tools/blender_export.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import hat_geometry as G  # noqa: E402
import hat_texture as T  # noqa: E402
from hat_export import write_mtl, write_obj, write_preview_json  # noqa: E402

OUT = os.path.join(HERE, "..", "ugc", "neko-bucket-hat")
NAME = "NekoBucketHat"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="colourways to bake (default: all)")
    ap.add_argument("--size", type=int, default=1024)
    args = ap.parse_args()

    t0 = time.time()
    for sub in ("obj", "textures", "build"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    print("Building geometry ...")
    shells = G.build_hat()
    mesh = G.merged(shells)
    write_obj(os.path.join(OUT, "obj", f"{NAME}.obj"), f"{NAME}.mtl", NAME, mesh, NAME)
    write_mtl(os.path.join(OUT, "obj", f"{NAME}.mtl"), NAME, f"../textures/{NAME}_Fraise_Albedo.png")
    write_preview_json(os.path.join(OUT, "build", "hat.json"), mesh)

    names = args.only or list(T.COLORWAYS)
    cws = {k: T.COLORWAYS[k] for k in names}
    print(f"Baking textures ({', '.join(names)}) ...")
    albedos, _ = T.bake(shells, cws, size=args.size)
    for k, img in albedos.items():
        img.save(os.path.join(OUT, "textures", f"{NAME}_{k}_Albedo.png"), optimize=True)

    V, F, UV, FT = mesh
    lo, hi = V.min(0), V.max(0)
    centre = (lo + hi) / 2
    specs = {
        "name": NAME,
        "triangles": G.triangle_count(F),
        "vertices": int(len(V)),
        "shells": [s.name for s in shells],
        "bbox_min": [round(float(x), 4) for x in lo],
        "bbox_max": [round(float(x), 4) for x in hi],
        "bbox_size": [round(float(x), 4) for x in hi - lo],
        "bbox_centre": [round(float(x), 4) for x in centre],
        # Studio recentres an imported MeshPart on its bounding box, so the
        # HatAttachment sits at (origin - centre) in the Handle's space.
        "hat_attachment_offset": [round(float(-x), 4) for x in centre],
        "colourways": list(T.COLORWAYS),
    }
    with open(os.path.join(OUT, "build", "specs.json"), "w") as fh:
        json.dump(specs, fh, indent=2)
    print(json.dumps(specs, indent=2))
    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
