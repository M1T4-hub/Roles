"""Froggy Shoulder Pal: a chubby kawaii frog plush riding on the right shoulder.

Item module for tools/build_ugc.py (see tools/items/README.md for the
contract). Units are studs, Roblox axes (+Y up, avatar faces -Z), origin =
RightCollarAttachment (world (1, 0.8, 0) on the R15 block rig): the shoulder /
upper-arm top is at y = 0, the right arm spans local x 0..1 and the torso
x <= 0.

Build: one squashed mochi body (head and body in one blob), two eye bumps on
top (white eyeballs, dark pupils and highlights are painted), tucked back
legs, little three-toed feet, and a mini strawberry beret between the eyes.
Face, belly, blush and back spots are painted colour zones (simple plastic).
The frog is modelled in its own frame (origin = bottom centre, facing -Z) and
then placed on the shoulder, turned slightly outward.
"""

from __future__ import annotations

import numpy as np

from ugclib.bake import aa as _aa
from ugclib.bake import mix
from ugclib.geometry import TAU, ellipsoid, loft, make_shell, revolve, slab, sweep
from ugclib.geometry import rot as _rot

NAME = "FroggyShoulderPal"
SLUG = "froggy-shoulder-pal"
ASSET_TYPE = "ShoulderCollar"
ATTACHMENT = "RightCollarAttachment"
AFT_BODY_SCALE = "Classic"
AO_RADIUS = 0.2
# Preview cameras, relative to the attachment point (studs).
PREVIEW = {
    "face": dict(cam="1.3,1.0,-2.3", target="0.15,0.4,0", fov=34),
    "profil": dict(cam="3.0,0.75,-1.3", target="0.45,0.22,0"),
    "dessus": dict(cam="1.4,2.5,1.8", target="0.4,0.18,0"),
    "buste": dict(cam="1.5,1.1,-2.6", target="-0.15,0.45,0", fov=38),
}

# Part ids, used by paint().
PART_BODY = 0
PART_EYE_L = 1
PART_EYE_R = 2
PART_HAUNCH_L = 3
PART_HAUNCH_R = 4
PART_FOOT_FL = 5
PART_FOOT_FR = 6
PART_FOOT_BL = 7
PART_FOOT_BR = 8
PART_HAT = 9
PART_CALYX = 10
PART_STEM = 11

# Placement of the frog frame on the shoulder: turned ~12 deg outward (+X).
YAW = np.radians(-12.0)
R_FROG = _rot((0, 1, 0), YAW)
T_FROG = np.array([0.44, 0.0, 0.0])

COLORWAYS = {
    # Classic leaf green, pale lime belly
    "Vert": dict(
        body=(134, 208, 100), shade=(48, 118, 58), belly=(244, 255, 208),
        spot=(98, 178, 82), blush=(255, 150, 172), ink=(52, 40, 50),
        white=(255, 255, 255), hat=(242, 72, 92), hat_shade=(150, 26, 52),
        seed=(255, 236, 170), leaf=(64, 156, 74), leaf_shade=(26, 88, 44)),
    # Strawberry-milk pink frog
    "Fraise": dict(
        body=(255, 170, 198), shade=(196, 84, 128), belly=(255, 242, 246),
        spot=(246, 138, 178), blush=(255, 104, 146), ink=(84, 36, 58),
        white=(255, 255, 255), hat=(236, 56, 80), hat_shade=(140, 20, 50),
        seed=(255, 240, 190), leaf=(84, 170, 86), leaf_shade=(34, 98, 52)),
    # Baby blue
    "Bleu": dict(
        body=(138, 196, 252), shade=(56, 104, 186), belly=(240, 248, 255),
        spot=(108, 168, 238), blush=(255, 156, 188), ink=(40, 42, 70),
        white=(255, 255, 255), hat=(242, 72, 96), hat_shade=(150, 26, 60),
        seed=(255, 238, 176), leaf=(70, 162, 80), leaf_shade=(28, 92, 48)),
    # Lemon yellow
    "Citron": dict(
        body=(255, 224, 92), shade=(206, 136, 34), belly=(255, 252, 228),
        spot=(250, 198, 64), blush=(255, 146, 140), ink=(74, 50, 40),
        white=(255, 255, 255), hat=(240, 70, 86), hat_shade=(150, 30, 48),
        seed=(255, 242, 196), leaf=(66, 158, 76), leaf_shade=(28, 90, 46)),
    # Chocolate brown, caramel belly
    "Choco": dict(
        body=(158, 106, 78), shade=(76, 44, 32), belly=(244, 216, 182),
        spot=(132, 86, 62), blush=(244, 140, 140), ink=(46, 28, 24),
        white=(255, 252, 248), hat=(236, 66, 84), hat_shade=(140, 24, 46),
        seed=(255, 236, 180), leaf=(72, 160, 80), leaf_shade=(28, 90, 46)),
}


