"""The round part of each display inside its face; the side displays' bump (toward the equator) may overhang.
The pole displays either whole (bump included) inside their face, or only their round part.
    ../../.venv/bin/python round_contained.py"""
from multiprocessing import Pool
from shapely.geometry import Point
import fit, sweep

ROUND = Point(0, 0).buffer(18.75, 64)   # the PCB's round part (the module's centre at the origin)
POLE = "whole"

def fits(L, side_deg, base_kind, s_side, s_base):
    fr = sweep.frames(L, side_deg, base_kind, s_side, s_base)
    poles = (0, fit.base_up)
    for f in range(12):
        pl = fit.plate(L, f, fr)
        need = fit.BASE_LAYERS[0][0] if (f in poles and POLE == "whole") else ROUND
        if not pl.contains(need):
            return False, "overhang"
        if not all(pl.buffer(-fit.HOLE_KEEP).contains(Point(p)) for p in fit.HOLES):
            return False, "holes"
        if not pl.buffer(-0.8).contains(fit.SLOT):
            return False, "slot"
    for a, b in fit.neighbours:
        if fit.collide(a, b, fr) or fit.collide(b, a, fr):
            return False, "touch"
    return True, ""

def run(args):
    global POLE
    POLE, side_deg, base_kind, h = args
    sweep.fits = fits
    return (POLE,) + sweep.smallest((side_deg, base_kind, h))

if __name__ == "__main__":
    combos = [(p, 0, b, h) for p in ("whole", "round") for b in ("vertex", "edge") for h in (-1.6, 0.0, 1.0, 2.0, 3.0, 4.0)]
    with Pool(4) as pool:
        rows = pool.map(run, combos, chunksize=1)
    for r in rows:
        print(f"pole {r[0]:5s} side {r[1]} base {r[2]:6s} h {r[3]:+.1f}: {r[4]:.2f} mm ({r[6]})")
