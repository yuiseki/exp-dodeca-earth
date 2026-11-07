"""Run: ../../.venv/bin/python fit_recessed.py PATTERN RIM POCKET (RIM -100: no rim condition; POCKET < 0 raises the module).

fit.py with the module sunk POCKET mm into its plate (the PCB in a pocket of its own outline), and the pocket
keeping a RIM mm ring of the plate's outer face."""
import sys
import numpy as np
from shapely.geometry import Point
import fit

POCKET = float(sys.argv[3]) if len(sys.argv) > 3 else 1.6
RIM = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
fit.LAYERS = [(p, h0 - POCKET, h1 - POCKET) for p, h0, h1 in fit.LAYERS]
fit.SAMPLES = [fit.sample(p, h0, h1) for p, h0, h1 in fit.LAYERS]
fit.GROWN = [(p.buffer(fit.CLEAR), h0 - fit.CLEAR, h1 + fit.CLEAR) for p, h0, h1 in fit.LAYERS]
PCB = fit.LAYERS[0][0].buffer(0.25)

def fits(L, pattern, s_side, s_base):
    fr = fit.frames(L, pattern, s_side, s_base)
    for f in range(12):
        pl = fit.plate(L, f, fr)
        if not all(pl.buffer(-fit.HOLE_KEEP).contains(Point(h)) for h in fit.HOLES): return False, "holes"
        if RIM > -50 and not pl.buffer(-RIM).contains(PCB): return False, "rim"
    for a, b in fit.neighbours:
        if fit.collide(a, b, fr) or fit.collide(b, a, fr): return False, "touch"
    return True, ""

pattern = int(sys.argv[1]) if len(sys.argv) > 1 else 2
best = None
for L in np.arange(33.0, 22.9, -0.25):
    ok, whys = None, {}
    for s_side in np.arange(-3.0, 3.01, 0.5):
        for s_base in np.arange(-3.0, 3.01, 0.5):
            good, why = fits(L, pattern, s_side, s_base)
            if good: ok = (s_side, s_base); break
            whys[why] = whys.get(why, 0) + 1
        if ok: break
    if ok:
        best = (L, ok); print(f"  {L:.2f} ok, shifts {ok}", flush=True)
    else:
        print(f"pattern {pattern}: {L:.2f} fails {whys}", flush=True); break
print(f"pattern {pattern} recessed {POCKET} mm: smallest edge {best[0]:.2f} mm, side shift {best[1][0]:+.1f}, base shift {best[1][1]:+.1f}")