def _spow(x, e):
    return np.sign(x) * np.abs(x) ** e


def place(V):
    """Frog frame -> attachment frame."""
    return np.asarray(V, float) @ R_FROG.T + T_FROG


def to_frog(P):
    """Attachment frame -> frog frame (inverse of place)."""
    return (np.asarray(P, float) - T_FROG) @ R_FROG


def _placed(shell):
    shell.V = place(shell.V)
    return shell


# ---------------------------------------------------------------------------
# Body: squashed mochi blob, flat bottom, full belly
# ---------------------------------------------------------------------------

BODY_YC = 0.165     # equator height
BODY_RYT = 0.240    # top half height  -> top at ~0.405
BODY_RYB = 0.172    # bottom half height -> bottom at ~-0.007
BODY_RX = 0.305
BODY_RZ = 0.258


def body_point(la, lon):
    """Point on the body for latitude la (-pi/2..pi/2) and longitude lon
    (0 = +X side, pi/2 = back +Z, -pi/2 = front -Z)."""
    la = np.asarray(la, float)
    lon = np.asarray(lon, float)
    e = np.where(la < 0, 0.50, 0.90)
    ry = np.where(la < 0, BODY_RYB, BODY_RYT)
    cy = _spow(np.cos(la), e)
    sy = _spow(np.sin(la), e)
    y = BODY_YC + ry * sy
    # front (belly) a bit fuller than the back, head a bit wider than deep
    front = np.clip(-np.sin(lon), 0, 1)
    rz = BODY_RZ * (1.0 + 0.06 * front * np.exp(-((y - 0.13) / 0.14) ** 2))
    rx = BODY_RX * (1.0 + 0.03 * np.exp(-((y - 0.22) / 0.10) ** 2))
    x = rx * cy * _spow(np.cos(lon), 0.92)
    z = rz * cy * _spow(np.sin(lon), 0.92)
    return np.stack(np.broadcast_arrays(x, y, z), -1)


def build_body(island, M=36):
    lats = np.radians([-88, -82, -74, -62, -46, -26, -8, 10, 26, 40, 52, 62, 71, 79, 85])
    lon = np.pi / 2 + TAU * np.arange(M) / M        # seam at the back
    rings = [body_point(la, lon) for la in lats]
    v = (lats + np.pi / 2) / np.pi
    data = loft(rings, apex0=body_point(-np.pi / 2, 0.0), apex1=body_point(np.pi / 2, 0.0),
                v_rings=0.02 + 0.96 * v, v_apex0=0.0, v_apex1=1.0, attr_v=v)
    return make_shell("Body", PART_BODY, data, island)


# ---------------------------------------------------------------------------
# Eyes, legs, feet
# ---------------------------------------------------------------------------

EYE_R = 0.122
# The eye white covers the eyeball where cos(angle to the look direction) >
# EYE_WRAP; a negative value wraps it over the top and back of the eye bump so
# the frog still reads as a frog (not a bear with ears) from above and behind.
EYE_WRAP = -0.75


def eye_frame(side):
    """side = +1 (frog's left = +X) or -1. Returns centre, right, up, fwd."""
    c = np.array([0.168 * side, 0.348, -0.085])
    f = np.array([0.30 * side, 0.33, -1.0])
    f /= np.linalg.norm(f)
    r = np.cross(np.array([0.0, 1.0, 0.0]), f)
    r = -r / np.linalg.norm(r)        # +X-ish when looking along -Z
    u = np.cross(f, r)
    u = -u if u[1] < 0 else u
    return c, r, u, f


