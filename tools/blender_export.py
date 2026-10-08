"""Export Studio-ready FBX files with Blender (run with the `bpy` module).

    <python-with-bpy> tools/blender_export.py

Uses the export settings from Roblox's creator docs:
  * Path Mode = Copy + Embed Textures   (the texture travels inside the .fbx)
  * Apply Scalings = FBX Unit Scale     (1 Blender unit = 1 stud in Studio)
  * Forward = Z, Up = Y                 (keeps Roblox's front = -Z)

Then re-imports each FBX and checks it matches the source mesh exactly.
"""

from __future__ import annotations

import json
import os
import sys

import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "ugc", "neko-bucket-hat"))
NAME = "NekoBucketHat"
COLOURS = ["Fraise", "Matcha", "Minuit", "Nuage", "Choco"]
AXES = dict(forward_axis="Z", up_axis="Y")


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def mesh_report(obj):
    """Geometry checks equivalent to Blender's 3D-Print toolbox."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    bm_tris = sum(len(f.verts) - 2 for f in bm.faces)
    # Every connected shell must enclose positive volume (normals outward).
    shells, bad_shells = 0, 0
    seen = set()
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, island = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            island.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        vol = 0.0
        for g in island:
            vs = [v.co for v in g.verts]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
        shells += 1
        bad_shells += vol <= 0
    bm.free()
    lo = [min(v.co[i] for v in me.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in me.vertices) for i in range(3)]
    return dict(triangles=bm_tris, vertices=len(me.vertices), faces=len(me.polygons),
                non_manifold_edges=non_manifold, boundary_edges=boundary,
                degenerate_faces=degenerate, ngons=ngons, shells=shells,
                inward_shells=bad_shells, uv_layers=len(me.uv_layers),
                materials=len(me.materials), bbox_min=lo, bbox_max=hi)


def world_bbox(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


def main():
    os.makedirs(os.path.join(OUT, "fbx"), exist_ok=True)
    report = {}
    for colour in COLOURS:
        reset()
        bpy.ops.wm.obj_import(filepath=os.path.join(OUT, "obj", f"{NAME}.obj"), **AXES)
        obj = bpy.context.selected_objects[0]
        obj.name = obj.data.name = NAME
        bpy.context.view_layer.objects.active = obj

        # One material, whose base colour is this colourway's albedo (packed).
        mat = obj.data.materials[0]
        mat.name = NAME
        png = os.path.join(OUT, "textures", f"{NAME}_{colour}_Albedo.png")
        img = bpy.data.images.load(png, check_existing=True)
        img.name = f"{NAME}_{colour}_Albedo.png"
        tex_nodes = [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"]
        tex_nodes[0].image = img
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Roughness"].default_value = 0.5
        img.pack()

        src = mesh_report(obj)
        src_bbox = world_bbox(obj)

        fbx = os.path.join(OUT, "fbx", f"{NAME}_{colour}.fbx")
        bpy.ops.export_scene.fbx(
            filepath=fbx, use_selection=False, object_types={"MESH"},
            apply_scale_options="FBX_SCALE_UNITS", axis_forward="Z", axis_up="Y",
            path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE",
            use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False,
        )

        # Round trip: the FBX must give back the same mesh, size and texture.
        reset()
        bpy.ops.import_scene.fbx(filepath=fbx, axis_forward="Z", axis_up="Y")
        back = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        assert len(back) == 1, f"{colour}: expected 1 mesh, got {len(back)}"
        rt = mesh_report(back[0])
        rt_bbox = world_bbox(back[0])
        images = [i for i in bpy.data.images if i.size[0] > 0]
        err = max(abs(a - b) for a, b in zip(src_bbox[0] + src_bbox[1], rt_bbox[0] + rt_bbox[1]))
        report[colour] = dict(
            source=src, roundtrip_triangles=rt["triangles"],
            roundtrip_bbox_error_studs=err,
            embedded_texture=[f"{i.name} {i.size[0]}x{i.size[1]}" for i in images],
            fbx_bytes=os.path.getsize(fbx),
        )
        ok = (rt["triangles"] == src["triangles"] and err < 1e-4 and images
              and src["non_manifold_edges"] == 0 and src["degenerate_faces"] == 0
              and src["inward_shells"] == 0)
        print(f"[{'OK' if ok else 'FAIL'}] {os.path.basename(fbx)}  tris={src['triangles']} "
              f"bbox_err={err:.2e}  texture={report[colour]['embedded_texture']}")
        if not ok:
            print(json.dumps(report[colour], indent=2))
            sys.exit(1)

    with open(os.path.join(OUT, "build", "blender_report.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report["Fraise"]["source"], indent=2))


if __name__ == "__main__":
    main()
