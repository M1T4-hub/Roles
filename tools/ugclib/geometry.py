"""Generic procedural-geometry toolkit for Roblox rigid accessories.

Units are studs, axes are Roblox's: +Y up, the avatar looks toward -Z and +X
is the avatar's right. An item's origin is its attachment point (e.g. the
HatAttachment at the top of a 1.2-stud R15 head).

Everything is built from closed "lofts" (rings of points joined by quads and
closed by fans or loops), so every shell is watertight by construction.
make_shell() then fixes the winding so each shell's normals point outward.

Helpers: revolve, ellipsoid, sweep (tubes along a path, open or closed),
slab (a thick, rounded 2D outline such as a wing or lens).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TAU = 2.0 * np.pi


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
         end_cap=None, u_by_arclength=True, closed_loop=False):
    """Join K rings of M points into a closed surface.

    rings   : (K, M, 3) ring points, ring order consistent along the loft.
    apex0/1 : (3,) points closing the first / last ring with a fan, or None.
    end_cap : optional list of polygons (indices into the last ring) used
              instead of apex1 to close the last ring.
    closed_loop : join the last ring back to the first (torus-like tube);
              apex0/apex1 must then be None. An extra UV row is added so the
              texture wraps without a seam artefact.
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
    if closed_loop:
        assert apex0 is None and apex1 is None and end_cap is None
        for m in range(M + 1):                      # duplicated first ring, v = 1
            UV.append((ring_u[0, m], 1.0))
            attr.append((m / M, 1.0))

    def vid(k, m):
        return k * M + (m % M)

    def tid(k, m):
        return k * (M + 1) + m

    for k in range(K - 1 + int(closed_loop)):
        k1 = (k + 1) % K
        for m in range(M):
            faces.append((vid(k, m), vid(k, m + 1), vid(k1, m + 1), vid(k1, m)))
            faces_uv.append((tid(k, m), tid(k, m + 1), tid(k + 1, m + 1), tid(k + 1, m)))

    n_v = K * M
    n_t = (K + int(closed_loop)) * (M + 1)
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

def tris(faces):
    out = []
    for f in faces:
        for i in range(1, len(f) - 1):
            out.append((f[0], f[i], f[i + 1]))
    return np.asarray(out)


def signed_volume(V, faces):
    T = tris(faces)
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
# Polyline helpers
# ---------------------------------------------------------------------------

def fillet_polyline(points, radii, arc_steps=24):
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


def dense_arclength(P):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


def rot(axis, ang):
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


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)




# ---------------------------------------------------------------------------
# Higher-level primitives (all return a ready, outward-facing Shell)
# ---------------------------------------------------------------------------

def _apex_attr_fix(data, K, M, a0_value, a1_value, has_apex0=True, has_apex1=True):
    V, faces, UV, faces_uv, attr = data
    n = K * (M + 1)
    if has_apex0:
        attr[n:n + M, 1] = a0_value
        n += M
    if has_apex1:
        attr[n:n + M, 1] = a1_value
    return V, faces, UV, faces_uv, attr


def revolve(name, part, profile, island, segments=32, seam_angle=np.pi / 2,
            centre=(0.0, 0.0, 0.0), v_values=None, meta=None):
    """Surface of revolution around the vertical axis through `centre`.

    profile : (N, 2) array of (radius, y) points. The first and last points
              must have radius 0 (they become the poles), so the result is a
              closed shell. Order: start at one pole, end at the other.
    attr    : a0 = angle/2pi, a1 = normalised profile arclength (0..1).
    """
    prof = np.asarray(profile, float)
    assert abs(prof[0, 0]) < 1e-9 and abs(prof[-1, 0]) < 1e-9, "profile must start/end on the axis"
    c = np.asarray(centre, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(prof, axis=0), axis=1))])
    t = s / s[-1]
    v = t if v_values is None else np.asarray(v_values, float)
    theta = seam_angle + TAU * np.arange(segments) / segments
    rings = [c + np.column_stack((r * np.cos(theta), np.full(segments, y), r * np.sin(theta)))
             for r, y in prof[1:-1]]
    data = loft(rings, apex0=c + (0, prof[0, 1], 0), apex1=c + (0, prof[-1, 1], 0),
                v_rings=1.0 - v[1:-1], v_apex0=1.0 - v[0], v_apex1=1.0 - v[-1],
                attr_v=t[1:-1], u_by_arclength=False)
    data = _apex_attr_fix(data, len(prof) - 2, segments, t[0], t[-1])
    return make_shell(name, part, data, island, meta)


def ellipsoid(name, part, centre, radii, island, axes=None, M=16, K=9,
              exponent=1.0, meta=None):
    """(Super)ellipsoid. axes: 3x3 rows = local X, Y (pole axis), Z directions.

    exponent < 1 gives a boxier, rounded-cube look (e.g. 0.6), 1 = ellipsoid.
    attr: a0 = longitude/2pi, a1 = latitude 0 (bottom pole) .. 1 (top pole).
    """
    c = np.asarray(centre, float)
    ax = np.eye(3) if axes is None else np.asarray(axes, float)
    rx, ry, rz = radii
    lat = np.linspace(-np.pi / 2, np.pi / 2, K + 2)[1:-1]
    lon = TAU * np.arange(M) / M

    def spow(x, e):
        return np.sign(x) * np.abs(x) ** e

    rings = []
    for la in lat:
        cy, sy = spow(np.cos(la), exponent), spow(np.sin(la), exponent)
        x = rx * cy * spow(np.cos(lon), exponent)
        z = rz * cy * spow(np.sin(lon), exponent)
        y = np.full(M, ry * sy)
        rings.append(c + np.outer(x, ax[0]) + np.outer(y, ax[1]) + np.outer(z, ax[2]))
    v = (lat + np.pi / 2) / np.pi
    data = loft(rings, apex0=c - ax[1] * ry, apex1=c + ax[1] * ry, v_rings=v,
                v_apex0=0.0, v_apex1=1.0, attr_v=v)
    data = _apex_attr_fix(data, K, M, 0.0, 1.0)
    return make_shell(name, part, data, island, meta)


