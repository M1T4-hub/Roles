"""Fluffy Wolf Cut: layered shaggy wolf-cut hair with curtain bangs.

Item module for tools/build_ugc.py (see tools/items/README.md for the
contract). Units are studs, Roblox axes (+Y up, avatar faces -Z, +X = the
avatar's right), origin = HairAttachment (top centre of the 1.2-stud R15
head, so the head occupies local y in [-1.2, 0], radius 0.6).

Construction: a thin scalp cap hugging the head, then ~30 pointed, tapered
clumps swept over a "hull" that follows the head's meridian (flat top,
0.26 fillet, vertical side). Clumps come in overlapping layers:
  * top layer   : choppy layers radiating from the crown, alternating long /
                  short and stacked like shingles, flicking out around
                  temple height (the wolf-cut volume),
  * mid layer   : a few back-crown pieces between the top and jaw points,
  * under layer : longer layers reaching the jaw, offset half a spacing,
Lengths, tip directions, widths and flicks carry a fixed, non-mirrored
jitter so the back reads as shaggy hair, not as regular rows of scales.
  * mullet      : long pointed pieces down the nape to y ~ -1.5,
  * bangs       : curtain bangs parted in the middle + face-framing pieces.
"""

from __future__ import annotations

import numpy as np

from ugclib.bake import aa as _aa
from ugclib.bake import mix
from ugclib.geometry import TAU, loft, make_shell
from ugclib.geometry import smoothstep as _ss

NAME = "FluffyWolfCut"
SLUG = "fluffy-wolf-cut"
ASSET_TYPE = "Hair"
ATTACHMENT = "HairAttachment"
AFT_BODY_SCALE = "Classic"
AO_RADIUS = 0.2
# Preview cameras, relative to the attachment point (studs).
PREVIEW = {
    "front": dict(cam="1.9,0.25,-3.2", target="0,-0.62,0"),
    "dos": dict(cam="-1.8,1.0,3.0", target="0,-0.7,0"),
    "profil": dict(cam="-3.6,0.15,-0.3", target="0,-0.65,0"),
}

COLORWAYS = {
    # Soft black with a cool blue-grey shine
    "Noir": dict(
        base=(54, 52, 66), dark=(28, 26, 38), shade=(14, 12, 22),
        light=(116, 120, 150), edge=(34, 32, 46),
        tip_l=(54, 52, 66), tip_r=(54, 52, 66)),
    # Chestnut brown
    "Chatain": dict(
        base=(122, 82, 60), dark=(80, 50, 36), shade=(46, 26, 18),
        light=(178, 136, 106), edge=(92, 58, 42),
        tip_l=(122, 82, 60), tip_r=(122, 82, 60)),
    # Platinum blond with soft rooted shading
    "Platine": dict(
        base=(242, 230, 194), dark=(204, 184, 144), shade=(148, 122, 88),
        light=(255, 252, 236), edge=(216, 198, 158),
        tip_l=(246, 238, 212), tip_r=(246, 238, 212)),
    # Pastel pink
    "Rose": dict(
        base=(255, 164, 200), dark=(222, 108, 158), shade=(170, 62, 112),
        light=(255, 204, 226), edge=(232, 124, 172),
        tip_l=(255, 164, 200), tip_r=(255, 164, 200)),
    # Black with split-dyed tips: pink on the left, blue on the right
    "Duo": dict(
        base=(48, 46, 60), dark=(26, 24, 36), shade=(14, 12, 22),
        light=(112, 116, 146), edge=(32, 30, 44),
        tip_l=(255, 128, 186), tip_r=(110, 176, 255)),
}

# ---------------------------------------------------------------------------
# Head hull
# ---------------------------------------------------------------------------

HEAD_R = 0.6
FIL = 0.26
FLAT = HEAD_R - FIL                      # 0.34: radius of the flat head top
S_SIDE0 = FLAT + FIL * np.pi / 2.0       # meridian arclength where the side starts

LAYER_IDS = {"cap": 0, "top": 1, "under": 2, "mullet": 3, "bang": 4}
DOME = 0.15                              # extra crown volume of the whole hairdo


