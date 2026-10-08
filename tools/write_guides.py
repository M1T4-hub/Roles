#!/usr/bin/env python3
"""Write the French import guide of every item and the collection table.

    python3 tools/write_guides.py

For each ugc/<slug>/build/specs.json whose item module defines LISTING,
writes ugc/<slug>/LISEZMOI.md, then rewrites the block between
<!-- collection:start --> and <!-- collection:end --> in the root README.
Run it after build_ugc.py / blender_export.py so sizes and files are current.
"""

from __future__ import annotations

import glob
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from ugclib.specs import LIMITS  # noqa: E402

AFT_LABEL = {"Hat": "Hat", "Hair": "Hair", "Face": "Face", "Neck": "Neck",
             "ShoulderNeck": "Shoulder", "ShoulderCollar": "Shoulder", "ShoulderArm": "Shoulder",
             "Front": "Front", "Back": "Back", "Waist": "Waist"}
TYPE_FR = {"Hat": "chapeau", "Hair": "cheveux", "Face": "visage", "Neck": "cou",
           "Shoulder": "épaule", "Front": "devant", "Back": "dos", "Waist": "taille"}
PRETTY_FR = {"Chatain": "Châtain", "ArcEnCiel": "Arc-en-ciel"}


def fr_num(x, digits=2):
    return f"{x:.{digits}f}".replace(".", ",")


def colour_fr(key, listing=None):
    """French display name: LISTING["colour_fr"] override, else a prettified key."""
    if listing and key in listing.get("colour_fr", {}):
        return listing["colour_fr"][key]
    return PRETTY_FR.get(key, key)


def offset_text(centre):
    """How to move an item that the fitting tool centred on its attachment."""
    parts = []
    dx, dy, dz = centre
    if abs(dy) >= 0.05:
        parts.append(f"{'monte' if dy > 0 else 'descends'}-le de **{fr_num(abs(dy))} stud**")
    if abs(dx) >= 0.05:
        parts.append(f"décale-le de **{fr_num(abs(dx))} stud** vers la "
                     f"{'droite' if dx > 0 else 'gauche'} de l'avatar")
    if abs(dz) >= 0.05:
        parts.append(f"recule-le de **{fr_num(abs(dz))} stud**" if dz > 0
                     else f"avance-le de **{fr_num(abs(dz))} stud**")
    return ", ".join(parts)


def box_text(box):
    (x0, x1), (y0, y1), (z0, z1) = box
    return f"{fr_num(x1 - x0)} × {fr_num(y1 - y0)} × {fr_num(z1 - z0)}"


