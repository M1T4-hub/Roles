"""Kawaii Space Buns: anime double-bun hairstyle with ruffled scrunchies.

Item module for tools/build_ugc.py (see tools/items/README.md for the
contract). Units are studs, Roblox axes (+Y up, avatar faces -Z), origin =
HairAttachment (top centre of the 1.2-stud R15 head).

Build: one scalp cap that hugs the head (top, sides and nape), soft bangs
that stop above the eyes, two face-framing strands, chunky back clumps that
cover the nape, and two round buns high on the head, each held by a puffy
scrunchie in an accent colour.
"""

from __future__ import annotations

import numpy as np

from ugclib.bake import aa as _aa
from ugclib.bake import mix
from ugclib.geometry import TAU, loft, make_shell
from ugclib.geometry import smoothstep as _ss

NAME = "KawaiiSpaceBuns"
SLUG = "kawaii-space-buns"
ASSET_TYPE = "Hair"
ATTACHMENT = "HairAttachment"
AFT_BODY_SCALE = "Classic"
AO_RADIUS = 0.17
# Preview cameras, relative to the attachment point (studs).
PREVIEW = {
    "front": dict(cam="1.7,0.45,-2.95", target="0,-0.36,0"),
    "dos": dict(cam="-1.75,1.35,2.6", target="0,-0.4,0"),
    "profil": dict(cam="-3.35,0.25,-0.35", target="0,-0.4,0"),
}

# Part ids, used by paint().
PART_CAP = 0
PART_BUN = 1
PART_SCRUNCHIE = 2
PART_BANG = 3
PART_SIDE = 4
PART_BACK = 5

COLORWAYS = {
    # Soft black with pink scrunchies
    "Noir": dict(
        hair=(52, 48, 64), root=(30, 28, 40), tip=(86, 80, 106),
        edge=(26, 24, 34), shine=(118, 112, 146), shade=(16, 14, 26),
        accent=(255, 150, 192), accent_dark=(222, 92, 146), accent_shade=(150, 40, 96)),
    # Chestnut brown with cream scrunchies
    "Chatain": dict(
        hair=(132, 84, 56), root=(92, 56, 38), tip=(170, 116, 78),
        edge=(84, 50, 32), shine=(222, 172, 128), shade=(56, 30, 20),
        accent=(255, 240, 222), accent_dark=(230, 202, 176), accent_shade=(150, 112, 90)),
    # Honey blonde with baby-blue scrunchies
    "Blond": dict(
        hair=(240, 184, 98), root=(204, 138, 64), tip=(252, 214, 142),
        edge=(194, 128, 56), shine=(255, 240, 198), shade=(146, 86, 34),
        accent=(150, 204, 255), accent_dark=(98, 160, 236), accent_shade=(50, 96, 170)),
    # Pastel pink with white scrunchies
    "Rose": dict(
        hair=(255, 172, 202), root=(232, 122, 162), tip=(255, 206, 224),
        edge=(224, 112, 152), shine=(255, 238, 246), shade=(176, 70, 112),
        accent=(255, 255, 255), accent_dark=(232, 216, 228), accent_shade=(170, 140, 160)),
    # Lavender with pink scrunchies
    "Lilas": dict(
        hair=(192, 166, 236), root=(146, 118, 204), tip=(222, 204, 252),
        edge=(138, 108, 196), shine=(244, 236, 255), shade=(90, 64, 150),
        accent=(255, 176, 210), accent_dark=(236, 120, 170), accent_shade=(160, 60, 110)),
}


# ---------------------------------------------------------------------------
# Head model (same as the previewer's R15 mannequin, in attachment space)
# ---------------------------------------------------------------------------

HEAD_R = 0.6
FIL = 0.26
TOP_R = HEAD_R - FIL               # radius of the flat top
S_FIL = TOP_R                      # profile arclength where the fillet starts
S_SIDE = TOP_R + FIL * np.pi / 2   # ... where the vertical side starts
HEAD_H = 1.2