def parallel_transport_frames(path, up_hint=(0.0, 1.0, 0.0), closed=False):
    """Rotation-minimising (T, N, B) frames along a polyline (K, 3)."""
    P = np.asarray(path, float)
    K = len(P)
    if closed:
        T = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
    else:
        T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    up = np.asarray(up_hint, float)
    n0 = up - np.dot(up, T[0]) * T[0]
    if np.linalg.norm(n0) < 1e-6:
        n0 = np.cross(T[0], [1.0, 0.0, 0.0])
    n0 /= np.linalg.norm(n0)
    N = np.zeros_like(P)
    N[0] = n0
    for k in range(1, K):
        n = N[k - 1] - np.dot(N[k - 1], T[k]) * T[k]
        N[k] = n / np.linalg.norm(n)
    B = np.cross(T, N)
    return T, N, B


def sweep(name, part, path, section, island, closed=False, cap_start=True,
          cap_end=True, up_hint=(0.0, 1.0, 0.0), frames=None, meta=None):
    """Tube along `path` (K, 3).

    section(k, u) -> (M, 2) points in the (N, B) plane of frame k, where
    u = k/(K-1) along the path (or k/K when closed). Keep M constant and the
    ring winding consistent. For open sweeps the ends are closed with fans
    (cap_*), so make the end sections small for a rounded/tapered tip.
    closed=True joins the last ring back to the first (rings, frames).
    attr: a0 = section angle fraction, a1 = u along the path.
    """
    P = np.asarray(path, float)
    K = len(P)
    T, N, B = frames if frames is not None else parallel_transport_frames(P, up_hint, closed)
    us = np.arange(K) / (K if closed else K - 1)
    rings = []
    for k in range(K):
        sec = np.asarray(section(k, us[k]), float)
        rings.append(P[k] + np.outer(sec[:, 0], N[k]) + np.outer(sec[:, 1], B[k]))
    rings = np.asarray(rings)
    if closed:
        data = loft(rings, None, None, v_rings=us, v_apex0=0, v_apex1=1, attr_v=us,
                    closed_loop=True)
        return make_shell(name, part, data, island, meta)
    apex0 = rings[0].mean(axis=0) - T[0] * 1e-4 if cap_start else None
    apex1 = rings[-1].mean(axis=0) + T[-1] * 1e-4 if cap_end else None
    v = 0.04 + 0.92 * us
    data = loft(rings, apex0, apex1, v_rings=v, v_apex0=0.0, v_apex1=1.0, attr_v=us)
    data = _apex_attr_fix(data, K, rings.shape[1], 0.0, 1.0, apex0 is not None,
                          apex1 is not None)
    return make_shell(name, part, data, island, meta)


def slab(name, part, outline, thickness, island, origin=(0, 0, 0),
         x_axis=(1, 0, 0), y_axis=(0, 1, 0), rings_per_side=3, bulge=0.25,
         edge_round=0.6, meta=None):
    """Thick, rounded 2D shape (wing, lens, patch, ear flap...).

    outline : (M, 2) closed outline in local (x, y), star-shaped around its
              centroid (every point visible from the centroid).
    thickness : total thickness along the normal (x_axis cross y_axis).
    bulge   : extra puffiness of the faces toward the centre (0 = flat).
    Front = +normal side. attr: a0 = outline fraction, a1 = 0 (back centre)
    .. 0.5 (rim) .. 1 (front centre). Paint can also use the 3D position.
    """
    O = np.asarray(outline, float)
    c2 = O.mean(axis=0)
    ox, oy = np.asarray(x_axis, float), np.asarray(y_axis, float)
    nz = np.cross(ox, oy)
    nz /= np.linalg.norm(nz)
    org = np.asarray(origin, float)
    h = thickness / 2.0

    def ring(scale, z):
        pts = c2 + (O - c2) * scale
        return org + np.outer(pts[:, 0], ox) + np.outer(pts[:, 1], oy) + np.outer(np.full(len(O), z), nz)

    rings, a1 = [], []
    # back face: centre -> rim, rounded edge, front face: rim -> centre
    fr = np.linspace(1.0 / (rings_per_side + 1), 1.0, rings_per_side + 1)[:-1]
    for s in fr:
        rings.append(ring(s, -h * (1 + bulge * (1 - s * s))))
        a1.append(0.5 * s * 0.9)
    edge = [(-0.85, 1.0 - 0.02 * edge_round), (0.0, 1.0), (0.85, 1.0 - 0.02 * edge_round)]
    for zf, s in edge:
        rings.append(ring(s, h * zf))
        a1.append(0.5 + 0.05 * zf)
    for s in fr[::-1]:
        rings.append(ring(s, h * (1 + bulge * (1 - s * s))))
        a1.append(1.0 - 0.5 * s * 0.9)
    centre0 = org + c2[0] * ox + c2[1] * oy - nz * h * (1 + bulge)
    centre1 = org + c2[0] * ox + c2[1] * oy + nz * h * (1 + bulge)
    a1 = np.asarray(a1)
    v = 0.04 + 0.92 * a1
    data = loft(np.asarray(rings), centre0, centre1, v_rings=v, v_apex0=0.0,
                v_apex1=1.0, attr_v=a1)
    data = _apex_attr_fix(data, len(rings), len(O), 0.0, 1.0)
    return make_shell(name, part, data, island, meta)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

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
