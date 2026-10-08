# Item modules (`tools/items/*.py`)

Each UGC item is one Python module here. The shared pipeline turns it into
Studio-ready files under `ugc/<SLUG>/`.

```bash
python3 tools/build_ugc.py <module>                 # OBJ + textures + build/specs.json
python3 tools/build_ugc.py <module> --no-textures   # geometry only (fast iteration)
python3 tools/render_previews.py <slug> --quick --out /tmp/x   # one quick render
<python-with-bpy> tools/blender_export.py <slug>    # one FBX per colourway (+ round-trip check)
python3 tools/validate_ugc.py <slug>                # Roblox rules, must print all PASS
python3 tools/render_previews.py <slug>             # final previews in ugc/<slug>/previews/
```

`<python-with-bpy>` is any Python with Blender's `bpy` module (`pip install bpy`).

## Module contract

```python
NAME = "NekoBucketHat"          # CamelCase, used for files and the Studio object
SLUG = "neko-bucket-hat"        # folder name in ugc/
ASSET_TYPE = "Hat"              # key of ugclib.specs.LIMITS: Hat, Hair, Face, Neck,
                                # ShoulderNeck, ShoulderCollar, ShoulderArm, Front, Back, Waist
ATTACHMENT = "HatAttachment"    # must be one of ugclib.specs.ATTACHMENTS[ASSET_TYPE][1]
AFT_BODY_SCALE = "Classic"      # body type to pick in the Accessory Fitting Tool
AO_RADIUS = 0.17                # studs; ~0.17 for head items, 0.3-0.4 for big items
AO_STRENGTH = 0.75              # optional, 0..1: how dark baked occlusion gets
PREVIEW = {                     # cameras RELATIVE to the attachment point
    "front": dict(cam="1.95,0.8,-2.95", target="0,-0.08,0"),
    "dos": dict(cam="-1.6,1.3,2.7", target="0,-0.08,0"),
}
COLORWAYS = {"Fraise": dict(body=(255, 176, 202), shade=(214, 98, 140), ...), ...}

def build_shells() -> list[Shell]: ...   # geometry, origin = the attachment point
def paint(ctx, C) -> (colour, shade): ...  # see ugclib/bake.py docstring
```

## Conventions

- **Units are studs, axes are Roblox's**: +Y up, the avatar looks toward **-Z**,
  +X is the avatar's **right**. The mesh origin is the attachment point.
- Reference body (classic R15 block rig, used by the previewer), world coords:
  head = rounded cylinder, radius 0.6, height 1.2, centre (0, 1.3, 0);
  UpperTorso 2 x 1.6 x 1 centred at (0, 0, 0); arms 1 x 2 x 1 at x = ±1.5.
  Attachments: Hat/Hair (0, 1.9, 0) = head top, FaceFront (0, 1.3, -0.6),
  Neck (0, 0.8, 0), BodyFront (0, 0, -0.5), BodyBack (0, 0, 0.5),
  RightCollar (1, 0.8, 0), LeftCollar (-1, 0.8, 0). Eyes are at head-centre
  height, x = ±0.2, on the face plane z = -0.6.
- **Roblox rules** (checked by `validate_ugc.py`): ≤ 4000 triangles, one mesh,
  one material, every shell closed and outward (use the `ugclib.geometry`
  primitives: they are watertight by construction), quads/tris only, UVs in
  0..1, UV islands of different shells never overlap, size inside the asset type's box (`ugclib/specs.py`) for Classic and
  for `AFT_BODY_SCALE`.
- **UV islands**: give every shell its own `island=(u0, v0, u1, v1)` rectangle;
  islands must not overlap and should keep ~0.006 gaps. Make island area
  roughly proportional to the visible surface area.
- **Style**: clean "simple plastic" — flat colour zones with soft edges, baked
  ambient occlusion and a gentle top light (both added by the baker). No fur,
  no noise, no photo textures. Cute, readable silhouettes. 4-5 colourways.

## Geometry toolkit (`ugclib.geometry`)

| helper | use |
|---|---|
| `revolve(name, part, profile, island, segments=32)` | anything round around a vertical axis (caps, buns, crowns). Profile = (r, y) points from pole to pole. |
| `ellipsoid(name, part, centre, radii, island, axes=None, exponent=1.0)` | blobs, eyes, pearls, knots; `exponent≈0.6` = rounded cube. |
| `sweep(name, part, path, section, island, closed=False)` | tubes along a path: hair clumps (tapered sections), frames, straps, tails. `closed=True` for rings. |
| `slab(name, part, outline2d, thickness, island, origin, x_axis, y_axis)` | thick rounded flat shapes: wings, lenses, ear flaps, patches. Outline must be star-shaped around its centroid. |
| `loft(...)` + `make_shell(...)` | low level: any ring sequence closed by apexes. |
| `rot(axis, angle)`, `fillet_polyline`, `smoothstep`, `parallel_transport_frames` | utilities. |

Each primitive returns a `Shell`; shells may intersect each other (that is
normal for UGC) but each must be closed on its own. `shell.part` is an int you
choose, read back in `paint()` as `ctx["part"]`.
