"""Roblox rigid-accessory size rules, per asset type and body scale.

Source: https://create.roblox.com/docs/avatar/rigid-accessories/specifications
Each box is ((xmin, xmax), (ymin, ymax), (zmin, zmax)) in studs, in the
attachment's space (-Z = the avatar's front, +Z = behind). Boxes the docs
mark as "not centered" are encoded with their exact up/down/front/behind
extents.
"""

from __future__ import annotations

import numpy as np


def centred(w, h, d):
    return ((-w / 2, w / 2), (-h / 2, h / 2), (-d / 2, d / 2))


LIMITS = {
    "Hat": {"Normal": centred(1.87, 2.5, 1.87), "Slender": centred(1.78, 2.5, 1.78),
            "Classic": centred(3, 4, 3)},
    "Hair": {"Normal": ((-0.935, 0.935), (-1.875, 1.25), (-0.9375, 1.25)),
             # docs print "1.892 front" for a 2.08 total; 0.892 is the consistent value
             "Slender": ((-0.89, 0.89), (-1.875, 1.25), (-0.892, 1.189)),
             "Classic": ((-1.5, 1.5), (-3.0, 2.0), (-1.5, 2.0))},
    "Face": {"Normal": centred(1.87, 1.25, 1.25), "Slender": centred(1.78, 1.25, 1.18),
             "Classic": centred(3, 2, 2)},
    "Neck": {"Normal": centred(2.95, 3.68, 2.16), "Slender": centred(2.59, 3.39, 1.92),
             "Classic": centred(3, 3, 2)},
    "ShoulderNeck": {"Normal": centred(6.90, 3.68, 3.24), "Slender": centred(6.05, 3.39, 2.88),
                     "Classic": centred(7, 3, 3)},
    "ShoulderCollar": {"Normal": centred(2.95, 3.68, 3.24), "Slender": centred(2.59, 3.39, 2.88),
                       "Classic": centred(3, 3, 3)},
    "ShoulderArm": {"Normal": centred(2.67, 4.40, 3.09), "Slender": centred(2.37, 3.96, 2.75),
                    "Classic": centred(3, 3, 3)},
    "Front": {"Normal": centred(2.95, 3.68, 3.24), "Slender": centred(2.59, 3.39, 2.88),
              "Classic": centred(3, 3, 3)},
    "Back": {"Normal": ((-4.93, 4.93), (-4.295, 4.295), (-1.623, 3.246)),
             "Slender": ((-4.32, 4.32), (-3.955, 3.955), (-1.443, 2.886)),
             "Classic": ((-5.0, 5.0), (-3.5, 3.5), (-1.5, 3.0))},
    "Waist": {"Normal": ((-1.97, 1.97), (-2.457, 1.842), (-3.785, 3.785)),
              "Slender": ((-1.88, 1.88), (-1.885, 1.414), (-3.365, 3.365)),
              "Classic": ((-2.0, 2.0), (-2.0, 1.5), (-3.5, 3.5))},
}

# Asset type -> (Roblox AccessoryType for "Save to Roblox", attachment names)
ATTACHMENTS = {
    "Hat": ("Hat", ["HatAttachment"]),
    "Hair": ("Hair", ["HairAttachment"]),
    "Face": ("Face", ["FaceFrontAttachment", "FaceCenterAttachment"]),
    "Neck": ("Neck", ["NeckAttachment"]),
    "ShoulderNeck": ("Shoulder", ["NeckAttachment"]),
    "ShoulderCollar": ("Shoulder", ["RightCollarAttachment", "LeftCollarAttachment"]),
    "ShoulderArm": ("Shoulder", ["RightShoulderAttachment", "LeftShoulderAttachment"]),
    "Front": ("Front", ["BodyFrontAttachment"]),
    "Back": ("Back", ["BodyBackAttachment"]),
    "Waist": ("Waist", ["WaistFrontAttachment", "WaistCenterAttachment", "WaistBackAttachment"]),
}

MAX_TRIANGLES = 4000
MAX_TEXTURE = 1024


def fit_report(V, asset_type):
    """{scale: (ok, needed_extents_text)} for a mesh whose origin is the attachment."""
    lo, hi = np.asarray(V).min(0), np.asarray(V).max(0)
    out = {}
    for scale, box in LIMITS[asset_type].items():
        ok = all(box[i][0] - 1e-9 <= lo[i] and hi[i] <= box[i][1] + 1e-9 for i in range(3))
        need = " ".join(f"{a}[{lo[i]:+.3f},{hi[i]:+.3f}]⊂[{box[i][0]:+.3f},{box[i][1]:+.3f}]"
                        for i, a in enumerate("XYZ"))
        out[scale] = (ok, need)
    return out