def build_eye(side, island, part, M=24, K=9):
    c, r, u, f = eye_frame(side)
    # pole axis along the look direction: the front outline is a smooth ring
    return ellipsoid(f"Eye{'L' if side > 0 else 'R'}", part, c, (EYE_R, EYE_R * 0.96, EYE_R),
                     island, axes=np.array([r, f, u]), M=M, K=K)


def build_haunch(side, island, part, M=20, K=8):
    c = np.array([0.262 * side, 0.092, 0.075])
    R = _rot((0, 1, 0), np.radians(-14.0) * side) @ _rot((1, 0, 0), np.radians(-10.0))
    return ellipsoid(f"Haunch{'L' if side > 0 else 'R'}", part, c, (0.092, 0.098, 0.150),
                     island, axes=R.T, M=M, K=K)


def build_toes(prefix, part, islands, base, heading, spread=36.0, length=0.041,
               width=0.0215, height=0.0175, M=6, K=5):
    """Three little toe beans fanning out from `base` along `heading`."""
    h = np.asarray(heading, float)
    h = h / np.linalg.norm(h)
    up = np.array([0.0, 1.0, 0.0])
    out = []
    for i, isl in zip((-1, 0, 1), islands):
        d = _rot((0, 1, 0), np.radians(spread) * i) @ h
        d = d * np.cos(0.10) - up * np.sin(0.10)          # tips touch the shoulder
        side = np.cross(up, d)
        side /= np.linalg.norm(side)
        tu = np.cross(d, side)
        tu = tu if tu[1] > 0 else -tu
        ln = length * (1.08 if i == 0 else 1.0)
        c = np.asarray(base, float) + d * ln * 0.80 + up * height * 0.80
        out.append(ellipsoid(f"{prefix}{i + 1}", part, c, (width, ln, height), isl,
                             axes=np.array([side, d, tu]), M=M, K=K))
    return out


# ---------------------------------------------------------------------------
# Mini strawberry beret
# ---------------------------------------------------------------------------

HAT_BASE = np.array([0.0, 0.372, 0.088])
HAT_R = _rot((0, 0, 1), np.radians(-10.0)) @ _rot((1, 0, 0), np.radians(12.0))
HAT_PROFILE = np.array([
    (0.000, 0.000), (0.070, 0.000), (0.098, 0.006), (0.110, 0.022),
    (0.112, 0.042), (0.104, 0.068), (0.086, 0.094), (0.060, 0.114),
    (0.030, 0.126), (0.000, 0.130),
])


def hat_point(local):
    return HAT_BASE + np.asarray(local, float) @ HAT_R.T


def build_hat(island, segments=24):
    s = revolve("StrawberryHat", PART_HAT, HAT_PROFILE, island, segments=segments,
                seam_angle=np.pi / 2)
    s.V = hat_point(s.V)
    return s


def calyx_outline(n=25, leaves=5, r_in=0.030, r_out=0.074):
    a = np.radians(90.0) + TAU * np.arange(n) / n
    lobe = np.cos(leaves * (a - np.radians(90.0)) / 2.0) ** 2
    r = r_in + (r_out - r_in) * lobe ** 1.4
    return np.column_stack((r * np.cos(a), r * np.sin(a)))


def build_calyx(island):
    """Five-leaf green star draped over the top of the strawberry."""
    s = slab("Calyx", PART_CALYX, calyx_outline(), 0.018, island,
             origin=(0.0, 0.0, 0.0), x_axis=(1, 0, 0), y_axis=(0, 0, -1),
             rings_per_side=1, bulge=0.2)
    V = s.V.copy()
    r = np.hypot(V[:, 0], V[:, 2])
    V[:, 1] += 0.126 - 3.3 * r * r + 0.004
    s.V = hat_point(V)
    return s


