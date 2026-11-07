"""sweep.py's contain mode, but the base (and top) display exempt from staying inside its face, or left out altogether.
    ../../.venv/bin/python base_exempt.py"""
import sys
from multiprocessing import Pool
import fit, sweep

MODE = "exempt"

def fits(L, side_deg, base_kind, s_side, s_base):
    from shapely.geometry import Point
    fr = sweep.frames(L, side_deg, base_kind, s_side, s_base)
    poles = (0, fit.base_up)
    for f in range(12):
        if MODE == "none" and f in poles:
            continue
        pl = fit.plate(L, f, fr)
        if f not in poles and not pl.contains(fit.BASE_LAYERS[0][0]):
            return False, "overhang"
        if not all(pl.buffer(-fit.HOLE_KEEP).contains(Point(p)) for p in fit.HOLES):
            return False, "holes"
        if not pl.buffer(-0.8).contains(fit.SLOT):
            return False, "slot"
    for a, b in fit.neighbours:
        if MODE == "none" and (a in poles or b in poles):
            continue
        if fit.collide(a, b, fr) or fit.collide(b, a, fr):
            return False, "touch"
    return True, ""

def run(args):
    global MODE
    MODE, side_deg, base_kind, h = args
    sweep.fits = fits
    return (MODE,) + sweep.smallest((side_deg, base_kind, h))

if __name__ == "__main__":
    combos = [(m, s, b, h) for m in ("exempt", "none") for s in (0, 180) for b in (("edge", "vertex") if m == "exempt" else ("edge",)) for h in (-1.6, 0.0, 2.0, 4.0)]
    with Pool(4) as p:
        rows = p.map(run, combos, chunksize=1)
    for r in rows:
        print(f"{r[0]:6s} side {r[1]:3d} base {r[2]:6s} h {r[3]:+.1f}: {r[4]:.2f} mm ({r[6]})")