def dome(s):
    return DOME * (1.0 - _ss(0.05, 0.85, np.asarray(s, float)))


S_SIDE1 = S_SIDE0 + (1.2 - 2 * FIL)     # where the bottom fillet starts


def meridian(s, o, bottom=False):
    """Head meridian at arclength s from the top centre, offset o outward.

    Returns (r, y, nr, ny). Below the side, the hull continues straight
    down (hair hangs), unless bottom=True (follow the head's bottom fillet).
    """
    s = np.asarray(s, float)
    o = np.asarray(o, float) + 0 * s
    a = np.clip((s - FLAT) / FIL, 0.0, np.pi / 2.0)
    r = np.where(s < FLAT, s, np.where(s < S_SIDE0, FLAT + (FIL + o) * np.sin(a), HEAD_R + o))
    y = np.where(s < FLAT, o, np.where(s < S_SIDE0, -FIL + (FIL + o) * np.cos(a),
                                       -FIL - (s - S_SIDE0)))
    nr = np.where(s < FLAT, 0.0, np.sin(a))
    ny = np.where(s < FLAT, 1.0, np.cos(a))
    if bottom:
        b = np.clip((s - S_SIDE1) / FIL, 0.0, np.pi / 2.0)
        low = s > S_SIDE1
        r = np.where(low, FLAT + (FIL + o) * np.cos(b), r)
        y = np.where(low, -1.2 + FIL - (FIL + o) * np.sin(b), y)
        nr = np.where(low, np.cos(b), nr)
        ny = np.where(low, -np.sin(b), ny)
    return r, y, nr, ny


def hull(s, theta, o, bottom=False):
    """3D point + outward normal. theta = 0 at the front (-Z), +90deg = +X."""
    r, y, nr, ny = meridian(s, o, bottom)
    st, ct = np.sin(theta), np.cos(theta)
    P = np.column_stack((r * st, y, -r * ct))
    N = np.column_stack((nr * st, ny, -nr * ct))
    return P, N


# ---------------------------------------------------------------------------
# Scalp cap
# ---------------------------------------------------------------------------

def rim_y(theta):
    """Hairline height of the cap: high on the forehead, low on the nape.

    The back-sides (behind the ears) are pulled a little lower so no bare
    "undercut" band shows between the jaw layer and the nape.
    """
    back = (1.0 - np.cos(theta)) / 2.0           # 0 front .. 1 back
    y = -0.29 - 0.79 * back ** 0.6 - 0.035 * _ss(0.45, 0.8, back) * (1.0 - _ss(0.85, 1.0, back))
    return np.maximum(y, -1.08)


def _s_at_y(y):
    """Meridian arclength (true head, with bottom fillet) reaching height y."""
    y = np.asarray(y, float)
    s_side = S_SIDE0 + (-FIL - y)
    yb = -(1.2 - FIL)
    b = np.arcsin(np.clip((yb - y) / FIL, 0.0, 1.0))
    return np.where(y > yb, s_side, S_SIDE1 + FIL * b)


def build_cap(Mc=24):
    theta = TAU * np.arange(Mc) / Mc
    s_rim = _s_at_y(rim_y(theta))
    ts = np.array([0.10, 0.26, 0.43, 0.60, 0.77, 0.93])
    rings = []
    for t in ts:
        o = 0.030 - 0.012 * _ss(0.6, 0.93, t) + dome(t * s_rim)
        rings.append(hull(t * s_rim, theta, o, bottom=True)[0])
    # Hairline: the cap stays clearly outside the skin (chord sag of the
    # 24-gon is ~0.005), then dives steeply under it. The visible hairline is
    # the clean intersection of two clearly non-parallel surfaces, so it
    # never z-fights with the head whatever the head's tessellation.
    rings.append(hull(s_rim - 0.012, theta, 0.016, bottom=True)[0])
    rings.append(hull(s_rim + 0.035, theta, -0.032, bottom=True)[0])
    rings = np.asarray(rings)
    # the last ring sits inside the (convex) head: close it on an interior apex
    apex_in = np.array([0.0, -0.5, 0.05])
    apex_top = np.array([0.0, 0.030 + DOME, 0.0])
    v = np.concatenate([ts * 0.95, [0.97, 1.0]])
    v_r = 1.0 - (0.04 + 0.92 * v)
    data = loft(rings, apex_top, apex_in, v_rings=v_r, v_apex0=0.98, v_apex1=0.01,
                attr_v=v)
    V, faces, UV, faces_uv, attr = data
    K = len(rings)
    n = K * (Mc + 1)
    attr[n:n + Mc, 1] = 0.0
    attr[n + Mc:, 1] = 1.0
    return make_shell("Scalp", 0, (V, faces, UV, faces_uv, attr), (0, 0, 1, 1),
                      meta={"layer": "cap", "circ": TAU * 0.63, "len": 1.2, "weight": 0.55})


