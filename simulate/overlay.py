"""Overlay the pentagon mounting plate (v0.0.1) and the 1.28" round LCD
module in the XY plane, using only data parsed out of the STEP files
(no FreeCAD/OpenCASCADE available in this environment).

Both parts are assumed centered on their own geometric center; this
script does not know the *intended* assembly transform, it just checks
whether the mounting-hole patterns can be made to coincide by a
rotation about the common Z axis.
"""
import math
import numpy as np
import matplotlib.pyplot as plt

from parse_step import parse_entities, get_circles

PENTAGON_STEP = "../3d/pentagon/v0.0.1/lcd_pentagon_plate.step"
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


def order_ccw(points):
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def rot90(xy):
    x, y = xy
    return (-y, x)


def main():
    pent_ents = parse_entities(PENTAGON_STEP)
    pent_circles = [c for c in get_circles(pent_ents) if round(c["radius"], 2) == 1.9]
    pent_holes = sorted({(round(c["center"][0], 3), round(c["center"][1], 3)) for c in pent_circles})

    disp_ents = parse_entities(DISPLAY_STEP)
    disp_circles = get_circles(disp_ents)
    disp_holes = sorted(
        {
            (round(c["center"][0], 3), round(c["center"][1], 3))
            for c in disp_circles
            if round(c["radius"], 2) == 1.75
        }
    )
    pcb_r = max(c["radius"] for c in disp_circles if round(c["radius"], 2) == 18.75)
    active_r = max(c["radius"] for c in disp_circles if round(c["radius"], 2) == 16.2)

    outline = order_ccw(PENTAGON_OUTLINE)
    outline_closed = outline + [outline[0]]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5))

    for ax, rotate, title in (
        (axes[0], False, "As-designed overlay (0 deg)"),
        (axes[1], True, "Display rotated 90 deg"),
    ):
        xs, ys = zip(*outline_closed)
        ax.plot(xs, ys, "k-", lw=1.5, label="pentagon plate outline")

        for hx, hy in pent_holes:
            ax.add_patch(plt.Circle((hx, hy), 1.9, fill=False, color="tab:orange", lw=1.5))
        ax.plot([], [], color="tab:orange", label="pentagon holes (d=3.8mm)")

        theta = np.linspace(0, 2 * math.pi, 200)
        ax.plot(pcb_r * np.cos(theta), pcb_r * np.sin(theta), "b--", lw=1, label="LCD PCB outline (d=37.5mm)")
        ax.plot(active_r * np.cos(theta), active_r * np.sin(theta), "b:", lw=1, label="LCD active area (d=32.4mm)")

        for hx, hy in disp_holes:
            if rotate:
                hx, hy = rot90((hx, hy))
            ax.add_patch(plt.Circle((hx, hy), 1.75, fill=False, color="tab:blue", lw=1.5))
        ax.plot([], [], color="tab:blue", label="LCD holes (d=3.5mm)")

        ax.set_title(title)
        ax.set_aspect("equal")
        ax.set_xlim(-30, 30)
        ax.set_ylim(-30, 30)
        ax.grid(alpha=0.3)

    axes[0].legend(loc="lower left", fontsize=7)
    fig.suptitle("exp-dodecahedron-earth: pentagon plate vs 1.28in LCD module (XY overlay)")
    fig.tight_layout()
    out = "overlay.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")

    print("\npentagon holes (x, y):", pent_holes)
    print("display holes (x, y):", disp_holes)
    print("display holes rotated 90deg:", sorted(rot90(h) for h in disp_holes))
    print(f"LCD PCB diameter: {pcb_r * 2:.1f} mm, active area diameter: {active_r * 2:.1f} mm")


if __name__ == "__main__":
    main()
