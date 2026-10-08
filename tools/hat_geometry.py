"""Procedural geometry for the "Neko Bucket Hat" Roblox UGC hat.

All units are Roblox studs. Axes follow Roblox: +Y is up, the avatar looks
toward -Z, and +X is the avatar's right. The origin is the HatAttachment
point (top centre of a standard R15 head, about 1.2 studs tall).

Every part is built as a closed "loft" (rings of points joined by quads and
closed by triangle fans), so each shell is watertight by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TAU = 2.0 * np.pi

# Part ids, used by the texture baker.
PART_CROWN = 0
PART_EAR_L = 1
PART_EAR_R = 2
PART_KNOT = 3
PART_LOOP_L = 4
PART_LOOP_R = 5
PART_TAIL_L = 6
PART_TAIL_R = 7
PART_PEARL = 8

# Avatar front is -Z: the revolve seam sits at the back (+Z).
SEAM_ANGLE = np.pi / 2.0
BOW_ANGLE = np.radians(-38.0)  # front-right side of the crown


@dataclass
class Shell:
    name: str
    part: int
    V: np.ndarray                     # (n, 3) positions
    faces: list                       # polygons (tuples of 3 or 4 vertex ids)
    UV: np.ndarray                    # (k, 2) island-local UVs in [0, 1]
    faces_uv: list                    # same layout as faces, ids into UV
    attr: np.ndarray                  # (k, 2) per-UV-vertex bake parameters
    island: tuple = (0.0, 0.0, 1.0, 1.0)   # atlas rect (u0, v0, u1, v1)
    meta: dict = field(default_factory=dict)

    def atlas_uv(self) -> np.ndarray:
        u0, v0, u1, v1 = self.island
        return np.column_stack(
            (u0 + self.UV[:, 0] * (u1 - u0), v0 + self.UV[:, 1] * (v1 - v0))
        )


# ---------------------------------------------------------------------------
# Generic closed loft
# ---------------------------------------------------------------------------

def loft(rings, apex0, apex1, v_rings, v_apex0, v_apex1, attr_v=None,
         end_cap=None, u_by_arclength=True):
    """Join K rings of M points into a closed surface.

    rings   : (K, M, 3) ring points, ring order consistent along the loft.
    apex0/1 : (3,) points closing the first / last ring with a fan, or None.
    end_cap : optional list of polygons (indices into the last ring) used
              instead of apex1 to close the last ring.
    Returns V, faces, UV, faces_uv, attr with UV/attr in island space.
    """
    rings = np.asarray(rings, dtype=float)
    K, M, _ = rings.shape
    V = [rings.reshape(-1, 3)]
    faces, faces_uv = [], []
    UV, attr = [], []
    attr_v = v_rings if attr_v is None else attr_v

    # UV grid: (K, M + 1) so the seam column is duplicated. With
    # u_by_arclength, u follows each ring's perimeter so flat sections
    # (ears, ribbon) get an even texel density instead of crowding the rims.
    ring_u = np.tile(np.arange(M + 1) / M, (K, 1))
    if u_by_arclength:
        seg = np.linalg.norm(np.roll(rings, -1, axis=1) - rings, axis=2)
        cum = np.concatenate([np.zeros((K, 1)), np.cumsum(seg, axis=1)], axis=1)
        ring_u = cum / cum[:, -1:]
    for k in range(K):
        for m in range(M + 1):
            UV.append((ring_u[k, m], v_rings[k]))
            attr.append((m / M, attr_v[k]))

    def vid(k, m):
        return k * M + (m % M)

    def tid(k, m):
        return k * (M + 1) + m

    for k in range(K - 1):
        for m in range(M):
            faces.append((vid(k, m), vid(k, m + 1), vid(k + 1, m + 1), vid(k + 1, m)))
            faces_uv.append((tid(k, m), tid(k, m + 1), tid(k + 1, m + 1), tid(k + 1, m)))

    n_v = K * M
    n_t = K * (M + 1)
    if apex0 is not None:
        V.append(np.asarray(apex0, float)[None])
        a = n_v
        n_v += 1
        for m in range(M):
            UV.append((0.5 * (ring_u[0, m] + ring_u[0, m + 1]), v_apex0))
            attr.append(((m + 0.5) / M, attr_v[0] - (v_rings[0] - v_apex0)))
            faces.append((a, vid(0, m + 1), vid(0, m)))
            faces_uv.append((n_t, tid(0, m + 1), tid(0, m)))
            n_t += 1
    if apex1 is not None:
        V.append(np.asarray(apex1, float)[None])
        a = n_v
        n_v += 1
        for m in range(M):
            UV.append((0.5 * (ring_u[-1, m] + ring_u[-1, m + 1]), v_apex1))
            attr.append(((m + 0.5) / M, attr_v[-1] + (v_apex1 - v_rings[-1])))
            faces.append((vid(K - 1, m), vid(K - 1, m + 1), a))
            faces_uv.append((tid(K - 1, m), tid(K - 1, m + 1), n_t))
            n_t += 1
    if end_cap is not None:
        for poly in end_cap:
            faces.append(tuple(vid(K - 1, m) for m in poly))
            faces_uv.append(tuple(tid(K - 1, m) for m in poly))

    return (np.concatenate(V), faces, np.asarray(UV), faces_uv, np.asarray(attr))


def make_shell(name, part, data, island, meta=None):
    V, faces, UV, faces_uv, attr = data
    s = Shell(name, part, V, faces, UV, faces_uv, attr, island, meta or {})
    orient_outward(s)
    return s


# ---------------------------------------------------------------------------
# Orientation helpers
# ---------------------------------------------------------------------------

def _tris(faces):
    out = []
    for f in faces:
        for i in range(1, len(f) - 1):
            out.append((f[0], f[i], f[i + 1]))
    return np.asarray(out)


def signed_volume(V, faces):
    T = _tris(faces)
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    return np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0


def orient_outward(shell: Shell):
    """Make winding consistent across the shell, then point it outward."""
    faces = [list(f) for f in shell.faces]
    faces_uv = [list(f) for f in shell.faces_uv]
    edge_faces = {}
    for fi, f in enumerate(faces):
        for i in range(len(f)):
            e = (f[i], f[(i + 1) % len(f)])
            edge_faces.setdefault(frozenset(e), []).append(fi)

    def directed(f):
        return {(f[i], f[(i + 1) % len(f)]) for i in range(len(f))}

    seen = [False] * len(faces)
    for start in range(len(faces)):
        if seen[start]:
            continue
        seen[start] = True
        stack = [start]
        while stack:
            fi = stack.pop()
            dirs = directed(faces[fi])
            for (a, b) in dirs:
                for fj in edge_faces[frozenset((a, b))]:
                    if fj == fi or seen[fj]:
                        continue
                    if (a, b) in directed(faces[fj]):
                        faces[fj].reverse()
                        faces_uv[fj].reverse()
                    seen[fj] = True
                    stack.append(fj)

    if signed_volume(shell.V, faces) < 0:
        faces = [f[::-1] for f in faces]
        faces_uv = [f[::-1] for f in faces_uv]
    shell.faces = [tuple(f) for f in faces]
    shell.faces_uv = [tuple(f) for f in faces_uv]


# ---------------------------------------------------------------------------
# Crown + brim: one revolved profile
# ---------------------------------------------------------------------------

def _fillet_polyline(points, radii, arc_steps=24):
    """Polyline through `points` with circular fillets of radius radii[i].

    Returns the dense points and, per point, the index of the key span
    (points[i] -> points[i + 1]) it belongs to.
    """
    P = np.asarray(points, float)
    out, span = [P[0]], [0]
    for i in range(1, len(P) - 1):
        r = radii[i]
        a, b, c = P[i - 1], P[i], P[i + 1]
        if r <= 0:
            out.append(b)
            span.append(i)
            continue
        d1 = (a - b) / np.linalg.norm(a - b)
        d2 = (c - b) / np.linalg.norm(c - b)
        half = np.arccos(np.clip(np.dot(d1, d2), -1, 1)) / 2.0
        t = r / np.tan(half)
        t = min(t, 0.48 * np.linalg.norm(a - b), 0.48 * np.linalg.norm(c - b))
        r_eff = t * np.tan(half)
        p1 = b + d1 * t
        bis = (d1 + d2) / np.linalg.norm(d1 + d2)
        centre = b + bis * (r_eff / np.sin(half))
        p2 = b + d2 * t
        a1 = np.arctan2(*(p1 - centre)[::-1])
        a2 = np.arctan2(*(p2 - centre)[::-1])
        da = (a2 - a1 + np.pi) % TAU - np.pi
        for s in np.linspace(0, 1, arc_steps):
            ang = a1 + da * s
            out.append(centre + r_eff * np.array([np.cos(ang), np.sin(ang)]))
            span.append(i - 1 if s < 0.5 else i)
    out.append(P[-1])
    span.append(len(P) - 2)
    return np.asarray(out), np.asarray(span)


def _dense_arclength(P):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


BRIM_TOP_A = np.array([0.704, -0.338])
BRIM_TOP_B = np.array([0.842, -0.418])
BRIM_THICK = 0.034


def _brim_under(p):
    """Offset a brim-top point downward by the brim thickness."""
    d = (BRIM_TOP_B - BRIM_TOP_A) / np.linalg.norm(BRIM_TOP_B - BRIM_TOP_A)
    n_down = np.array([d[1], -d[0]])          # (-0.50, -0.87)
    if n_down[1] > 0:
        n_down = -n_down
    return p + n_down * BRIM_THICK


def crown_profile():
    """Closed (r, y) profile from the outer top pole to the inner top pole.

    Returns the dense polyline and a region label per dense point.
    """
    under_out = _brim_under(BRIM_TOP_B)
    # where the brim underside meets the inner wall (r = 0.648)
    d = BRIM_TOP_B - BRIM_TOP_A
    under_in = _brim_under(BRIM_TOP_A)
    under_in = under_in + d / d[0] * (0.648 - under_in[0])
    keys = [
        # (r, y), fillet radius, region label of the span starting here
        ((0.000, 0.262), 0.000, "top"),
        ((0.330, 0.254), 0.300, "top"),
        ((0.585, 0.205), 0.100, "side"),
        ((0.668, -0.200), 0.008, "band"),
        ((0.688, -0.207), 0.008, "band"),
        ((0.698, -0.312), 0.008, "band"),
        ((0.686, -0.322), 0.010, "brim_top"),
        (tuple(BRIM_TOP_A), 0.022, "brim_top"),
        (tuple(BRIM_TOP_B), 0.012, "hem"),
        ((0.874, -0.432), 0.016, "hem"),
        ((0.868, -0.468), 0.016, "hem"),
        (tuple(under_out + np.array([-0.004, -0.004])), 0.010, "brim_under"),
        (tuple(under_in), 0.016, "inner"),
        ((0.556, 0.176), 0.080, "inner"),
        ((0.300, 0.220), 0.250, "inner"),
        ((0.000, 0.228), 0.000, "inner"),
    ]
    pts = [k[0] for k in keys]
    rad = [k[1] for k in keys]
    dense, span = _fillet_polyline(pts, rad, arc_steps=40)
    labels = np.array([keys[i][2] for i in span], dtype=object)
    return dense, labels, span


# Hand-tuned vertex budget per profile span: dense where the silhouette
# turns (shoulder, hat band, rolled hem), sparse on hidden inner faces.
SPAN_SAMPLES = [3, 3, 4, 1, 2, 1, 1, 3, 2, 2, 1, 3, 2, 2, 2]


def _sample_spans(dense, span, counts):
    s = _dense_arclength(dense)
    pts, ss = [], []
    for i, n in enumerate(counts):
        ids = np.where(span == i)[0]
        s0 = s[ids[0]]
        s1 = s[ids[-1] + 1] if ids[-1] + 1 < len(s) else s[ids[-1]]
        for k in range(n):
            target = s0 + (s1 - s0) * k / n
            pts.append([np.interp(target, s, dense[:, 0]), np.interp(target, s, dense[:, 1])])
            ss.append(target)
    pts.append(dense[-1])
    ss.append(s[-1])
    return np.asarray(pts), np.asarray(ss)


def build_crown(segments=36):
    dense, labels, span = crown_profile()
    prof, s_prof = _sample_spans(dense, span, SPAN_SAMPLES)
    prof[0, 0] = 0.0
    prof[-1, 0] = 0.0

    # True arclength parameter (for region lookup in the baker).
    s_dense = _dense_arclength(dense)
    s_total = s_dense[-1]
    t_prof = s_prof / s_total

    # Region marks in normalised arclength.
    marks = {}
    for lab in ["top", "side", "band", "brim_top", "hem", "brim_under", "inner"]:
        ids = np.where(labels == lab)[0]
        marks[lab] = (s_dense[ids.min()] / s_total, s_dense[ids.max()] / s_total)

    # UV v: arclength weighted by visibility so inner faces use less space.
    weight = {"top": 1.0, "side": 1.0, "band": 1.0, "brim_top": 1.0,
              "hem": 1.0, "brim_under": 0.85, "inner": 0.3}
    wd = np.array([weight[l] for l in labels])
    ws = np.concatenate([[0.0], np.cumsum(np.diff(s_dense) * 0.5 * (wd[1:] + wd[:-1]))])
    ws /= ws[-1]
    v_prof = np.interp(t_prof * s_total, s_dense, ws)
    # v runs top (1.0) to inner (0.0) so the texture reads upright.
    v_prof = 1.0 - v_prof

    theta = SEAM_ANGLE + TAU * np.arange(segments) / segments
    rings = []
    for (r, y) in prof[1:-1]:
        rings.append(np.column_stack((r * np.cos(theta), np.full(segments, y),
                                      r * np.sin(theta))))
    data = loft(
        rings,
        apex0=(0.0, prof[0, 1], 0.0),
        apex1=(0.0, prof[-1, 1], 0.0),
        v_rings=v_prof[1:-1],
        v_apex0=v_prof[0],
        v_apex1=v_prof[-1],
        attr_v=t_prof[1:-1],
        u_by_arclength=False,
    )
    # Fix the apex attr (normalised arclength) to the exact pole values.
    V, faces, UV, faces_uv, attr = data
    n_ring_uv = (len(prof) - 2) * (segments + 1)
    attr[n_ring_uv:n_ring_uv + segments, 1] = t_prof[0]
    attr[n_ring_uv + segments:, 1] = t_prof[-1]
    shell = make_shell("Crown", PART_CROWN, (V, faces, UV, faces_uv, attr),
                       island=(0.0, 0.30, 1.0, 1.0),
                       meta={"marks": marks, "profile": prof, "dense": dense,
                             "labels": labels})
    return shell


def brim_top_height(r):
    """y of the brim's upper surface at radius r (for placing the bow tails)."""
    t = (r - BRIM_TOP_A[0]) / (BRIM_TOP_B[0] - BRIM_TOP_A[0])
    return BRIM_TOP_A[1] + t * (BRIM_TOP_B[1] - BRIM_TOP_A[1])