# ---------------------------------------------------------------------------
# Hair clumps
# ---------------------------------------------------------------------------

def _plane(s, th_deg):
    """Unrolled head-top map: (s, theta) polar -> 2D (x, z)."""
    th = np.radians(th_deg)
    return np.array([s * np.sin(th), -s * np.cos(th)])


def build_clump(name, part, layer, root, tip, ctrl=None, o_root=-0.07, o_mid=0.08,
                o_tip=0.2, w0=0.4, t0=0.13, M=6, K=9, lift=0.5, curl=0.30,
                root_w=0.45, taper=3.0, root_t=0.86, rise=0.32):
    """One pointed hair clump swept over the head hull.

    root / tip / ctrl : (s, theta_deg) on the unrolled head map (s = meridian
               arclength from the top centre, theta = 0 front, +90 = +X);
               the centre line is a quadratic Bezier in that map.
    o_*      : centre-line offset above the head at the root (buried), along
               the body and at the tip (the outward flick).
    w0 / t0  : max width / thickness. taper: higher = blunter, shorter point.
    """
    k = np.arange(K) / (K - 1)
    u = 1.0 - (1.0 - k) ** 1.3                 # denser rings toward the tip
    R2, T2 = _plane(*root), _plane(*tip)
    C2 = 0.5 * (R2 + T2) if ctrl is None else _plane(*ctrl)
    q = ((1 - u) ** 2)[:, None] * R2 + (2 * u * (1 - u))[:, None] * C2 + (u ** 2)[:, None] * T2
    s = np.hypot(q[:, 0], q[:, 1])
    th = np.arctan2(q[:, 0], -q[:, 1])
    o = (o_root + (o_mid - o_root) * _ss(0.0, rise, u)
         + (o_tip - o_mid) * _ss(lift, 1.0, u) ** 1.4)
    o = o + dome(s)
    P, Nout = hull(s, th, o)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    B = Nout - np.sum(Nout * T, axis=1, keepdims=True) * T
    B /= np.linalg.norm(B, axis=1, keepdims=True)
    W = np.cross(B, T)

    # half-step phase: each side edge is a small flat face (no knife edge)
    # and the top has a soft ridge vertex -> chunky, toy-like clumps.
    phi = TAU * (np.arange(M) + 0.5) / M
    cphi, sphi = np.cos(phi), np.sin(phi)
    cphi = cphi / np.abs(cphi).max()
    rings = []
    for i in range(K):
        grow = root_w + (1.0 - root_w) * _ss(0.0, 0.38, u[i])
        tp = max((1.0 - u[i] ** taper), 0.0) ** 0.75
        w = max(w0 * grow * tp, 0.006)
        tg = root_t + (1.0 - root_t) * _ss(0.0, 0.42, u[i])
        t = max(t0 * tg * max(1.0 - u[i] ** (taper * 0.8), 0.0) ** 0.7, 0.005)
        x = 0.5 * w * cphi
        thin = 1.0 - 0.65 * cphi ** 2              # thin side edges, soft ridge
        yv = 0.5 * t * sphi * thin * np.where(sphi > 0, 1.0, 0.75) - curl * t * cphi ** 2
        rings.append(P[i] + np.outer(x, W[i]) + np.outer(yv, B[i]))
    rings = np.asarray(rings)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    length = arc[-1]
    vr = 0.03 + 0.94 * arc / length
    apex0 = rings[0].mean(axis=0) - T[0] * 0.01
    apex1 = rings[-1].mean(axis=0) + T[-1] * 0.004
    data = loft(rings, apex0, apex1, v_rings=vr, v_apex0=0.0, v_apex1=1.0, attr_v=u)
    V, faces, UV, faces_uv, attr = data
    n = K * (M + 1)
    attr[n:n + M, 1] = 0.0
    attr[n + M:, 1] = 1.0
    circ = float(np.mean([np.linalg.norm(np.roll(r, -1, 0) - r, axis=1).sum() for r in rings]))
    meta = dict(layer=layer, circ=circ, len=float(length), weight=1.0, tip=P[-1].copy(), M=M)
    return make_shell(name, part, (V, faces, UV, faces_uv, attr), (0, 0, 1, 1), meta)