def guide(specs, listing):
    name = specs["name"]
    tris_fr = f"{specs['triangles']:,}".replace(",", "\u202f")
    acc = specs["accessory_type"]
    att = specs["attachment"]
    size = specs["bbox_size"]
    lo, hi = specs["bbox_min"], specs["bbox_max"]
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    colours = specs["colourways"]
    side = " (côté **droit**)" if att.startswith("Right") else (
        " (côté **gauche**)" if att.startswith("Left") else "")
    lines = [
        f"# {listing['title_fr']} : UGC Roblox ({acc})",
        "",
        listing["description_fr"],
        "",
        f"![Les {len(colours)} coloris](previews/coloris.png)",
        "",
        "## Fichiers",
        "",
        "| Coloris | À importer dans Studio | Texture seule (dépannage) |",
        "|---|---|---|",
    ]
    for c in colours:
        lines.append(f"| {colour_fr(c)} | [`fbx/{name}_{c}.fbx`](fbx/{name}_{c}.fbx) | "
                     f"`textures/{name}_{c}_Albedo.png` |")
    lines += [
        "",
        "Chaque `.fbx` contient le maillage **et** sa texture.",
        "",
        "## Dans Roblox Studio",
        "",
        f"1. **Import 3D** : choisis un des `.fbx` ci-dessus et ne change aucun réglage "
        f"(*Scale Unit* = Studs, *World Forward* = Front, *World Up* = Top). Taille affichée : "
        f"environ **{fr_num(size[0])} × {fr_num(size[1])} × {fr_num(size[2])}** studs, "
        f"**{tris_fr} triangles**.",
        f"2. **Avatar › Accessory** (Accessory Fitting Tool) : *Part* = le MeshPart `{name}`, "
        f"*Asset Type* = **Accessory › {AFT_LABEL[specs['asset_type']]}**{side}, "
        f"*body type* = **{specs['aft_body_scale']}**.",
        f"3. **Placement** : {listing['placement_fr']}",
    ]
    off = offset_text(centre)
    if off:
        lines.append(f"   Si l'outil pose l'objet centré sur son point d'attache (`{att}`) : {off}.")
    lines += [
        "4. **Generate MeshPart Accessory**, puis sélectionne l'Accessory et colle "
        "[`VerifierUGC.lua`](../VerifierUGC.lua) dans la Command Bar : il doit afficher « 🎉 Prêt ».",
        f"5. Clic droit sur l'Accessory › **Save to Roblox** › *Avatar Asset* › **{acc}**.",
        "",
        "## Fiche Marketplace",
        "",
        "| Coloris | Titre EN | Titre FR |",
        "|---|---|---|",
    ]
    for c in colours:
        en = listing["colour_en"].get(c, c)
        lines.append(f"| {colour_fr(c)} | `{listing['title_en']} - {en}` | "
                     f"`{listing['title_fr']} - {colour_fr(c, listing)}` |")
    lines += [
        "",
        "**Description (EN)**",
        "```",
        listing["description_en"],
        "```",
        "**Description (FR)**",
        "```",
        listing["description_fr"],
        "```",
        "",
        "## Conformité (mesurée par `tools/validate_ugc.py`)",
        "",
        "| Règle Roblox | Limite | Cet objet |",
        "|---|---|---|",
        f"| Triangles | ≤ 4 000 | **{specs['triangles']}** |",
        "| Maillage / matériau | 1 / 1 | ✅ |",
        f"| Volumes fermés, normales vers l'extérieur | tous | ✅ {len(specs['shells'])} pièces |",
    ]
    for scale in ("Classic", "Normal", "Slender"):
        box = LIMITS[specs["asset_type"]][scale]
        ok = specs["fits"].get(scale)
        lines.append(f"| Boîte {acc} {scale} | {box_text(box)} | "
                     f"{'✅' if ok else '❌'} {fr_num(size[0])} × {fr_num(size[1])} × {fr_num(size[2])} |")
    lines += ["| Texture | ≤ 1024 px | ✅ 1024 × 1024 PNG |", ""]
    return "\n".join(lines)


def main():
    rows = []
    for spec_path in sorted(glob.glob(os.path.join(ROOT, "ugc", "*", "build", "specs.json"))):
        with open(spec_path) as fh:
            specs = json.load(fh)
        module = importlib.import_module(f"items.{specs['module']}")
        listing = getattr(module, "LISTING", None)
        if not listing:
            print(f"skip {specs['slug']}: no LISTING in tools/items/{specs['module']}.py")
            continue
        path = os.path.join(ROOT, "ugc", specs["slug"], "LISEZMOI.md")
        with open(path, "w", newline="\n") as fh:
            fh.write(guide(specs, listing))
        print("wrote", os.path.relpath(path, ROOT))
        rows.append((specs, listing))

    order = {"Hat": 0, "Hair": 1, "Face": 2, "Back": 3, "Shoulder": 4}
    rows.sort(key=lambda r: (order.get(r[0]["accessory_type"], 9), r[0]["name"]))
    table = ["| | Objet | Type | Coloris | Triangles |", "|---|---|---|---|---|"]
    for specs, listing in rows:
        slug = specs["slug"]
        img = f"ugc/{slug}/previews/{specs['name']}_{specs['colourways'][0]}.png"
        acc = specs["accessory_type"]
        table.append(
            f"| <img src=\"{img}\" width=\"120\"> | **[{listing['title_fr']}](ugc/{slug}/LISEZMOI.md)**"
            f"<br>{listing['title_en']} | {acc} ({TYPE_FR.get(acc, acc)}) | "
            f"{', '.join(colour_fr(c, listing) for c in specs['colourways'])} | {specs['triangles']} |")
    readme = os.path.join(ROOT, "README.md")
    text = open(readme).read()
    a, b = "<!-- collection:start -->", "<!-- collection:end -->"
    if a in text and b in text:
        head, rest = text.split(a, 1)
        _, tail = rest.split(b, 1)
        text = head + a + "\n" + "\n".join(table) + "\n" + b + tail
        with open(readme, "w", newline="\n") as fh:
            fh.write(text)
        print("updated README collection table")
    else:
        print("README has no collection markers; table:\n" + "\n".join(table))


if __name__ == "__main__":
    main()
