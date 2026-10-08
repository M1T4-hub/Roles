"""Texture baking for the Neko Bucket Hat - clean "simple plastic" style.

Every texel of the UV atlas is mapped back to its 3D surface point
(G-buffer rasterised in UV space). Colour zones (body, inner ears, ribbon,
paw print, lining) are drawn from those 3D points, so edges stay crisp and
seam-free, and a soft ambient occlusion computed against a voxelised copy of
the hat is baked in so the shape reads well under any Roblox lighting.

No fur, no noise, no normal map: flat, glossy-looking plastic colours.
Output per colourway: one 1024 px albedo (MeshPart.TextureID).
"""

from __future__ import annotations

import numpy as np
from PIL import Image

import hat_geometry as G
from hat_export import vertex_normals

# ---------------------------------------------------------------------------
# Colourways (sRGB 0-255)
# ---------------------------------------------------------------------------

COLORWAYS = {
    # Strawberry milk: pink body, cream bow
    "Fraise": dict(
        body=(255, 176, 202), shade=(214, 98, 140), ear_inner=(255, 112, 160),
        ribbon=(255, 250, 244), ribbon_shade=(226, 186, 200),
        lining=(255, 214, 226), paw=(255, 250, 244), pearl=(255, 255, 255)),
    # Matcha latte: sage body, cream bow, pink inner ears
    "Matcha": dict(
        body=(176, 214, 150), shade=(96, 146, 86), ear_inner=(255, 176, 196),
        ribbon=(255, 250, 236), ribbon_shade=(206, 204, 170),
        lining=(226, 240, 208), paw=(255, 250, 236), pearl=(255, 255, 255)),
    # Midnight: charcoal body, lilac bow (soft emo / y2k)
    "Minuit": dict(
        body=(58, 54, 74), shade=(22, 20, 34), ear_inner=(198, 170, 255),
        ribbon=(198, 170, 255), ribbon_shade=(118, 92, 184),
        lining=(92, 86, 116), paw=(198, 170, 255), pearl=(250, 246, 255)),
    # Cloud: white body, baby-blue bow
    "Nuage": dict(
        body=(250, 250, 252), shade=(170, 182, 204), ear_inner=(255, 170, 196),
        ribbon=(150, 200, 255), ribbon_shade=(86, 138, 214),
        lining=(214, 232, 255), paw=(150, 200, 255), pearl=(255, 255, 255)),
    # Cocoa: brown body, cream bow
    "Choco": dict(
        body=(150, 98, 70), shade=(84, 48, 32), ear_inner=(250, 190, 182),
        ribbon=(255, 242, 224), ribbon_shade=(214, 180, 150),
        lining=(196, 146, 114), paw=(255, 242, 224), pearl=(255, 252, 244)),
}


def srgb_to_lin(c):
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# UV-space G-buffer
# ---------------------------------------------------------------------------

def rasterize(shells, size):
    H = W = size
    pos = np.zeros((H, W, 3))
    nrm = np.zeros((H, W, 3))
    part = np.full((H, W), -1, np.int16)
    a0 = np.zeros((H, W))
    a1 = np.zeros((H, W))
    for s in shells:
        N = vertex_normals(s.V, s.faces)
        UV = s.atlas_uv()
        px = UV[:, 0] * W - 0.5
        py = (1.0 - UV[:, 1]) * H - 0.5
        for f, ft in zip(s.faces, s.faces_uv):
            for i in range(1, len(f) - 1):
                tri = (f[0], f[i], f[i + 1])
                tt = (ft[0], ft[i], ft[i + 1])
                x = px[list(tt)]
                y = py[list(tt)]
                x0, x1 = int(np.floor(x.min())), int(np.ceil(x.max()))
                y0, y1 = int(np.floor(y.min())), int(np.ceil(y.max()))
                x0, y0 = max(x0, 0), max(y0, 0)
                x1, y1 = min(x1, W - 1), min(y1, H - 1)
                if x1 < x0 or y1 < y0:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
                den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
                if abs(den) < 1e-12:
                    continue
                w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / den
                w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / den
                w2 = 1 - w0 - w1
                inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
                if not inside.any():
                    continue
                gx, gy = gx[inside], gy[inside]
                w = np.stack([w0[inside], w1[inside], w2[inside]], -1)
                pos[gy, gx] = w @ s.V[list(tri)]
                n = w @ N[list(tri)]
                nrm[gy, gx] = n / np.linalg.norm(n, axis=1, keepdims=True)
                part[gy, gx] = s.part
                a0[gy, gx] = w @ s.attr[list(tt), 0]
                a1[gy, gx] = w @ s.attr[list(tt), 1]
    return dict(pos=pos, nrm=nrm, part=part, a0=a0, a1=a1, mask=part >= 0)