def build_stem(island):
    t = np.linspace(0, 1, 4)
    path = np.column_stack((0.010 * t, 0.124 + 0.040 * t, 0.006 * t * t))
    M = 6
    phi = TAU * np.arange(M) / M

    def section(k, u):
        rr = 0.0105 * (1.0 - 0.25 * u)
        return np.column_stack((rr * np.cos(phi), rr * np.sin(phi)))
    s = sweep("Stem", PART_STEM, path, section, island, up_hint=(0, 0, 1))
    s.V = hat_point(s.V)
    return s


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_shells():
    g = 0.006
    shells = [
        build_body(island=(0.0, 0.40, 1.0, 1.0)),
        build_eye(+1, (g, 0.135, 0.245, 0.395), PART_EYE_L),
        build_eye(-1, (0.25 + g, 0.135, 0.495, 0.395), PART_EYE_R),
        build_hat((0.50 + g, 0.135, 0.745, 0.395)),
        build_calyx((0.75 + g, 0.215, 0.995, 0.395)),
        build_stem((0.75 + g, 0.135, 0.86, 0.21)),
        build_haunch(+1, (g, g, 0.195, 0.13), PART_HAUNCH_L),
        build_haunch(-1, (0.20 + g, g, 0.395, 0.13), PART_HAUNCH_R),
    ]
    feet = [
        # prefix, part, base (frog frame), heading, toe ellipsoid rings
        ("ToeFL", PART_FOOT_FL, (0.122, 0.0, -0.192), (0.25, 0, -1.0), 5),
        ("ToeFR", PART_FOOT_FR, (-0.122, 0.0, -0.192), (-0.25, 0, -1.0), 5),
        ("ToeBL", PART_FOOT_BL, (0.285, 0.0, -0.025), (0.60, 0, -1.0), 4),
        ("ToeBR", PART_FOOT_BR, (-0.285, 0.0, -0.025), (-0.60, 0, -1.0), 4),
    ]
    u0, w = 0.40, (1.0 - 0.40) / 12
    for i, (prefix, part, base, hd, K) in enumerate(feet):
        isl = [(u0 + (3 * i + j) * w + g, g, u0 + (3 * i + j + 1) * w, 0.13) for j in range(3)]
        shells += build_toes(prefix, part, isl, base, hd, K=K)
    return [_placed(s) for s in shells]


# ---------------------------------------------------------------------------
# Paint
# ---------------------------------------------------------------------------

def _ellipse_d(x, y, cx, cy, rx, ry):
    """Approximate signed distance (studs) to an ellipse."""
    q = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    return (q - 1.0) * min(rx, ry)


def _seed_points(n=26):
    """Seed positions (hat-local) spread on the strawberry sides."""
    pts = []
    ga = np.pi * (3 - np.sqrt(5))
    prof = HAT_PROFILE
    for i in range(n):
        t = (i + 0.5) / n
        y = 0.016 + t * 0.072
        # radius on the profile at that height (profile is monotone on the side)
        side = prof[3:-1]
        r = np.interp(y, side[:, 1], side[:, 0])
        a = i * ga
        pts.append((r * np.cos(a), y, r * np.sin(a)))
    return np.array(pts)