def _profile(s):
    """Head profile (r, y, nr, ny) at arclength s from the top pole.

    Past the fillet the profile continues straight down (hair hangs
    vertically instead of following the chin/bottom fillet).
    """
    s = np.asarray(s, float)
    a = np.clip((s - S_FIL) / FIL, 0.0, np.pi / 2)
    r = np.where(s < S_FIL, s, np.where(s < S_SIDE, TOP_R + FIL * np.sin(a), HEAD_R))
    y = np.where(s < S_FIL, 0.0,
                 np.where(s < S_SIDE, -FIL + FIL * np.cos(a), -FIL - (s - S_SIDE)))
    return r, y, np.sin(a), np.cos(a)


def surf(phi, s, off):
    """Point and normal on the head surface offset by `off`.

    phi = azimuth from the front (0 = -Z, +pi/2 = avatar right, +X).
    """
    phi, s, off = np.broadcast_arrays(*(np.asarray(v, float) for v in (phi, s, off)))
    r, y, nr, ny = _profile(s)
    R = r + off * nr
    Y = y + off * ny
    P = np.stack([R * np.sin(phi), Y, -R * np.cos(phi)], -1)
    N = np.stack([nr * np.sin(phi), ny, -nr * np.cos(phi)], -1)
    return P, N


def head_radius(y):
    """Real head radius at height y (with both fillets)."""
    y = np.asarray(y, float)
    top = TOP_R + np.sqrt(np.clip(FIL ** 2 - (y + FIL) ** 2, 0, None))
    bot = TOP_R + np.sqrt(np.clip(FIL ** 2 - (y + HEAD_H - FIL) ** 2, 0, None))
    return np.where(y > -FIL, top, np.where(y > -HEAD_H + FIL, HEAD_R, bot))


# ---------------------------------------------------------------------------
# Scalp cap
# ---------------------------------------------------------------------------

def cap_offset(s):
    """Cap thickness over the head: a little volume on top, snug on the sides."""
    return 0.040 + 0.034 * (1.0 - _ss(0.0, 0.62, s))


def cap_drop(phi):
    """How far below the fillet (S_SIDE) the cap's edge reaches, per azimuth."""
    a = np.degrees(np.abs(np.angle(np.exp(1j * np.asarray(phi, float)))))
    return np.interp(a, [0, 35, 60, 90, 120, 150, 180],
                     [0.075, 0.085, 0.16, 0.32, 0.55, 0.70, 0.74])


def build_cap(island, M=32):
    phi = np.pi + TAU * np.arange(M) / M          # seam at the back
    s_top = [0.10, 0.20, 0.29, 0.38, 0.47, 0.56, 0.65, S_SIDE]
    drop = cap_drop(phi)
    rings, v = [], []
    for s in s_top:
        P, _ = surf(phi, s, cap_offset(s))
        rings.append(P)
        v.append(s)
    for f, off in ((0.40, None), (0.85, None), (1.0, 0.022)):
        s = S_SIDE + drop * f
        o = cap_offset(s) if off is None else np.full(M, off)
        P, _ = surf(phi, s, o)
        if off is not None:
            P[:, 1] -= 0.008
        rings.append(P)
        v.append(S_SIDE + 0.45 * f)
    # lip tucked inside the head, then a fan to a point inside the head
    y_lip = -FIL - drop - 0.016
    r_lip = head_radius(y_lip) - 0.012
    rings.append(np.stack([r_lip * np.sin(phi), y_lip, -r_lip * np.cos(phi)], -1))
    v.append(S_SIDE + 0.5)
    v = np.asarray(v)
    vt = 1.0 - 0.96 * v / v[-1]
    data = loft(rings, apex0=(0.0, cap_offset(0.0), 0.0), apex1=(0.0, -0.45, 0.0),
                v_rings=vt, v_apex0=1.0, v_apex1=0.0, attr_v=v / v[-1])
    return make_shell("Scalp", PART_CAP, data, island)


# ---------------------------------------------------------------------------
# Hair clumps (tapered sweeps lying on the head)
# ---------------------------------------------------------------------------

def lens(M, w, t_out, t_in, tuck=0.0, sharp=1.3):
    """Lens-shaped clump section: (a = along the surface normal, b = across)."""
    psi = TAU * np.arange(M) / M
    b = w * np.cos(psi)
    sn = np.sin(psi)
    a = np.sign(sn) * np.abs(sn) ** sharp * np.where(sn > 0, t_out, t_in)
    a = a - tuck * (b / max(w, 1e-6)) ** 2
    return np.column_stack([a, b])