def dilate(img, mask, passes=12):
    """Bleed island colours outward so mip-maps never show seams."""
    img = img.astype(float).copy()
    mask = mask.copy()
    for _ in range(passes):
        acc = np.zeros_like(img)
        cnt = np.zeros(mask.shape)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            m = np.roll(np.roll(mask, dy, 0), dx, 1)
            v = np.roll(np.roll(img, dy, 0), dx, 1)
            acc += v * m[..., None] if img.ndim == 3 else v * m
            cnt += m
        grow = (~mask) & (cnt > 0)
        if img.ndim == 3:
            img[grow] = acc[grow] / cnt[grow][:, None]
        else:
            img[grow] = acc[grow] / cnt[grow]
        mask = mask | grow
    # fill whatever is left with the mean colour
    if (~mask).any():
        img[~mask] = img[mask].mean(axis=0)
    return img


# ---------------------------------------------------------------------------
# Voxel occupancy + ambient occlusion
# ---------------------------------------------------------------------------

def voxelize(shells, h=0.008, pad=0.05):
    allV = np.concatenate([s.V for s in shells])
    lo = allV.min(0) - pad
    hi = allV.max(0) + pad
    n = np.ceil((hi - lo) / h).astype(int)
    occ = np.zeros((n[0], n[2], n[1]), np.int16)   # x, z, y
    xs = lo[0] + (np.arange(n[0]) + 0.5) * h + 1.3e-5
    zs = lo[2] + (np.arange(n[2]) + 0.5) * h + 2.1e-5
    for s in shells:
        T = G._tris(s.faces)
        A, B, C = s.V[T[:, 0]], s.V[T[:, 1]], s.V[T[:, 2]]
        cols, ys = [], []
        for a, b, c in zip(A, B, C):
            xmin, xmax = min(a[0], b[0], c[0]), max(a[0], b[0], c[0])
            zmin, zmax = min(a[2], b[2], c[2]), max(a[2], b[2], c[2])
            i0, i1 = np.searchsorted(xs, xmin), np.searchsorted(xs, xmax)
            k0, k1 = np.searchsorted(zs, zmin), np.searchsorted(zs, zmax)
            if i1 <= i0 or k1 <= k0:
                continue
            gx, gz = np.meshgrid(xs[i0:i1], zs[k0:k1], indexing="ij")
            den = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
            if abs(den) < 1e-14:
                continue
            w0 = ((b[2] - c[2]) * (gx - c[0]) + (c[0] - b[0]) * (gz - c[2])) / den
            w1 = ((c[2] - a[2]) * (gx - c[0]) + (a[0] - c[0]) * (gz - c[2])) / den
            w2 = 1 - w0 - w1
            ins = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not ins.any():
                continue
            y = w0 * a[1] + w1 * b[1] + w2 * c[1]
            ii, kk = np.meshgrid(np.arange(i0, i1), np.arange(k0, k1), indexing="ij")
            cols.append((ii[ins] * n[2] + kk[ins]))
            ys.append(y[ins])
        if not cols:
            continue
        cols = np.concatenate(cols)
        ys = np.concatenate(ys)
        order = np.lexsort((ys, cols))
        cols, ys = cols[order], ys[order]
        # rank of each hit within its column
        start = np.r_[0, np.flatnonzero(np.diff(cols)) + 1]
        rank = np.arange(len(cols)) - np.repeat(start, np.diff(np.r_[start, len(cols)]))
        enter = rank % 2 == 0
        # columns with an odd hit count (grazing rays) are skipped
        counts = np.diff(np.r_[start, len(cols)])
        good = np.repeat(counts % 2 == 0, counts)
        e_idx = np.flatnonzero(enter & good)
        delta = np.zeros((n[0] * n[2], n[1] + 1), np.int16)
        iy0 = np.clip(np.round((ys[e_idx] - lo[1]) / h).astype(int), 0, n[1])
        iy1 = np.clip(np.round((ys[e_idx + 1] - lo[1]) / h).astype(int), 0, n[1])
        np.add.at(delta, (cols[e_idx], iy0), 1)
        np.add.at(delta, (cols[e_idx], iy1), -1)
        occ += (np.cumsum(delta, axis=1)[:, :n[1]] > 0).reshape(n[0], n[2], n[1])
    return dict(occ=occ > 0, lo=lo, h=h, n=n)