def paint(ctx, C):
    P, part = ctx["P"], ctx["part"]
    n = len(P)
    L = to_frog(P)
    x, y, z = L[:, 0], L[:, 1], L[:, 2]

    body_like = np.isin(part, [PART_BODY, PART_HAUNCH_L, PART_HAUNCH_R,
                               PART_FOOT_FL, PART_FOOT_FR, PART_FOOT_BL, PART_FOOT_BR,
                               PART_EYE_L, PART_EYE_R])
    body = part == PART_BODY
    col = np.zeros((n, 3))
    sh = np.zeros((n, 3))
    col[body_like] = C["body"]
    sh[body_like] = C["shade"]

    # --- belly: pale oval on the lower front --------------------------------
    # kept on the front-facing part of the belly (not the flattened underside,
    # where the top light and AO would turn it grey); soft fade toward the sides
    front = body * _aa(z + 0.05, 0.01)
    d_belly = _ellipse_d(x, y, 0.0, 0.122, 0.188, 0.073)
    belly = front * _aa(d_belly, 0.006)
    col = mix(col, C["belly"][None], belly)
    sh = mix(sh, mix(C["belly"], C["shade"], 0.25)[None], belly)

    # --- back spots ------------------------------------------------------------
    # (latitude, longitude, radius): longitude 90 = middle of the back
    spots = [(28, 90, 0.046), (50, 130, 0.034), (54, 52, 0.037), (-4, 60, 0.028),
             (-2, 117, 0.025)]
    sp = np.zeros(n)
    for la, lo, r in spots:
        c = body_point(np.radians(la), np.radians(lo))
        d = np.linalg.norm(L - c, axis=1) - r
        sp = np.maximum(sp, _aa(d, 0.005))
    col = mix(col, C["spot"][None], sp * body)

    # --- blush ---------------------------------------------------------------------
    for side in (+1, -1):
        nc = np.array([0.55 * side, 0.0, -1.0])
        nc /= np.linalg.norm(nc)
        ex = np.cross(np.array([0.0, 1.0, 0.0]), nc)
        ex /= np.linalg.norm(ex)
        cc = np.array([0.170 * side, 0.202, 0.0])
        bu = (L - cc) @ ex
        bv = y - cc[1]
        facing = (L @ nc) > 0.0
        d = _ellipse_d(bu, bv, 0.0, 0.0, 0.050, 0.030)
        col = mix(col, C["blush"][None], body * facing * _aa(d, 0.007) * 0.95)

    # --- smile -------------------------------------------------------------------
    w, y0, a, half = 0.080, 0.214, 2.6, 0.0100
    xs = np.clip(x, -w, w)
    ym = y0 + a * xs * xs - 0.004
    d_curve = np.abs(y - ym) / np.sqrt(1 + (2 * a * xs) ** 2)
    d_end = np.hypot(x - xs, y - ym)
    d_mouth = np.where(np.abs(x) > w, d_end, d_curve) - half
    mouth = body * (z < -0.12) * _aa(d_mouth, 0.0035)
    col = mix(col, C["ink"][None], mouth)
    sh = mix(sh, C["ink"][None], mouth)

    # --- eyes ----------------------------------------------------------------------
    for side, pid in ((+1, PART_EYE_L), (-1, PART_EYE_R)):
        m = part == pid
        c, r, u, f = eye_frame(side)
        d = (L - c)
        dn = d / np.linalg.norm(d, axis=1, keepdims=True)
        ex, ey = d @ r / EYE_R, d @ u / EYE_R
        cosf = dn @ f
        sclera = _aa((EYE_WRAP - cosf) / 0.6, 0.02)
        # pupil a little inward and down: looking at the viewer
        pc = (-0.10 * side, -0.06)
        d_pup = np.hypot(ex - pc[0], ey - pc[1]) - 0.50
        pupil = (cosf > 0) * _aa(d_pup, 0.025)
        hl1 = (cosf > 0) * _aa(np.hypot(ex - pc[0] - 0.18, ey - pc[1] - 0.20) - 0.16, 0.025)
        hl2 = (cosf > 0) * _aa(np.hypot(ex - pc[0] + 0.17, ey - pc[1] + 0.20) - 0.075, 0.025)
        e_col = mix(np.broadcast_to(C["body"], (n, 3)), C["white"][None], sclera)
        e_col = mix(e_col, C["ink"][None], pupil)
        e_col = mix(e_col, C["white"][None], np.maximum(hl1, hl2))
        e_sh = mix(np.broadcast_to(C["shade"], (n, 3)), C["white"][None] * 0.55, sclera)
        col[m] = e_col[m]
        sh[m] = e_sh[m]

    # --- strawberry beret ------------------------------------------------------------
    hat = part == PART_HAT
    # hat-local coordinates
    HL = (L - HAT_BASE) @ HAT_R
    seeds = _seed_points()
    dmin = np.full(n, 1e9)
    for s in seeds:
        dmin = np.minimum(dmin, np.linalg.norm(HL - s, axis=1))
    seed = hat * _aa(dmin - 0.0085, 0.003)
    col[hat] = C["hat"]
    sh[hat] = C["hat_shade"]
    col = mix(col, C["seed"][None], seed)

    leaf = np.isin(part, [PART_CALYX, PART_STEM])
    col[leaf] = C["leaf"]
    sh[leaf] = C["leaf_shade"]
    return col, sh