def clump(name, part, island, path, us, width, t_out, t_in, M=8, tuck=0.3,
          root_len=0.03, tip_len=0.02, meta=None):
    """Hair clump along path(u) -> (P, N_surface); width/t_* are functions of u."""
    eps = 1e-3
    rings, centres, Ts = [], [], []
    for u in us:
        P, Ns = path(u)
        Pa, _ = path(max(u - eps, 0.0))
        Pb, _ = path(min(u + eps, 1.0))
        T = (Pb - Pa) / np.linalg.norm(Pb - Pa)
        B = np.cross(T, Ns)
        B /= np.linalg.norm(B)
        N = np.cross(B, T)
        w, to, ti = width(u), t_out(u), t_in(u)
        sec = lens(M, w, to, ti, tuck=tuck * to)
        rings.append(P + np.outer(sec[:, 0], N) + np.outer(sec[:, 1], B))
        centres.append(P)
        Ts.append(T)
    rings = np.asarray(rings)
    apex0 = centres[0] - Ts[0] * root_len
    apex1 = centres[-1] + Ts[-1] * tip_len
    us = np.asarray(us, float)
    data = loft(rings, apex0, apex1, v_rings=0.04 + 0.92 * us, v_apex0=0.0,
                v_apex1=1.0, attr_v=us)
    V, faces, UV, faces_uv, attr = data
    n = len(us) * (M + 1)
    attr[n:n + M, 1] = 0.0
    attr[n + M:, 1] = 1.0
    return make_shell(name, part, (V, faces, UV, faces_uv, attr), island, meta)


def _taper(w_root, w_mid, u_peak=0.35, tip_pow=0.65):
    """Width profile: root -> widest at u_peak -> rounded-pointed tip."""
    def f(u):
        if u <= u_peak:
            return w_root + (w_mid - w_root) * _ss(0.0, u_peak, u)
        t = (u - u_peak) / (1.0 - u_peak)
        return max(w_mid * (1.0 - t ** 2.2) ** tip_pow, 0.004)
    return f


# Bangs: (azimuth of the tip in degrees, tip drop below S_SIDE, curl in deg)
BANGS = [(-47.0, 0.265, 5.0), (-31.0, 0.205, 3.0), (-15.0, 0.180, 1.5),
         (0.0, 0.192, 0.0), (15.0, 0.180, -1.5), (31.0, 0.205, -3.0),
         (47.0, 0.265, -5.0)]
BANG_US = [0.0, 0.18, 0.36, 0.53, 0.68, 0.81, 0.92, 1.0]


def build_bang(i, island):
    tip_phi, drop, curl = BANGS[i]
    tip_phi, curl = np.radians(tip_phi), np.radians(curl)
    root_phi = tip_phi * 0.55
    s0, s1 = 0.24, S_SIDE + drop

    def path(u):
        phi = root_phi + (tip_phi - root_phi) * _ss(0.0, 0.6, u) + curl * _ss(0.6, 1.0, u)
        s = s0 + (s1 - s0) * u
        off = (cap_offset(s) - 0.032 + 0.060 * _ss(0.0, 0.38, u)
               - 0.016 * _ss(0.75, 1.0, u))
        return surf(phi, s, off)

    width = _taper(0.06, 0.120, u_peak=0.72, tip_pow=0.5)
    t_out = _taper(0.02, 0.040, u_peak=0.6, tip_pow=0.6)
    t_in = _taper(0.01, 0.018, u_peak=0.6, tip_pow=0.6)
    return clump(f"Bang{i}", PART_BANG, island, path, BANG_US, width, t_out, t_in,
                 M=8, tuck=0.35, root_len=0.03, tip_len=0.016)


SIDE_US = [0.0, 0.14, 0.28, 0.42, 0.56, 0.69, 0.81, 0.91, 1.0]


