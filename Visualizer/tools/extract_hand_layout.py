#!/usr/bin/env python3
"""
Extract the hand outline and taxel shapes from the hand DXF into hand_layout.json,
so hand_heatmap.py does not need ezdxf at runtime.

  pip install ezdxf
  python Visualizer/tools/extract_hand_layout.py hand_outer_shape_closed_footprint_v3.dxf

Layers used:
  0          hand outline
  FOOTPRINT  taxel shapes (22 shapes; F2+F3 and F0+F14 are wired as one taxel -> 20 taxels)

Shape ids "F<n>" are the order of the entities in the DXF.  The taxel -> channel
mapping (which S0..S23 each taxel is) lives in hand_layout.json and is NOT read
from the DXF; edit "channel" there.
"""

import json
import os
import sys

import ezdxf
from ezdxf import path as ezpath

FLATTEN_TOL = 0.2  # mm

# Taxels: (name, [shape ids]).  Default channel = list index (PROVISIONAL).
TAXELS = [
    ("thumb_tip",     ["F13"]),
    ("thumb_mid",     ["F12"]),
    ("thumb_base",    ["F11"]),
    ("index_tip",     ["F10"]),
    ("index_mid",     ["F9"]),
    ("index_base",    ["F8"]),
    ("middle_tip",    ["F5"]),
    ("middle_mid",    ["F6"]),
    ("middle_base",   ["F7"]),
    ("ring_tip",      ["F4"]),
    ("ring_mid_base", ["F3", "F2"]),
    ("little_tip",    ["F1"]),
    ("little_mid_base", ["F0", "F14"]),
    ("palm_upper",    ["F17"]),
    ("palm_thumb_side", ["F16"]),
    ("palm_little_side", ["F15"]),
    ("side_upper",    ["F20"]),
    ("side_lower",    ["F19"]),
    ("back_main",     ["F18"]),
    ("back_edge",     ["F21"]),
]


def points(entity):
    pts = [(round(v.x, 2), round(v.y, 2)) for v in ezpath.make_path(entity).flattening(FLATTEN_TOL)]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    msp = ezdxf.readfile(sys.argv[1]).modelspace()

    outline, shapes = [], {}
    for e in msp:
        if e.dxftype() != "LWPOLYLINE":
            continue
        if e.dxf.layer == "0":
            outline.append(points(e))
        elif e.dxf.layer == "FOOTPRINT":
            shapes[f"F{len(shapes)}"] = points(e)

    used = [s for _, ids in TAXELS for s in ids]
    missing = set(used) - set(shapes)
    if missing:
        sys.exit(f"shapes not found in DXF: {sorted(missing)}")

    layout = {
        "source": os.path.basename(sys.argv[1]),
        "units": "mm",
        "mapping_note": "channel = index into the 24 sensor values (S0..S23). PROVISIONAL: not yet checked against the hardware.",
        "outline": outline,
        "taxels": [{"name": n, "channel": i, "shapes": ids, "polygons": [shapes[s] for s in ids]}
                   for i, (n, ids) in enumerate(TAXELS)],
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hand_layout.json")
    with open(out, "w") as f:
        json.dump(layout, f, separators=(",", ":"))
    print(f"wrote {os.path.normpath(out)}: {len(layout['taxels'])} taxels, {len(outline)} outline polylines")


if __name__ == "__main__":
    main()