# Fixed, hand-picked jitter (deliberately NOT mirrored left/right) so the
# layers read as choppy, uneven wolf-cut hair instead of regular rows of
# scales: tip length, tip direction, width and flick vary per clump.
J_TOP = [0.0, 0.9, -0.6, 0.4, -1.0, 0.7, -0.3, 0.8]
J_TOP2 = [0.6, -0.5, 0.9, -0.8, 0.3, -0.9, 1.0, -0.2]
J_UNDER = [0.5, -0.3, 0.8, -0.7, 0.2, 0.9, -0.5]
J_UNDER2 = [-0.6, 0.8, -0.2, 0.7, -0.9, 0.4, 0.6]
J_MULLET = [0.6, -0.7, 1.0, -0.4]
J_MULLET2 = [-0.8, 0.5, -0.3, 0.9]


def clump_specs():
    """(name, layer, kwargs) for every clump (angles in degrees)."""
    specs = []
    # Top layer: radiating from the crown, flicking out at temple height.
    # Long / short alternate so the rows of points stagger.
    for i, th in enumerate([75.0, 105.0, 135.0, 165.0, 195.0, 225.0, 255.0, 285.0]):
        side = np.sign(th - 180.0)
        j, j2 = J_TOP[i], J_TOP2[i]
        s_tip = (1.14 if i % 2 == 0 else 0.88) + 0.05 * j
        specs.append((f"Top{i}", "top", dict(
            root=(0.0, th - 14 * side), ctrl=(0.55 * s_tip, th - 6 * side + 1.5 * j2),
            tip=(s_tip, th + 4 * side + 6.0 * j2),
            # short (odd) clumps lie on top of the long ones like shingles:
            # higher, with flatter edges; long ones tuck their edges under.
            o_root=0.012 if i % 2 else -0.004,
            o_mid=0.085 + (0.02 if i % 2 else -0.01), o_tip=0.23 + 0.05 * j2,
            w0=0.52 * (1.0 + 0.10 * j), t0=0.17, M=6, K=10, lift=0.45,
            curl=0.16 if i % 2 else 0.36,
            root_w=0.75, root_t=0.4, rise=0.45, taper=1.5)))
    # Mid layer at the back crown: choppy pieces over the top-layer seams,
    # reaching between the top and jaw points so the tiers don't line up.
    for i, (th, s_tip, j2) in enumerate([(151.0, 1.26, 0.6), (181.0, 1.16, -0.7),
                                         (209.0, 1.30, 0.3)]):
        specs.append((f"Mid{i}", "under", dict(
            root=(0.30, th - 3.0), ctrl=(0.75, th + 2.0 * j2), tip=(s_tip, th + 6.0 * j2),
            o_root=-0.04, o_mid=0.07, o_tip=0.22 + 0.03 * j2, w0=0.40, t0=0.13,
            K=9, lift=0.5, rise=0.5, taper=1.5)))
    # Under layer: to the jaw, between the top-layer clumps.
    for i, th in enumerate([90.0, 120.0, 150.0, 184.0, 210.0, 240.0, 270.0]):
        side = np.sign(th - 180.0)
        j, j2 = J_UNDER[i], J_UNDER2[i]
        length = [1.34, 1.44, 1.46, 1.34, 1.46, 1.44, 1.34][i] + 0.06 * j
        specs.append((f"Under{i}", "under", dict(
            root=(0.36, th - 4 * side), ctrl=(0.85, th + 2.5 * j2),
            tip=(length, th + 4 * side + 5.0 * j2),
            o_mid=0.045, o_tip=0.19 + 0.035 * j2, w0=0.46 * (1.0 + 0.10 * j), t0=0.14,
            K=9, lift=0.5, rise=0.6, taper=2.0)))
    # Nape: short pieces filling the corners between the jaw layer and mullet.
    for i, th in enumerate([128.0, 232.0]):
        side = np.sign(th - 180.0)
        specs.append((f"Nape{i}", "under", dict(
            root=(0.70, th + 6 * side), tip=(1.53 - 0.04 * i, th - 4 * side - 3.0 * i),
            o_mid=0.06, o_tip=0.16, w0=0.40, t0=0.12, K=9, lift=0.5, taper=2.2)))
    # Mullet: long pieces down the nape, tips flicking out.
    for i, th in enumerate([147.0, 169.0, 191.0, 213.0]):
        a = th - 180.0
        j, j2 = J_MULLET[i], J_MULLET2[i]
        specs.append((f"Mullet{i}", "mullet", dict(
            root=(0.62, th), tip=(1.98 - 0.16 * abs(a) / 33.0 + 0.08 * j,
                                  180.0 + 0.8 * a + 4.0 * j2),
            o_mid=0.08, o_tip=0.25 + 0.04 * j2, w0=0.40 * (1.0 + 0.08 * j), t0=0.13,
            K=10, lift=0.6, taper=2.2)))
    # Curtain bangs: roots spaced along the centre part, sweeping outward.
    for sd, tag in ((-1.0, "L"), (1.0, "R")):
        for j, (root, ctrl, tip, o_mid, o_tip, w0) in enumerate([
                ((0.40, 2.0), (0.70, 10.0), (0.95, 30.0), 0.075, 0.10, 0.36),
                ((0.26, 3.0), (0.72, 14.0), (1.02, 42.0), 0.090, 0.13, 0.34),
                ((0.12, 4.0), (0.70, 26.0), (1.32, 58.0), 0.120, 0.17, 0.34)]):
            specs.append((f"Bang{tag}{j}", "bang", dict(
                root=(root[0], sd * root[1]), ctrl=(ctrl[0], sd * ctrl[1]),
                tip=(tip[0], sd * tip[1]), o_root=-0.02, o_mid=o_mid, o_tip=o_tip,
                w0=w0, t0=0.11, K=9, lift=0.55, root_w=0.8,
                curl=(0.36, 0.26, 0.16)[j])))      # upper bangs: flatter edges
        # thin wispy face-framing strand lying over the curtain
        specs.append((f"Wisp{tag}", "bang", dict(
            root=(0.30, sd * 8.0), ctrl=(0.80, sd * 22.0), tip=(1.24, sd * 46.0),
            o_root=-0.02, o_mid=0.125, o_tip=0.15, w0=0.17, t0=0.06, K=8, lift=0.55,
            root_w=0.8, taper=2.2, curl=0.14)))
    return specs