def build_side(side, island):
    """Face-framing strand beside the cheek, side = +1 (avatar right) / -1."""
    s0, s1 = 0.40, S_SIDE + 0.64

    def path(u):
        phi = side * np.radians(66.0 - 8.0 * _ss(0.2, 1.0, u) - 4.0 * _ss(0.75, 1.0, u))
        s = s0 + (s1 - s0) * u
        off = (cap_offset(s) - 0.030 + 0.052 * _ss(0.0, 0.35, u)
               + 0.018 * _ss(0.45, 0.85, u) - 0.012 * _ss(0.85, 1.0, u))
        return surf(phi, s, off)

    width = _taper(0.05, 0.096, u_peak=0.38, tip_pow=0.45)
    t_out = _taper(0.02, 0.036, u_peak=0.3, tip_pow=0.7)
    t_in = _taper(0.012, 0.020, u_peak=0.3, tip_pow=0.7)
    return clump(f"Strand{'R' if side > 0 else 'L'}", PART_SIDE, island, path, SIDE_US,
                 width, t_out, t_in, M=8, tuck=0.35, root_len=0.03, tip_len=0.025)


# Back clumps: (azimuth deg, root s, tip drop below S_SIDE, flick deg, width)
BACKS = [(-121.0, 0.16, 0.60, -14.0, 0.205), (-145.0, 0.13, 0.78, -9.0, 0.215),
         (-167.0, 0.11, 0.86, -4.0, 0.205), (167.0, 0.11, 0.84, 4.0, 0.205),
         (145.0, 0.13, 0.76, 9.0, 0.215), (121.0, 0.16, 0.60, 14.0, 0.205)]
CROWN_CONVERGE = 0.35   # back locks radiate from a whorl at the back of the crown
# Temple clumps under the buns: (azimuth deg, root s, tip drop, flick deg, width)
TEMPLES = [(-88.0, 0.58, 0.44, 5.0, 0.135), (88.0, 0.58, 0.44, -5.0, 0.135)]
BACK_US = [0.0, 0.14, 0.25, 0.35, 0.46, 0.60, 0.75, 0.89, 1.0]
TEMPLE_US = [0.0, 0.2, 0.4, 0.58, 0.74, 0.88, 1.0]


def build_back(i, island, table=BACKS, us=BACK_US, name="Back", converge=CROWN_CONVERGE):
    phi_c, s0, drop, flick, wmax = table[i]
    phi_c, flick = np.radians(phi_c), np.radians(flick)
    s1 = S_SIDE + drop
    phi_root = np.pi * np.sign(phi_c) + (phi_c - np.pi * np.sign(phi_c)) * converge

    def path(u):
        phi = phi_root + (phi_c - phi_root) * _ss(0.0, 0.5, u) + flick * _ss(0.55, 1.0, u)
        s = s0 + (s1 - s0) * u
        off = (cap_offset(s) - 0.036 + 0.060 * _ss(0.0, 0.40, u)
               + 0.034 * _ss(0.40, 0.78, u) - 0.026 * _ss(0.80, 1.0, u))
        return surf(phi, s, off)

    width = _taper(0.05, wmax, u_peak=0.48, tip_pow=0.5)
    t_out = _taper(0.02, 0.034, u_peak=0.45, tip_pow=0.6)
    t_in = _taper(0.012, 0.016, u_peak=0.45, tip_pow=0.6)
    return clump(f"{name}{i}", PART_BACK, island, path, us, width, t_out, t_in,
                 M=6, tuck=0.9, root_len=0.03, tip_len=0.018)


# ---------------------------------------------------------------------------
# Buns + scrunchies
# ---------------------------------------------------------------------------

BUN_PHI = np.radians(97.0)     # azimuth from the front (slightly behind the side)
BUN_TILT = np.radians(35.0)    # axis angle from vertical (front view: 10/2 o'clock)
BUN_RAD = 0.262                # equatorial radius
BUN_HALF = 0.240               # half height along its axis
BUN_LIFT = 0.165               # bun centre distance from the cap surface


def bun_frame(side):
    """(centre, axis, base) of one bun."""
    phi = side * BUN_PHI
    s = S_FIL + FIL * BUN_TILT
    base, axis = surf(phi, s, cap_offset(s))
    centre = base + axis * BUN_LIFT
    return centre, axis, base


