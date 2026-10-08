#!/usr/bin/env python3
"""Build the mesh + textures of one UGC item.

    python3 tools/build_ugc.py neko_bucket_hat          # module in tools/items/
    python3 tools/build_ugc.py neko_bucket_hat --only Fraise

Writes into ugc/<SLUG>/:
    obj/<NAME>.obj / .mtl                 source mesh (studs, Roblox axes)
    textures/<NAME>_<Colour>_Albedo.png   1024 px colour maps (plastic)
    build/hat.json                        geometry for the previewer
    build/specs.json                      item metadata + measured stats

Then: tools/blender_export.py <SLUG>  (FBX)  and  tools/validate_ugc.py <SLUG>.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ugclib.bake import bake_albedos  # noqa: E402
from ugclib.export import write_mtl, write_obj, write_preview_json  # noqa: E402
from ugclib.geometry import merged, triangle_count  # noqa: E402
from ugclib.specs import ATTACHMENTS, fit_report  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("item", help="module name in tools/items/ (e.g. neko_bucket_hat)")
    ap.add_argument("--only", nargs="*", help="colourways to bake (default: all)")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--no-textures", action="store_true", help="geometry only (fast)")
    args = ap.parse_args()

    item = importlib.import_module(f"items.{args.item}")
    name, slug = item.NAME, item.SLUG
    out = os.path.join(HERE, "..", "ugc", slug)
    t0 = time.time()
    for sub in ("obj", "textures", "build"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    print(f"[{name}] building geometry ...")
    shells = item.build_shells()
    mesh = merged(shells)
    first = list(item.COLORWAYS)[0]
    write_obj(os.path.join(out, "obj", f"{name}.obj"), f"{name}.mtl", name, mesh, name)
    write_mtl(os.path.join(out, "obj", f"{name}.mtl"), name, f"../textures/{name}_{first}_Albedo.png")
    write_preview_json(os.path.join(out, "build", "hat.json"), mesh)

    if not args.no_textures:
        names = args.only or list(item.COLORWAYS)
        cws = {k: item.COLORWAYS[k] for k in names}
        print(f"[{name}] baking textures ({', '.join(names)}) ...")
        albedos, _ = bake_albedos(shells, cws, item.paint, size=args.size,
                                  ao_radius=getattr(item, "AO_RADIUS", 0.17))
        for k, img in albedos.items():
            img.save(os.path.join(out, "textures", f"{name}_{k}_Albedo.png"), optimize=True)

    V, F, UV, FT = mesh
    lo, hi = V.min(0), V.max(0)
    fit = fit_report(V, item.ASSET_TYPE)
    specs = {
        "name": name,
        "slug": slug,
        "module": args.item,
        "asset_type": item.ASSET_TYPE,
        "accessory_type": ATTACHMENTS[item.ASSET_TYPE][0],
        "attachment": item.ATTACHMENT,
        "aft_body_scale": getattr(item, "AFT_BODY_SCALE", "Classic"),
        "triangles": triangle_count(F),
        "vertices": int(len(V)),
        "shells": [s.name for s in shells],
        "bbox_min": [round(float(x), 4) for x in lo],
        "bbox_max": [round(float(x), 4) for x in hi],
        "bbox_size": [round(float(x), 4) for x in hi - lo],
        "fits": {k: v[0] for k, v in fit.items()},
        "colourways": list(item.COLORWAYS),
        "preview": getattr(item, "PREVIEW", {}),
    }
    with open(os.path.join(out, "build", "specs.json"), "w") as fh:
        json.dump(specs, fh, indent=2, ensure_ascii=False)
    print(f"[{name}] {specs['triangles']} triangles, size {specs['bbox_size']}, fits {specs['fits']}")
    print(f"[{name}] done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