# ---------------------------------------------------------------------------
# Cat ears
# ---------------------------------------------------------------------------

def _rot(axis, ang):
    axis = np.asarray(axis, float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    c, s = np.cos(ang), np.sin(ang)
    C = 1 - c
    return np.array([
        [c + x * x * C, x * y * C - z * s, x * z * C + y * s],
        [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
        [z * x * C - y * s, z * y * C + x * s, c + z * z * C],
    ])


def build_ear(side, island, part, M=14, K=10):
    """side = +1 (avatar right, +X) or -1 (avatar left)."""
    W, D, H = 0.350, 0.200, 0.385
    base = np.array([0.330 * side, 0.170, -0.030])
    # Orientation: roll outward, slight forward pitch, yaw outward.
    R = (_rot((0, 1, 0), np.radians(-12.0) * side)
         @ _rot((0, 0, 1), np.radians(-17.0) * side)
         @ _rot((1, 0, 0), np.radians(-7.0)))

    hs = np.concatenate([np.linspace(0.0, 0.80, K - 3), [0.87, 0.925, 0.965]])
    phi = TAU * np.arange(M) / M
    rings = []
    for h in hs:
        # softly convex sides and a rounded tip (kawaii, not pointy)
        w = W * (1.0 - h) ** 0.72 * (1.0 + 0.10 * np.sin(np.pi * h))
        d = D * (1.0 - h) ** 0.95
        cup = 0.30 * np.sin(np.pi * min(h / 0.9, 1.0)) ** 0.6
        x = 0.5 * w * np.cos(phi)
        sp = np.sin(phi)
        # back (+Z) is convex, front (-Z) is cupped inward
        z = np.where(sp >= 0, 0.5 * d * sp, cup * 0.5 * d * (-sp))
        bend = np.array([0.010 * side, 0.0, -0.030]) * h * h
        local = np.column_stack((x, np.full(M, h * H), z)) + bend
        rings.append(base + local @ R.T)
    tip = base + (np.array([0.0, H * 0.995, 0.004]) + np.array([0.010 * side, 0, -0.030])) @ R.T
    cap = base + np.array([0.0, -0.01, 0.012]) @ R.T

    v_r = 0.06 + 0.90 * hs / hs[-1]
    data = loft(rings, apex0=cap, apex1=tip, v_rings=v_r, v_apex0=0.0,
                v_apex1=1.0, attr_v=hs)
    V, faces, UV, faces_uv, attr = data
    n_ring_uv = K * (M + 1)
    attr[n_ring_uv:n_ring_uv + M, 1] = -0.05
    attr[n_ring_uv + M:, 1] = 1.0
    return make_shell(f"Ear{'R' if side > 0 else 'L'}", part, (V, faces, UV, faces_uv, attr),
                      island, meta={"base": base, "R": R, "W": W, "D": D, "H": H,
                                    "side": side})


# ---------------------------------------------------------------------------
# Coquette bow on the hat band
# ---------------------------------------------------------------------------

BAND_R = 0.693
BOW_Y = -0.262


def _band_frame(theta, out=0.0, y=BOW_Y):
    """Point on a cylinder around the band plus its radial/tangent axes."""
    radial = np.array([np.cos(theta), 0.0, np.sin(theta)])
    tangent = np.array([-np.sin(theta), 0.0, np.cos(theta)])
    p = radial * (BAND_R + out) + np.array([0.0, y, 0.0])
    return p, radial, tangent


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def build_knot(island):
    c, radial, tangent = _band_frame(BOW_ANGLE, out=0.046)
    up = np.array([0.0, 1.0, 0.0])
    M, K = 12, 7
    a_t, a_y, a_r = 0.044, 0.062, 0.034
    us = np.linspace(-1, 1, K + 2)[1:-1]
    phi = TAU * np.arange(M) / M
    rings = []
    for u in us:
        s = np.sqrt(1 - u * u)
        # slightly squarer than an ellipsoid: a wrapped ribbon knot
        prof = np.sign(np.cos(phi)) * np.abs(np.cos(phi)) ** 0.8
        prof2 = np.sign(np.sin(phi)) * np.abs(np.sin(phi)) ** 0.8
        pinch = 1.0 - 0.10 * (1 - u * u)
        pts = (c[None]
               + np.outer(np.full(M, u * a_y), up)
               + np.outer(s * pinch * a_t * prof, tangent)
               + np.outer(s * a_r * prof2, radial))
        rings.append(pts)
    v_r = (us + 1) / 2
    data = loft(rings, apex0=c - up * a_y, apex1=c + up * a_y,
                v_rings=0.04 + 0.92 * v_r, v_apex0=0.0, v_apex1=1.0, attr_v=v_r)
    V, faces, UV, faces_uv, attr = data
    n_ring_uv = K * (M + 1)
    attr[n_ring_uv:n_ring_uv + M, 1] = 0.0
    attr[n_ring_uv + M:, 1] = 1.0
    return make_shell("BowKnot", PART_KNOT, data, island)


def build_loop(side, island, part, M=12, K=11):
    """One puffy bow wing. side=+1 goes toward +tangent (avatar front)."""
    L = 0.215
    up = np.array([0.0, 1.0, 0.0])
    us = np.linspace(0.0, 1.0, K + 2)[1:-1]
    phi = TAU * np.arange(M) / M
    rings = []
    rise = 0.055
    for u in us:
        # centre line hugs the band cylinder and rises (a smiling bow)
        theta = BOW_ANGLE + side * u * L / BAND_R
        out = 0.040 + 0.014 * np.sin(np.pi * u) - 0.016 * u
        c, radial, tangent = _band_frame(theta, out=out, y=BOW_Y + rise * u ** 1.2)
        # wing silhouette: pinched at the knot, widening, round tip
        grow = 0.20 + 0.80 * _smoothstep(0.0, 0.88, u) ** 0.85
        uc = 0.70
        close = 1.0 if u <= uc else (1.0 - ((u - uc) / (1 - uc)) ** 3.2) ** (1 / 3.2)
        a_y = 0.104 * grow * close
        a_r = 0.027 * (0.50 + 0.50 * np.sin(np.pi * min(u / 0.9, 1.0)) ** 0.6) * close ** 0.5
        # section tilt: wing leans outward/upward
        tilt = np.radians(24.0) * u
        ydir = np.cos(tilt) * up - side * np.sin(tilt) * tangent
        cphi, sphi = np.cos(phi), np.sin(phi)
        # soft crease along the outer face of the wing (folded ribbon)
        dent = np.where(sphi > 0, 1.0 - 0.32 * np.exp(-(cphi / 0.35) ** 2), 1.0)
        pts = (c[None]
               + np.outer(a_y * cphi, ydir)
               + np.outer(a_r * sphi * dent, radial))
        rings.append(pts)
    start = _band_frame(BOW_ANGLE, out=0.040)[0]
    end_theta = BOW_ANGLE + side * L / BAND_R
    end = _band_frame(end_theta, out=0.024, y=BOW_Y + rise)[0]
    data = loft(np.asarray(rings), apex0=start, apex1=end, v_rings=0.04 + 0.92 * us,
                v_apex0=0.0, v_apex1=1.0, attr_v=us)
    V, faces, UV, faces_uv, attr = data
    n_ring_uv = K * (M + 1)
    attr[n_ring_uv:n_ring_uv + M, 1] = 0.0
    attr[n_ring_uv + M:, 1] = 1.0
    return make_shell(f"BowLoop{'R' if side > 0 else 'L'}", part,
                      (V, faces, UV, faces_uv, attr), island)


def _tail_centre(side, u):
    """Centre line of a tail: hangs from the knot, then lies on the brim."""
    theta = BOW_ANGLE + side * (0.012 + 0.125 * u)
    radial = np.array([np.cos(theta), 0.0, np.sin(theta)])
    r0, r1 = BAND_R + 0.034, 0.838
    r = r0 + (r1 - r0) * u
    y_hang = (BOW_Y - 0.030) - 1.9 * (r - r0)
    y_lie = brim_top_height(max(r, BRIM_TOP_A[0])) + 0.5 * 0.0135 - 0.0015
    # smooth max so the ribbon drapes onto the brim instead of kinking
    k = 0.012
    y = 0.5 * (y_hang + y_lie + np.sqrt((y_hang - y_lie) ** 2 + k * k))
    return radial * r + np.array([0.0, y, 0.0]), theta


def build_tail(side, island, part, K=9):
    """Ribbon tail draped on the brim, ending in a swallowtail notch."""
    width, thick = 0.070, 0.0135
    us = np.linspace(0.0, 1.0, K)
    rings = []
    eps = 1e-3
    for u in us:
        p, theta = _tail_centre(side, u)
        p2, _ = _tail_centre(side, min(u + eps, 1.0))
        p1, _ = _tail_centre(side, max(u - eps, 0.0))
        T = (p2 - p1) / np.linalg.norm(p2 - p1)
        tangent = np.array([-np.sin(theta), 0.0, np.cos(theta)])
        wdir = tangent - np.dot(tangent, T) * T
        wdir /= np.linalg.norm(wdir)
        ndir = np.cross(wdir, T)
        if ndir[1] < 0 and np.dot(ndir, p * np.array([1, 0, 1])) < 0:
            ndir = -ndir
        hw = 0.5 * width * (0.80 + 0.20 * u)
        ht = 0.5 * thick
        ring = np.array([
            p - wdir * hw + ndir * ht,
            p + ndir * ht * 1.2,
            p + wdir * hw + ndir * ht,
            p + wdir * hw - ndir * ht,
            p - ndir * ht * 1.2,
            p - wdir * hw - ndir * ht,
        ])
        if u == 1.0:
            # swallowtail notch: pull the middle points back along the ribbon
            ring[1] -= T * 0.032
            ring[4] -= T * 0.032
        rings.append(ring)
    start = _band_frame(BOW_ANGLE + side * 0.004, out=0.040, y=BOW_Y - 0.006)[0]
    # end cap: two quads forming the V notch (ring order L, mid, R on each face)
    end_cap = [(0, 1, 4, 5), (1, 2, 3, 4)]
    data = loft(np.asarray(rings), apex0=start, apex1=None,
                v_rings=0.05 + 0.9 * us, v_apex0=0.0, v_apex1=1.0, attr_v=us,
                end_cap=end_cap)
    V, faces, UV, faces_uv, attr = data
    n_ring_uv = K * 7
    attr[n_ring_uv:n_ring_uv + 6, 1] = 0.0
    return make_shell(f"BowTail{'R' if side > 0 else 'L'}", part,
                      (V, faces, UV, faces_uv, attr), island)


def build_pearl(island, M=12, K=5):
    """Small pearl set in the middle of the knot."""
    c, radial, tangent = _band_frame(BOW_ANGLE, out=0.046 + 0.030)
    up = np.array([0.0, 1.0, 0.0])
    rad = 0.021
    us = np.linspace(-1, 1, K + 2)[1:-1]
    phi = TAU * np.arange(M) / M
    rings = []
    for u in us:
        s = np.sqrt(1 - u * u)
        rings.append(c[None] + np.outer(np.full(M, u * rad), up)
                     + np.outer(s * rad * np.cos(phi), tangent)
                     + np.outer(s * rad * np.sin(phi), radial))
    v_r = (us + 1) / 2
    data = loft(rings, apex0=c - up * rad, apex1=c + up * rad,
                v_rings=0.05 + 0.9 * v_r, v_apex0=0.0, v_apex1=1.0, attr_v=v_r)
    return make_shell("BowPearl", PART_PEARL, data, island)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_hat():
    shells = [build_crown()]
    # Lower atlas band (v in [0, 0.29]) holds the small parts.
    shells.append(build_ear(-1, island=(0.005, 0.005, 0.215, 0.29), part=PART_EAR_L))
    shells.append(build_ear(+1, island=(0.225, 0.005, 0.445, 0.29), part=PART_EAR_R))
    shells.append(build_loop(-1, island=(0.505, 0.150, 0.745, 0.29), part=PART_LOOP_L))
    shells.append(build_loop(+1, island=(0.755, 0.150, 0.995, 0.29), part=PART_LOOP_R))
    shells.append(build_knot(island=(0.505, 0.005, 0.625, 0.140)))
    shells.append(build_tail(-1, island=(0.635, 0.005, 0.815, 0.140), part=PART_TAIL_L))
    shells.append(build_tail(+1, island=(0.825, 0.005, 0.995, 0.140), part=PART_TAIL_R))
    shells.append(build_pearl(island=(0.455, 0.215, 0.495, 0.290)))
    return shells


def merged(shells):
    """Concatenate shells into one mesh (positions, polygons, atlas UVs)."""
    V, F, UV, FT = [], [], [], []
    ov = ot = 0
    for s in shells:
        V.append(s.V)
        UV.append(s.atlas_uv())
        F += [tuple(i + ov for i in f) for f in s.faces]
        FT += [tuple(i + ot for i in f) for f in s.faces_uv]
        ov += len(s.V)
        ot += len(s.UV)
    return np.concatenate(V), F, np.concatenate(UV), FT


def triangle_count(faces):
    return sum(len(f) - 2 for f in faces)