def _occupied(vox, Q):
    idx = np.floor((Q - vox["lo"]) / vox["h"]).astype(int)
    n = vox["n"]
    ok = ((idx >= 0) & (idx < n)).all(axis=1)
    out = np.zeros(len(Q), bool)
    i = idx[ok]
    out[ok] = vox["occ"][i[:, 0], i[:, 2], i[:, 1]]
    return out


def ambient_occlusion(P, N, vox, samples=40, max_dist=0.17, seed=3):
    rng = np.random.default_rng(seed)
    # stratified cosine-weighted hemisphere in a local frame
    k = np.arange(samples)
    u1 = (k + rng.random(samples)) / samples
    u2 = rng.random(samples)
    r = np.sqrt(u1)
    phi = 2 * np.pi * u2
    local = np.stack([r * np.cos(phi), r * np.sin(phi), np.sqrt(1 - u1)], -1)
    dist = 0.012 + max_dist * (rng.permutation(samples) + 0.5) / samples
    dist = dist ** 1.0
    ao = np.zeros(len(P))
    up = np.where(np.abs(N[:, 1:2]) < 0.9, [[0.0, 1.0, 0.0]], [[1.0, 0.0, 0.0]])
    T = np.cross(up, N)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    B = np.cross(N, T)
    base = P + N * 0.013
    wsum = 0.0
    for j in range(samples):
        d = T * local[j, 0] + B * local[j, 1] + N * local[j, 2]
        w = 1.0 - 0.6 * (dist[j] / (max_dist + 0.012))   # near hits matter more
        ao += w * _occupied(vox, base + d * dist[j])
        wsum += w
    return 1.0 - ao / wsum


# ---------------------------------------------------------------------------
# Colour zones
# ---------------------------------------------------------------------------

def _paw_dist(s, y):
    """Paw print (main pad + 4 toe beans); < 1 inside. Local coords in studs."""
    def ell(cx, cy, rx, ry, rot=0.0):
        cs, sn = np.cos(rot), np.sin(rot)
        dx, dy = s - cx, y - cy
        x2 = (dx * cs + dy * sn) / rx
        y2 = (-dx * sn + dy * cs) / ry
        return np.sqrt(x2 * x2 + y2 * y2)
    k = 1.2   # overall scale
    pad = np.minimum(ell(0.0, -0.018 * k, 0.040 * k, 0.030 * k),
                     ell(0.0, -0.032 * k, 0.032 * k, 0.024 * k))
    toes = np.minimum.reduce([
        ell(-0.044 * k, 0.018 * k, 0.0135 * k, 0.017 * k, 0.35),
        ell(-0.016 * k, 0.040 * k, 0.0135 * k, 0.018 * k, 0.10),
        ell(0.016 * k, 0.040 * k, 0.0135 * k, 0.018 * k, -0.10),
        ell(0.044 * k, 0.018 * k, 0.0135 * k, 0.017 * k, -0.35),
    ])
    return np.minimum(pad, toes)


