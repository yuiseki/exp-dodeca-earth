"""Every combination of how the modules can sit, and the smallest dodecahedron for each.

    ../../.venv/bin/python sweep.py [OUT_DIR] [WORKERS] [contain]     # default ../../tmp/simulate, 4 workers

With `contain`, a combination also needs each module's outline (the PCB with its bump, seen square to the face) to stay
inside its own face's pentagon: nothing overhangs the face.

Varies:
- side: the side displays' bump, as an angle in the face from the direction of the rim vertex (0 = toward the equator,
  180 = toward the edge shared with the base, the pole). A 12 degree sweep (2026-11-07) found nothing worth the odd
  turn in between, so only these two.
  Left and right turns are mirror images, so 0..180 covers them;
- base: the base display's bump toward an edge or a vertex;
- height: how far the module sits above its plate's outer face, relative to now (PCB back on the face): -1.6 sinks the
  PCB into a pocket of its own outline (no rim condition), positive values raise it on spacers.
For each, the smallest edge (to 0.125 mm) at which no two neighbouring modules come within 0.3 mm and each module's
screw holes and connector stay on its own plate (fit.py), the module shifted along its bump axis for the best fit.
Writes OUT_DIR/results.csv, OUT_DIR/summary.md and a picture at its smallest size for the 36 degree, 1 mm subset."""
import csv
import itertools
import math
import os
import sys
from multiprocessing import Pool

import numpy as np

import fit

