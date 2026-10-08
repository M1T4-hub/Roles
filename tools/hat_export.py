"""Mesh export helpers: Wavefront OBJ/MTL (Roblox Studio 3D Importer) and a
compact JSON used by the HTML previewer."""

from __future__ import annotations

import json

import numpy as np


def vertex_normals(V, faces):
    """Area-weighted smooth normals per position."""
    N = np.zeros_like(V)
    for f in faces:
        for i in range(1, len(f) - 1):
            a, b, c = V[f[0]], V[f[i]], V[f[i + 1]]
            n = np.cross(b - a, c - a)
            for j in (f[0], f[i], f[i + 1]):
                N[j] += n
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    return N


def write_obj(path, mtl_name, material, shells_merged, object_name):
    V, F, UV, FT = shells_merged
    N = vertex_normals(V, F)
    lines = [
        "# Neko Bucket Hat - Roblox UGC rigid accessory (Hat)",
        "# Units: studs, +Y up, avatar faces -Z. Origin = HatAttachment.",
        f"# Triangles: {sum(len(f) - 2 for f in F)}",
        f"mtllib {mtl_name}",
        f"o {object_name}",
    ]
    lines += [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in V]
    lines += [f"vt {u:.6f} {v:.6f}" for u, v in UV]
    lines += [f"vn {x:.5f} {y:.5f} {z:.5f}" for x, y, z in N]
    lines.append(f"usemtl {material}")
    lines.append("s 1")
    for f, ft in zip(F, FT):
        lines.append("f " + " ".join(f"{a + 1}/{t + 1}/{a + 1}" for a, t in zip(f, ft)))
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def write_mtl(path, material, albedo_png):
    with open(path, "w", newline="\n") as fh:
        fh.write(
            f"newmtl {material}\n"
            "Ka 1.000 1.000 1.000\n"
            "Kd 1.000 1.000 1.000\n"
            "Ks 0.000 0.000 0.000\n"
            "Ns 10.0\n"
            "d 1.0\n"
            "illum 1\n"
            f"map_Kd {albedo_png}\n"
        )


def triangulated_buffers(shells_merged):
    """Unique (position, uv) corners -> indexed triangle buffers."""
    V, F, UV, FT = shells_merged
    N = vertex_normals(V, F)
    key_to_idx = {}
    pos, nrm, uv, idx = [], [], [], []
    for f, ft in zip(F, FT):
        corners = []
        for a, t in zip(f, ft):
            k = (a, t)
            if k not in key_to_idx:
                key_to_idx[k] = len(pos)
                pos.append(V[a])
                nrm.append(N[a])
                uv.append(UV[t])
            corners.append(key_to_idx[k])
        for i in range(1, len(corners) - 1):
            idx += [corners[0], corners[i], corners[i + 1]]
    return (np.asarray(pos), np.asarray(nrm), np.asarray(uv), np.asarray(idx))


def write_preview_json(path, shells_merged):
    pos, nrm, uv, idx = triangulated_buffers(shells_merged)
    data = {
        "position": np.round(pos, 5).ravel().tolist(),
        "normal": np.round(nrm, 4).ravel().tolist(),
        "uv": np.round(uv, 5).ravel().tolist(),
        "index": idx.tolist(),
    }
    with open(path, "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