# ---------------------------------------------------------------------------
# UV packing (shelf packer, area roughly proportional to visible surface)
# ---------------------------------------------------------------------------

GAP = 0.007


def _shelf(sizes, scale):
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    x = y = row_h = 0.0
    out = [None] * len(sizes)
    for i in order:
        w, h = sizes[i][0] * scale, sizes[i][1] * scale
        if x + w + 2 * GAP > 1.0:              # keep a gap on the right border too
            x = 0.0
            y += row_h + GAP
            row_h = 0.0
        out[i] = (x + GAP, y + GAP, x + GAP + w, y + GAP + h)
        x += w + GAP
        row_h = max(row_h, h)
    return out, y + row_h + GAP


def pack_islands(shells):
    sizes = []
    for s in shells:
        wgt = np.sqrt(s.meta.get("weight", 1.0))
        sizes.append((s.meta["circ"] * wgt, s.meta["len"] * wgt))
    lo, hi = 0.01, 2.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        _, top = _shelf(sizes, mid)
        if top <= 1.0:
            lo = mid
        else:
            hi = mid
    rects, _ = _shelf(sizes, lo)
    for s, r in zip(shells, rects):
        s.island = tuple(float(np.clip(c, 0.0, 1.0)) for c in r)


def build_shells():
    shells = [build_cap()]
    for i, (name, layer, kw) in enumerate(clump_specs()):
        shells.append(build_clump(name, i + 1, layer, **kw))
    pack_islands(shells)
    return shells