def _basis(axis):
    """Right-handed basis (e1, axis, e3) with e1 roughly horizontal."""
    e1 = np.cross(axis, [0.0, 0.0, 1.0])
    if np.linalg.norm(e1) < 1e-6:
        e1 = np.array([1.0, 0.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e3 = np.cross(e1, axis)
    return e1, axis, e3


def build_bun(side, island, segments=20):
    c, axis, _ = bun_frame(side)
    e1, e2, e3 = _basis(axis)
    th = np.array([0.0, 0.85, 1.25, 1.58, 1.90, 2.22, 2.52, 2.82, np.pi])
    r = BUN_RAD * np.sin(th)
    y = -BUN_HALF * np.cos(th)
    psi = TAU * np.arange(segments) / segments
    rings = []
    for ri, yi in zip(r[1:-1], y[1:-1]):
        loc = np.column_stack([ri * np.cos(psi), np.full(segments, yi), ri * np.sin(psi)])
        rings.append(c + loc[:, :1] * e1 + loc[:, 1:2] * e2 + loc[:, 2:] * e3)
    t = th / np.pi
    data = loft(rings, apex0=c - e2 * BUN_HALF, apex1=c + e2 * BUN_HALF,
                v_rings=t[1:-1], v_apex0=0.0, v_apex1=1.0, attr_v=t[1:-1],
                u_by_arclength=False)
    V, faces, UV, faces_uv, attr = data
    n = len(rings) * (segments + 1)
    attr[n:n + segments, 1] = 0.0
    attr[n + segments:, 1] = 1.0
    return make_shell(f"Bun{'R' if side > 0 else 'L'}", PART_BUN,
                      (V, faces, UV, faces_uv, attr), island)


SCR_Y = -0.150      # scrunchie height along the bun axis (from the bun centre)
SCR_TUBE = 0.068
SCR_BUMPS = 5


def build_scrunchie(side, island, K=25, M=6):
    """Ruffled ring at the bun base; the left one mirrors the right one."""
    c, axis, _ = bun_frame(+1)
    e1, e2, e3 = _basis(axis)
    yb = SCR_Y
    r_bun = BUN_RAD * np.sqrt(max(1.0 - (yb / BUN_HALF) ** 2, 0.0))
    R = r_bun + 0.018
    ang = TAU * np.arange(K) / K
    psi = TAU * np.arange(M) / M
    rings = []
    for k, a in enumerate(ang):
        radial = np.cos(a) * e1 + np.sin(a) * e3
        ruff = 1.0 + 0.24 * np.cos(SCR_BUMPS * a)
        centre = c + e2 * yb + radial * R
        tr = SCR_TUBE * ruff
        # slightly flattened along the axis, puffier outward
        sec_r = tr * (1.0 + 0.10 * np.cos(psi)) * np.cos(psi)
        sec_y = tr * 0.92 * np.sin(psi)
        rings.append(centre + np.outer(sec_r, radial) + np.outer(sec_y, e2))
    rings = np.asarray(rings) * np.array([side, 1.0, 1.0])
    us = np.arange(K) / K
    data = loft(rings, None, None, v_rings=us, v_apex0=0, v_apex1=1, attr_v=us,
                closed_loop=True)
    return make_shell(f"Scrunchie{'R' if side > 0 else 'L'}", PART_SCRUNCHIE, data, island)


# ---------------------------------------------------------------------------
# Assembly + UV layout
# ---------------------------------------------------------------------------

def _skyline(rects, order, gap):
    """Bottom-left skyline packing in the unit square; None if it overflows."""
    sky = [(0.0, 0.0, 1.0)]                       # (x, y, width) segments
    out = [None] * len(rects)
    for i in order:
        w, h = rects[i][0] + gap, rects[i][1] + gap
        best = None
        for x, _, _ in sky:
            if x + w > 1.0 - gap:
                break
            y = max(sy for sx, sy, sw in sky if sx < x + w - 1e-12 and sx + sw > x + 1e-12)
            if y + h <= 1.0 - gap and (best is None or (y + h, x) < (best[1] + h, best[0])):
                best = (x, y)
        if best is None:
            return None
        x, y = best
        out[i] = (x + gap, y + gap, x + gap + rects[i][0], y + gap + rects[i][1])
        new = []
        for sx, sy, sw in sky:                     # cut [x, x + w] out of the skyline
            if sx + sw <= x or sx >= x + w:
                new.append((sx, sy, sw))
                continue
            if sx < x:
                new.append((sx, sy, x - sx))
            if sx + sw > x + w:
                new.append((x + w, sy, sx + sw - x - w))
        new.append((x, y + h, w))
        new.sort()
        merged = [new[0]]
        for seg in new[1:]:
            px, py, pw = merged[-1]
            if abs(py - seg[1]) < 1e-12 and abs(px + pw - seg[0]) < 1e-9:
                merged[-1] = (px, py, pw + seg[2])
            else:
                merged.append(seg)
        sky = merged
    return out


def _pack(sizes, gap=0.008):
    """Pack rectangles (w, h in studs) into the unit square at the largest scale."""
    n = len(sizes)
    keys = [lambda i: -sizes[i][1], lambda i: -sizes[i][0],
            lambda i: -sizes[i][0] * sizes[i][1], lambda i: -max(sizes[i])]
    best_k, best = 0.0, None
    for key in keys:
        order = sorted(range(n), key=key)
        lo, hi = 0.01, 2.0
        for _ in range(36):
            mid = 0.5 * (lo + hi)
            ok = _skyline([(w * mid, h * mid) for w, h in sizes], order, gap)
            lo, hi = (mid, hi) if ok else (lo, mid)
        if lo > best_k:
            best_k = lo
            best = _skyline([(w * lo, h * lo) for w, h in sizes], order, gap)
    return best


def _uv_size(shell):
    """(around, along) extents in studs that give the shell an even texel density."""
    V, UV = shell.V, shell.UV
    su, sv = [], []
    area = 0.0
    for f, ft in zip(shell.faces, shell.faces_uv):
        for i in range(1, len(f) - 1):
            area += 0.5 * np.linalg.norm(np.cross(V[f[i]] - V[f[0]], V[f[i + 1]] - V[f[0]]))
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            ta, tb = ft[i], ft[(i + 1) % len(f)]
            du, dv = abs(UV[tb, 0] - UV[ta, 0]), abs(UV[tb, 1] - UV[ta, 1])
            L = np.linalg.norm(V[b] - V[a])
            if du > 4 * dv and du > 1e-6:
                su.append(L / du)
            elif dv > 4 * du and dv > 1e-6:
                sv.append(L / dv)
    su, sv = float(np.mean(su)), float(np.mean(sv))
    k = np.sqrt(area / (su * sv))
    return su * k, sv * k


def build_shells():
    shells = [build_cap(None)]
    shells += [build_bun(s, None) for s in (-1, 1)]
    shells += [build_scrunchie(s, None) for s in (-1, 1)]
    shells += [build_bang(i, None) for i in range(len(BANGS))]
    shells += [build_side(s, None) for s in (-1, 1)]
    shells += [build_back(i, None) for i in range(len(BACKS))]
    shells += [build_back(i, None, TEMPLES, TEMPLE_US, "Temple", 1.0) for i in range(len(TEMPLES))]
    # Visible-area weights: the cap is partly hidden under the clumps.
    weight = {PART_CAP: 0.8, PART_BUN: 1.0, PART_SCRUNCHIE: 1.0, PART_BANG: 1.0,
              PART_SIDE: 1.0, PART_BACK: 0.9}
    sizes = []
    for sh in shells:
        w, h = _uv_size(sh)
        k = np.sqrt(weight[sh.part])
        sizes.append((w * k, h * k))
    for sh, isl in zip(shells, _pack(sizes)):
        sh.island = isl
    return shells


# ---------------------------------------------------------------------------
# Paint
# ---------------------------------------------------------------------------

def paint(ctx, C):
    P, N, part, a0, a1 = ctx["P"], ctx["N"], ctx["part"], ctx["a0"], ctx["a1"]
    n = len(P)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    phi = np.arctan2(x, -z)
    clumps = np.isin(part, [PART_BANG, PART_SIDE, PART_BACK])
    scr = part == PART_SCRUNCHIE
    bun = part == PART_BUN

    col = np.tile(C["hair"], (n, 1))
    shade = np.tile(C["shade"], (n, 1))

    # darker roots around the crown and along the parting (position based on
    # the cap and the clumps alike, so the clumps blend into the cap)
    r_xz = np.hypot(x, z)
    cap = part == PART_CAP
    root_top = (cap | clumps) * (1.0 - _ss(0.10, 0.42, r_xz)) * _ss(-0.12, 0.02, y) * 0.8
    parting = cap * (1.0 - _ss(0.008, 0.03, np.abs(x))) * (z > -0.42) * (y > -0.05) * 0.6
    col = mix(col, C["root"][None], np.clip(root_top + parting, 0, 1))

    # lighter tips on clumps
    tip = clumps * _ss(0.62, 1.0, a1)
    col = mix(col, C["tip"][None], tip)

    # darker clump edges (the lens points)
    edge = clumps * _ss(0.80, 0.98, np.abs(np.cos(TAU * a0))) * 0.7 * _ss(0.15, 0.75, a1)
    col = mix(col, C["edge"][None], edge)

    # anime "angel ring": one lens-shaped shine stroke per clump around the crown
    radial = (N[:, 0] * x + N[:, 2] * z) / np.maximum(r_xz, 1e-6)
    facing = _ss(0.2, 0.5, N[:, 1] * 0.5 + radial)
    across = np.abs(np.cos(TAU * a0))                  # 0 on the clump spine, 1 at its edges
    outer = np.sin(TAU * a0) > 0
    # the ring sits on the crown's curve at the front and lower on the back locks
    y_c = np.interp(np.degrees(np.abs(phi)), [0, 50, 75, 110, 180],
                    [-0.125, -0.13, -0.27, -0.30, -0.34]) + 0.008 * np.sin(phi * 5.0 + 0.7)
    narrow = np.clip(across / np.where(part == PART_BANG, 0.92, 0.80), 0, 1)
    top = y_c + 0.017 * np.clip(1.0 - narrow ** 3, 0, 1)
    bot = y_c - 0.056 * np.clip(1.0 - narrow ** 1.5, 0, 1) ** 1.2
    d_ring = np.maximum(y - top, bot - y)
    ring = clumps * outer * _aa(d_ring, 0.006) * facing * 0.85
    col = mix(col, C["shine"][None], ring)

    # Buns and scrunchies are painted in mirrored coordinates (left = mirror
    # of right) so both sides match their mirrored geometry.
    flip = np.where(x < 0, -1.0, 1.0)
    Pm = P * np.column_stack([flip, np.ones(n), np.ones(n)])
    c, axis, _ = bun_frame(+1)
    e1, e2, e3 = _basis(axis)
    d = Pm - c
    ang = np.arctan2(d @ e3, d @ e1)

    # buns: spiral grooves (twisted bun) + a short arc of shine strokes
    h = (d @ e2) / BUN_HALF                              # -1 bottom .. 1 top
    lat = np.arcsin(np.clip(h, -1, 1))
    sw = ((ang / TAU) * 4.0 + lat * 0.75) % 1.0
    groove = (1.0 - _ss(0.02, 0.22, np.minimum(sw, 1.0 - sw))) * (1.0 - _ss(0.45, 0.95, h))
    col = mix(col, C["edge"][None], bun * groove * 0.42)
    col = mix(col, C["root"][None], bun * (1.0 - _ss(-0.6, -0.1, h)) * 0.5)
    lv = np.array([0.30, 0.0, -1.0])
    la = np.arctan2(lv @ e3, lv @ e1)
    dang = np.abs(np.angle(np.exp(1j * (ang - la))))
    gap = 1.0 - _ss(0.0, 0.16, np.minimum(sw, 1.0 - sw))         # 1 on a groove
    span = np.clip(1.0 - (dang / 1.15) ** 2, 0, 1) * (1.0 - gap)
    arc_top = 0.56 + 0.05 * span
    arc_bot = 0.56 - 0.20 * span ** 1.3
    arc = _aa(np.maximum(h - arc_top, arc_bot - h), 0.03) * (span > 0.02)
    col = mix(col, C["shine"][None], bun * arc * 0.8)

    # scrunchies: accent with soft pleat lines in the ruffle valleys
    pleat = 0.5 + 0.5 * np.cos(SCR_BUMPS * ang)          # 1 on the puffs, 0 in valleys
    col[scr] = C["accent"]
    shade[scr] = C["accent_shade"]
    col = mix(col, C["accent_dark"][None], scr * (1.0 - _ss(0.0, 0.45, pleat)) * 0.8)

    return col, shade
