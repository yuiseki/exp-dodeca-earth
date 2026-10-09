"""Overlay a pentagon plate version and the 1.28" round LCD module in the
XY plane, using data parsed out of the STEP files.

    python3 overlay.py v0.0.2      # writes v0.0.2/overlay.png

The two STEP files do not share a frame: the plate is drawn with the
display rotated -90 deg (clockwise) about Z, so the display geometry is
mapped into the plate frame with (x, y) -> (y, -x) before overlaying.
Only with -90 deg do the holes AND the connector both land in place;
the hole pattern alone is symmetric and also matches at +90 deg.
"""
import math
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

from parse_step import parse_entities, get_circles
from trace_face import face_bounds, trace_loop

DISPLAY_STEP = (
    "../3d/display/1.28inch_LCD_Module_3D_Drawing/"
    "1.28inch LCD Module 3D Drawing/0508.stp"
)

# Loops of the display's back PCB face (0508.stp, face 806): 763 is the
# PCB outline (round, with the flat bottom edge at +X), 781 is the
# footprint of the 8-pin connector housing that stands 5.6mm proud of
# the board (its top is face 836 at z=6.05).
DISPLAY_OUTER_FACE = 763
DISPLAY_CONNECTOR_FACE = 781


def display_to_plate(x, y):
    return (y, -x)


def bbox(points):
    xs, ys = zip(*points)
    return min(xs), max(xs), min(ys), max(ys)


def plate_outline_and_slots(ents):
    """The plate's cap face has the most loops: the outline, 4 holes and
    the slot. The outline is the widest loop; anything else wider than
    a hole is a slot."""
    faces = [e for e, (t, _) in ents.items() if t == "ADVANCED_FACE"]
    cap = max(faces, key=lambda f: len(face_bounds(ents, f)))
    loops = [[(p[0], p[1]) for p in trace_loop(ents, b)] for b in face_bounds(ents, cap)]
    width = lambda loop: bbox(loop)[1] - bbox(loop)[0]
    outline = max(loops, key=width)
    slots = [loop for loop in loops if loop is not outline and width(loop) > 5]
    return outline, slots


def closed(points):
    return list(points) + [points[0]]


def main():
    version = sys.argv[1]
    plate_step = f"../3d/pentagon/{version}/lcd_pentagon_plate.step"

    disp_ents = parse_entities(DISPLAY_STEP)
    disp_circles = get_circles(disp_ents)
    disp_holes = sorted(
        {
            display_to_plate(round(c["center"][0], 3), round(c["center"][1], 3))
            for c in disp_circles
            if round(c["radius"], 2) == 1.75
        }
    )
    active_r = max(c["radius"] for c in disp_circles if round(c["radius"], 2) == 16.2)
    disp_outline = [display_to_plate(p[0], p[1]) for p in trace_loop(disp_ents, DISPLAY_OUTER_FACE)]
    connector = [display_to_plate(p[0], p[1]) for p in trace_loop(disp_ents, DISPLAY_CONNECTOR_FACE)]

    pent_ents = parse_entities(plate_step)
    pent_holes = sorted(
        {(round(c["center"][0], 3), round(c["center"][1], 3)) for c in get_circles(pent_ents) if round(c["radius"], 2) == 1.9}
    )
    outline, slots = plate_outline_and_slots(pent_ents)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(*zip(*closed(outline)), "k-", lw=1.5, label="pentagon plate outline")
    for i, slot in enumerate(slots):
        ax.fill(*zip(*slot), color="tab:green", alpha=0.25)
        ax.plot(*zip(*closed(slot)), color="tab:green", lw=1.3, label="pentagon connector slot" if i == 0 else None)
    for hx, hy in pent_holes:
        ax.add_patch(plt.Circle((hx, hy), 1.9, fill=False, color="tab:orange", lw=1.5))
    ax.plot([], [], color="tab:orange", label="pentagon holes (d=3.8mm)")

    theta = np.linspace(0, 2 * math.pi, 200)
    ax.plot(active_r * np.cos(theta), active_r * np.sin(theta), "b:", lw=1, label="LCD active area (d=32.4mm)")
    ax.plot(*zip(*closed(disp_outline)), "b--", lw=1, label="LCD PCB outline")
    ax.fill(*zip(*connector), color="tab:red", alpha=0.25)
    ax.plot(*zip(*closed(connector)), color="tab:red", lw=1.3, label="LCD connector housing")
    for hx, hy in disp_holes:
        ax.add_patch(plt.Circle((hx, hy), 1.75, fill=False, color="tab:blue", lw=1.5))
    ax.plot([], [], color="tab:blue", label="LCD holes (d=3.5mm)")

    ax.set_title(version)
    ax.set_aspect("equal")
    ax.set_xlim(-30, 30)
    ax.set_ylim(-30, 30)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", fontsize=7)
    fig.suptitle("pentagon plate vs 1.28in LCD\n(display rotated -90 deg into plate frame)")
    fig.tight_layout()
    os.makedirs(version, exist_ok=True)
    out = f"{version}/overlay.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")

    print("pentagon holes:", pent_holes)
    print("display holes: ", disp_holes)
    cx0, cx1, cy0, cy1 = bbox(connector)
    for slot in slots:
        sx0, sx1, sy0, sy1 = bbox(slot)
        print(
            f"slot x {sx0:.2f}..{sx1:.2f} y {sy0:.2f}..{sy1:.2f}; clearance to connector "
            f"left {cx0 - sx0:.2f} right {sx1 - cx1:.2f} center-side {cy0 - sy0:.2f} apex-side {sy1 - cy1:.2f} mm"
        )


if __name__ == "__main__":
    main()
