"""Neko Bucket Hat: cat-ear bucket hat with a coquette bow and a pearl.

Item module for tools/build_ugc.py (see tools/items/README.md for the
contract). Units are studs, Roblox axes (+Y up, avatar faces -Z), origin =
HatAttachment (top centre of a 1.2-stud R15 head).
"""

from __future__ import annotations

import numpy as np

from ugclib.bake import aa as _aa
from ugclib.bake import mix
from ugclib.geometry import TAU, loft, make_shell
from ugclib.geometry import dense_arclength as _dense_arclength
from ugclib.geometry import fillet_polyline as _fillet_polyline
from ugclib.geometry import rot as _rot
from ugclib.geometry import smoothstep as _smoothstep

NAME = "NekoBucketHat"
SLUG = "neko-bucket-hat"
ASSET_TYPE = "Hat"
ATTACHMENT = "HatAttachment"
AFT_BODY_SCALE = "Classic"
AO_RADIUS = 0.17
# Preview cameras, relative to the attachment point (studs).
PREVIEW = {
    "front": dict(cam="1.95,0.8,-2.95", target="0,-0.08,0"),
    "dos": dict(cam="-1.6,1.3,2.7", target="0,-0.08,0"),
    "profil": dict(cam="-3.4,0.35,-0.6", target="0,-0.08,0"),
}

# Marketplace texts and import notes (used by tools/write_guides.py).
LISTING = dict(
    title_fr="Bob Oreilles de Chat Kawaii + Nœud",
    title_en="Kawaii Cat Ear Bucket Hat w/ Bow",
    description_fr=("Un bob trop mignon avec oreilles de chat, nœud coquette à perle et petite "
                    "patte. Style plastique simple et propre. Existe en 5 couleurs : Rose, "
                    "Matcha, Minuit, Nuage et Choco !"),
    description_en=("A cute bucket hat with cat ears, a coquette bow with a pearl and a little "
                    "paw print. Clean, simple plastic style. Available in 5 colors: Pink, "
                    "Matcha, Midnight, Cloud and Cocoa!"),
    colour_en={"Fraise": "Pink", "Matcha": "Matcha", "Minuit": "Midnight", "Nuage": "Cloud",
               "Choco": "Cocoa"},
    placement_fr=("Le bob se pose bien droit sur la tête, le bord juste au-dessus des yeux ; "
                  "la patte est devant et le nœud sur le côté avant droit."),
)

# Part ids, used by paint().
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



# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

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


def build_shells():
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



# ---------------------------------------------------------------------------
# Paint
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


def paint(ctx, C):
    """Colour zones: body, inner ears, paw print, lining, satin ribbon, pearl."""
    P, part, a0, a1 = ctx["P"], ctx["part"], ctx["a0"], ctx["a1"]
    shells = ctx["shells"]
    n = len(P)
    marks = shells[0].meta["marks"]
    crown = part == PART_CROWN
    t = a1
    r_xz = np.hypot(P[:, 0], P[:, 2])
    theta = np.arctan2(P[:, 2], P[:, 0])

    def region(name):
        lo, hi = marks[name]
        return crown & (t >= lo) & (t <= hi)

    band = region("band")
    lining = region("brim_under") | region("inner")
    ears = (part == PART_EAR_L) | (part == PART_EAR_R)
    ribbon = band | np.isin(part, [PART_KNOT, PART_LOOP_L, PART_LOOP_R,
                                   PART_TAIL_L, PART_TAIL_R])
    pearl = part == PART_PEARL
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
    return col, shade_tint