def _aa(d, px):
    """Anti-aliased inside mask from a distance-like field (inside < 0)."""
    return np.clip(0.5 - d / px, 0.0, 1.0)


def bake(shells, colorways, size=1024, log=print):
    log("  rasterising UV G-buffer ...")
    gb = rasterize(shells, size)
    m = gb["mask"]
    P = gb["pos"][m]
    N = gb["nrm"][m]
    part = gb["part"][m]
    a0 = gb["a0"][m]
    a1 = gb["a1"][m]
    n = len(P)

    log("  voxelising + ambient occlusion ...")
    vox = voxelize(shells)
    ao = np.empty(n)
    for i in range(0, n, 120000):
        ao[i:i + 120000] = ambient_occlusion(P[i:i + 120000], N[i:i + 120000], vox)

    log("  painting colour zones ...")
    marks = shells[0].meta["marks"]
    crown = part == G.PART_CROWN
    t = a1
    r_xz = np.hypot(P[:, 0], P[:, 2])
    theta = np.arctan2(P[:, 2], P[:, 0])

    def region(name):
        lo, hi = marks[name]
        return crown & (t >= lo) & (t <= hi)

    band = region("band")
    lining = region("brim_under") | region("inner")
    ears = (part == G.PART_EAR_L) | (part == G.PART_EAR_R)
    ribbon = band | np.isin(part, [G.PART_KNOT, G.PART_LOOP_L, G.PART_LOOP_R,
                                   G.PART_TAIL_L, G.PART_TAIL_R])
    pearl = part == G.PART_PEARL
    body = (crown & ~band & ~lining) | ears

    # Inner ear: rounded-triangle patch on the cupped front face.
    phi = a0 * 2 * np.pi
    h = a1
    lateral = np.abs(np.cos(phi))
    front = np.sin(phi) < 0
    half_w = 0.80 * (1.0 - 0.45 * h)            # narrows toward the tip
    d_side = (lateral - half_w) / 0.80
    d_bot = (0.12 - h) / 0.5
    d_top = (h - 0.84) / 0.5
    d_ear = np.maximum.reduce([d_side, d_bot, d_top])
    ear_in = ears * front * _aa(d_ear, 0.02)

    # Paw print on the crown front (avatar looks toward -Z).
    d_ang = np.angle(np.exp(1j * (theta + np.pi / 2)))
    s_loc = d_ang * r_xz
    y_loc = P[:, 1] + 0.010
    on_side = crown & (t > marks["side"][0] + 0.01) & (t < marks["band"][0] - 0.004)
    paw = on_side * _aa(_paw_dist(s_loc, y_loc) - 1.0, 0.06)

    # Soft gloss: a light top-down gradient gives the "toy plastic" look.
    light = 0.86 + 0.14 * np.clip(N[:, 1] * 0.5 + 0.5, 0, 1)
    occl = np.clip(ao, 0, 1) ** 1.3

    albedos = {}
    for name, cw in colorways.items():
        C = {k: srgb_to_lin(v) for k, v in cw.items()}
        col = np.zeros((n, 3))
        shade_tint = np.zeros((n, 3))
        col[body] = C["body"]
        shade_tint[body] = C["shade"]
        col = mix(col, C["ear_inner"][None], ear_in)
        col = mix(col, C["paw"][None], paw)
        col[lining] = C["lining"]
        shade_tint[lining] = C["shade"]
        col[ribbon] = C["ribbon"]
        shade_tint[ribbon] = C["ribbon_shade"]
        col[pearl] = C["pearl"]
        shade_tint[pearl] = C["ribbon_shade"]
        # coloured (not grey) occlusion keeps the plastic clean and saturated
        col = mix(shade_tint * 0.85, col, 0.25 + 0.75 * occl) * light[:, None]
        img = np.zeros((size, size, 3))
        img[m] = lin_to_srgb(col)
        img = dilate(img, m, passes=16)
        albedos[name] = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
    return albedos, gb
