"""Overlay the pentagon mounting plate and the 1.28" round LCD module in
the XY plane, using only data parsed out of the STEP files (no
FreeCAD/OpenCASCADE available in this environment).

The two STEP files do not share a frame: the plate is drawn with the
display rotated -90 deg (clockwise) about Z, so the display geometry is
mapped into the plate frame with (x, y) -> (y, -x) before overlaying.
Only with -90 deg do the holes AND the connector both land in place;
the hole pattern alone is symmetric and also matches at +90 deg.
"""
import math
import numpy as np
import matplotlib.pyplot as plt

from parse_step import parse_entities, get_circles
from trace_face import trace_loop

PENTAGON_STEPS = {
    "v0.0.1": "../3d/pentagon/v0.0.1/lcd_pentagon_plate.step",
}
DISPLAY_STEP = (
    "../3d/display/1.28inch_LCD_Module_3D_Drawing/"
    "1.28inch LCD Module 3D Drawing/0508.stp"
)

# Pentagon outline, read off the outer 5 vertices (radius > 20mm from
# center) found among the STEP's VERTEX_POINTs. Order them by angle so
# they plot as a proper closed polygon.
PENTAGON_OUTLINE = [
    (-24.271, 6.256),
    (-15.0, -22.276),
    (0.0, 23.89),
    (15.0, -22.276),
    (24.271, 6.256),
]

# Rectangular through-slot cut into the pentagon plate (traced via its
# EDGE_CURVE connectivity).
PENTAGON_SLOT = [(-10.3, 3.5), (-10.3, 11.5), (10.3, 11.5), (10.3, 3.5)]

# Loops of the display's back PCB face (0508.stp, face 806): 763 is the
# PCB outline (round, with the flat bottom edge at +X), 781 is the
# footprint of the 8-pin connector housing that stands 5.6mm proud of
# the board (its top is face 836 at z=6.05).
DISPLAY_OUTER_FACE = 763


def display_to_plate(x, y):
    return (y, -x)
DISPLAY_CONNECTOR_SLOT_FACE = 781


def order_ccw(points):
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def main():
    disp_ents = parse_entities(DISPLAY_STEP)
    disp_circles = get_circles(disp_ents)
    disp_holes = sorted(
        {
            display_to_plate(round(c["center"][0], 3), round(c["center"][1], 3))
            for c in disp_circles
            if round(c["radius"], 2) == 1.75
        }
    )
    pcb_r = max(c["radius"] for c in disp_circles if round(c["radius"], 2) == 18.75)
    active_r = max(c["radius"] for c in disp_circles if round(c["radius"], 2) == 16.2)

    disp_outline = [display_to_plate(p[0], p[1]) for p in trace_loop(disp_ents, DISPLAY_OUTER_FACE)]
    disp_outline_closed = disp_outline + [disp_outline[0]]
    disp_slot = [display_to_plate(p[0], p[1]) for p in trace_loop(disp_ents, DISPLAY_CONNECTOR_SLOT_FACE)]
    disp_slot_closed = disp_slot + [disp_slot[0]]

    outline = order_ccw(PENTAGON_OUTLINE)
    outline_closed = outline + [outline[0]]
    pent_slot_closed = PENTAGON_SLOT + [PENTAGON_SLOT[0]]

    fig, axes = plt.subplots(1, len(PENTAGON_STEPS), figsize=(6, 6), squeeze=False)
    axes = axes[0]

    for ax, (title, step_path) in zip(axes, PENTAGON_STEPS.items()):
        pent_ents = parse_entities(step_path)
        pent_circles = [c for c in get_circles(pent_ents) if round(c["radius"], 2) == 1.9]
        pent_holes = sorted({(round(c["center"][0], 3), round(c["center"][1], 3)) for c in pent_circles})

        xs, ys = zip(*outline_closed)
        ax.plot(xs, ys, "k-", lw=1.5, label="pentagon plate outline")

        xs, ys = zip(*pent_slot_closed)
        ax.fill(xs, ys, color="tab:green", alpha=0.25)
        ax.plot(xs, ys, color="tab:green", lw=1.3, label="pentagon connector slot")

        for hx, hy in pent_holes:
            ax.add_patch(plt.Circle((hx, hy), 1.9, fill=False, color="tab:orange", lw=1.5))
        ax.plot([], [], color="tab:orange", label="pentagon holes (d=3.8mm)")

        theta = np.linspace(0, 2 * math.pi, 200)
        ax.plot(active_r * np.cos(theta), active_r * np.sin(theta), "b:", lw=1, label="LCD active area (d=32.4mm)")

        xs, ys = zip(*disp_outline_closed)
        ax.plot(xs, ys, "b--", lw=1, label="LCD PCB outline")

        xs, ys = zip(*disp_slot_closed)
        ax.fill(xs, ys, color="tab:red", alpha=0.25)
        ax.plot(xs, ys, color="tab:red", lw=1.3, label="LCD connector housing")

        for hx, hy in disp_holes:
            ax.add_patch(plt.Circle((hx, hy), 1.75, fill=False, color="tab:blue", lw=1.5))
        ax.plot([], [], color="tab:blue", label="LCD holes (d=3.5mm)")

        ax.set_title(title)
        ax.set_aspect("equal")
        ax.set_xlim(-30, 30)
        ax.set_ylim(-30, 30)
        ax.grid(alpha=0.3)

        print(f"\n{title}")
        print("  pentagon holes:", pent_holes)

    axes[0].legend(loc="lower left", fontsize=7)
    fig.suptitle("pentagon plate vs 1.28in LCD\n(display rotated -90 deg into plate frame)")
    fig.tight_layout()
    out = "v0.0.1/overlay.png"
    fig.savefig(out, dpi=150)
    print(f"\nwrote {out}")

    print("\ndisplay holes (x, y):", disp_holes)
    print(f"LCD PCB diameter: {pcb_r * 2:.1f} mm, active area diameter: {active_r * 2:.1f} mm")


if __name__ == "__main__":
    main()