# ---------------------------------------------------------------------------
# Paint
# ---------------------------------------------------------------------------

def paint(ctx, C):
    """Base colour, darker inner layers/undersides/edges, top halo, dyed tips."""
    P, part, a0, a1 = ctx["P"], ctx["part"], ctx["a0"], ctx["a1"]
    shells = ctx["shells"]
    n = len(P)
    layer_of = np.zeros(max(s.part for s in shells) + 1, int)
    phase = np.zeros(len(layer_of))
    side_of = np.zeros(len(layer_of))
    for s in shells:
        layer_of[s.part] = LAYER_IDS[s.meta["layer"]]
        phase[s.part] = np.pi / s.meta.get("M", 1e9)
        side_of[s.part] = 1.0 if s.meta.get("tip", np.zeros(3))[0] > 0 else 0.0
    L = layer_of[part]
    cap = L == 0
    clump = ~cap
    phi = TAU * a0 + phase[part]
    cphi, sphi = np.cos(phi) / np.cos(phase[part]), np.sin(phi)
    u = np.where(clump, a1, 0.0)

    # dyed tips (split: left = tip_l, right = tip_r). The side is chosen per
    # clump (from its tip), so a strand is never cut in two colours. The tip
    # colour keeps the same shading ratios as the base colour.
    right = np.where(clump, side_of[part], _ss(-0.03, 0.03, P[:, 0]))
    tipcol = mix(np.repeat(C["tip_l"][None], n, axis=0), C["tip_r"][None], right)
    tip = (_ss(0.60, 0.86, u) * clump)
    base_c = np.maximum(C["base"], 1e-4)
    base = mix(np.repeat(C["base"][None], n, axis=0), tipcol, tip)
    dark = mix(np.repeat(C["dark"][None], n, axis=0), tipcol * (C["dark"] / base_c), tip)
    edge_c = mix(np.repeat(C["edge"][None], n, axis=0), tipcol * (C["edge"] / base_c), tip)

    # deeper layers read a touch darker
    depth = np.array([0.55, 0.0, 0.22, 0.12, 0.0])[L]
    col = mix(base, dark, depth)
    # underside of each clump
    under = _ss(0.15, -0.6, sphi) * clump
    col = mix(col, dark, 0.65 * under)
    # soft darker clump edges
    edge = _ss(0.72, 0.985, np.abs(cphi)) * clump
    col = mix(col, edge_c, 0.75 * edge)
    # roots melt into the scalp colour
    root = (1.0 - _ss(0.02, 0.30, u)) * clump
    col = mix(col, dark, 0.40 * root)

    # halo highlight band on the top / bangs (lens per clump, crisp-soft
    # edge). It fades out toward the back so it never reads as a headband,
    # and is gentler on the light colourways.
    top_face = _ss(0.05, 0.6, sphi) * np.isin(L, [1, 4])
    hw = 0.045 * (1.0 - np.abs(cphi) ** 1.5) + 0.004
    yc = -0.15 - 0.03 * np.cos(np.arctan2(P[:, 0], -P[:, 2]))
    halo = _aa(np.abs(P[:, 1] - yc) - hw, 0.012) * top_face * _ss(0.45, -0.15, P[:, 2])
    lum = float(np.mean(C["base"]))
    col = mix(col, C["light"][None], (0.55 - 0.17 * _ss(0.3, 0.6, lum)) * halo)

    shade = mix(np.repeat(C["shade"][None], n, axis=0), tipcol * (C["shade"] / base_c), tip)
    return col, shade