SIDE = [0, 180]  # toward the equator (the rim vertex) or the pole (the edge on the base); turns in between were no use
PICTURE_SIDE = SIDE
BASE = ["edge", "vertex"]
HEIGHT = [-1.6, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
PICTURE_HEIGHT = [-1.6, 0.0, 1.0, 2.0, 3.0, 4.0]
SHIFTS = np.arange(-3.0, 3.01, 0.5)       # the side modules, along their bump axis
BASE_SHIFTS = np.arange(-3.0, 3.01, 1.0)  # the base module


def unit(x):
    return x / np.linalg.norm(x)


def frames(L, side_deg, base_kind, s_side, s_base):
    """fit.frames, with the side bump turned side_deg from the rim vertex and the base bump at an edge or a vertex."""
    ri = L / 2 * math.sqrt(5 / 2 + 11 / 10 * 5 ** 0.5)
    out = {}
    for f in range(12):
        nn = fit.N[f]
        c = ri * nn
        if f in (0, fit.base_up):
            side = [g for g in (fit.lower if f == 0 else fit.upper) if g != f][0]
            toward_edge = unit(fit.N[side] - (fit.N[side] @ nn) * nn)
            t = math.radians(0 if base_kind == "edge" else 36)
            bx = math.cos(t) * toward_edge + math.sin(t) * np.cross(nn, toward_edge)
            s = s_base
        else:
            pole = fit.n0 if f in fit.lower else fit.N[fit.base_up]
            apex = unit(-(pole - (pole @ nn) * nn))
            # the upper cup is the lower one turned 180 degrees about x: the same turn, seen from outside, on both
            t = math.radians(side_deg)
            bx = math.cos(t) * apex + math.sin(t) * np.cross(nn, apex)
            s = s_side
        by = np.cross(nn, bx)
        out[f] = (c + s * bx, bx, by, nn, c)
    return out


def set_height(h):
    base = fit.BASE_LAYERS
    fit.LAYERS = [(p, h0 + h, h1 + h) for p, h0, h1 in base]
    fit.SAMPLES = [fit.sample(p, h0, h1) for p, h0, h1 in fit.LAYERS]
    fit.GROWN = [(p.buffer(fit.CLEAR), h0 - fit.CLEAR, h1 + fit.CLEAR) for p, h0, h1 in fit.LAYERS]


CONTAIN = False


def fits(L, side_deg, base_kind, s_side, s_base):
    fr = frames(L, side_deg, base_kind, s_side, s_base)
    from shapely.geometry import Point
    for f in range(12):
        pl = fit.plate(L, f, fr)
        if CONTAIN and not pl.contains(fit.BASE_LAYERS[0][0]):
            return False, "overhang"
        if not all(pl.buffer(-fit.HOLE_KEEP).contains(Point(p)) for p in fit.HOLES):
            return False, "holes"
        if not pl.buffer(-0.8).contains(fit.SLOT):
            return False, "slot"
    for a, b in fit.neighbours:
        if fit.collide(a, b, fr) or fit.collide(b, a, fr):
            return False, "touch"
    return True, ""


def any_fit(L, side_deg, base_kind):
    whys = {}
    for s_side in SHIFTS:
        for s_base in BASE_SHIFTS:
            ok, why = fits(L, side_deg, base_kind, s_side, s_base)
            if ok:
                return (float(s_side), float(s_base)), whys
            whys[why] = whys.get(why, 0) + 1
    return None, whys


def smallest(args):
    side_deg, base_kind, h = args
    set_height(h)
    lo, hi = 22.0, 34.0  # lo fails, hi fits (checked)
    shifts, _ = any_fit(hi, side_deg, base_kind)
    if shifts is None:
        return side_deg, base_kind, h, None, None, "fails even at 34 mm"
    best = shifts
    why_lo = {}
    while hi - lo > 0.125:
        mid = (lo + hi) / 2
        s, whys = any_fit(mid, side_deg, base_kind)
        if s is None:
            lo, why_lo = mid, whys
        else:
            hi, best = mid, s
    limit = max(why_lo, key=why_lo.get) if why_lo else ""
    print(f"side {side_deg:3d} base {base_kind:6s} height {h:+.1f}: {hi:.3f} mm ({limit})", flush=True)
    return side_deg, base_kind, h, hi, best, limit


def picture(out_dir, side_deg, base_kind, h, L, shifts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import render
    set_height(h)
    fit.frames = lambda L_, pattern, s1, s2: frames(L_, side_deg, base_kind, s1, s2)
    fig, ax = plt.subplots(figsize=(5, 5), dpi=110)
    render.draw(ax, L, 0, shifts[0], shifts[1], f"side {side_deg} / base {base_kind} / height {h:+.1f}\nedge {L:.2f} mm")
    plt.tight_layout()
    path = os.path.join(out_dir, f"side{side_deg:03d}_base-{base_kind}_h{h:+.1f}.png")
    plt.savefig(path)
    plt.close(fig)
    return path


def _set_contain(v):
    global CONTAIN
    CONTAIN = v


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../tmp/simulate")
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    global CONTAIN
    CONTAIN = len(sys.argv) > 3 and sys.argv[3] == "contain"
    os.makedirs(out_dir, exist_ok=True)
    combos = list(itertools.product(SIDE, BASE, HEIGHT))
    with Pool(workers, initializer=_set_contain, initargs=(CONTAIN,)) as pool:
        rows = pool.map(smallest, combos, chunksize=1)
    with open(os.path.join(out_dir, "results.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["side_deg", "base", "height_mm", "min_edge_mm", "side_shift_mm", "base_shift_mm", "limited_by"])
        for side_deg, base_kind, h, L, s, limit in rows:
            w.writerow([side_deg, base_kind, h, f"{L:.3f}" if L else "", s[0] if s else "", s[1] if s else "", limit])
    for side_deg, base_kind, h, L, s, limit in rows:
        if L and side_deg in PICTURE_SIDE and h in PICTURE_HEIGHT:
            picture(out_dir, side_deg, base_kind, h, L, s)
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        for base_kind in BASE:
            f.write(f"\n## base bump toward an {base_kind}: smallest edge (mm)\n\n| side \\ height | " + " | ".join(f"{h:+.1f}" for h in HEIGHT) + " |\n")
            f.write("|---|" + "---|" * len(HEIGHT) + "\n")
            for side_deg in SIDE:
                cells = []
                for h in HEIGHT:
                    r = [x for x in rows if x[:3] == (side_deg, base_kind, h)][0]
                    cells.append(f"{r[3]:.2f}" if r[3] else "-")
                f.write(f"| {side_deg} | " + " | ".join(cells) + " |\n")
    print("wrote", out_dir)


fit.BASE_LAYERS = list(fit.LAYERS)

if __name__ == "__main__":
    main()
