"""How small can the dodecahedron be (run: ../../.venv/bin/python fit.py, about 10 minutes) with the 1.28 inch modules on its faces? Two patterns:
1: each side display's bump (the LCD's FPC side) toward the base (the pole), as now;
2: toward the rim vertex (the equator). The base display's bump points at an edge in both.
A size works when no two modules on neighbouring faces overlap (0.3 mm apart), and each module's
screw holes and connector slot stay on its own plate."""
import math, os, struct, sys
import numpy as np
from shapely.geometry import MultiPoint, Polygon, Point
from shapely import contains_xy, prepared

STL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../3d/display/1.28inch_LCD_Module_3D_Drawing/1.28inch LCD Module 3D Drawing/0508.stl")
d = open(STL, "rb").read()
n = struct.unpack("<I", d[80:84])[0]
v = np.frombuffer(d[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))["v"].reshape(-1, 3).astype(float)
# module z: -3.15 screen .. 0.6 PCB back (on the plate); height above the plate h = 0.6 - z
def hull(z0, z1):
    m = (v[:, 2] >= z0) & (v[:, 2] <= z1)
    return MultiPoint([tuple(p) for p in v[m][:, :2]]).convex_hull
LAYERS = [(hull(-1.05, 0.65), 0.0, 1.6), (hull(-3.2, -1.05), 1.6, 3.75)]  # (outline, h0, h1); bump toward +x
HOLES = [(sx * 13.35, sy * 9.3) for sx in (1, -1) for sy in (1, -1)]  # plate coords, module centre at origin
HOLE_KEEP = 1.9 + 0.8
SLOT = Polygon([(-11.2, -10.0), (-5.2, -10.0), (-5.2, 10.0), (-11.2, 10.0)])  # the connector, opposite the bump
CLEAR = 0.3
PHI = (1 + 5 ** 0.5) / 2

ico = []
for a in (1, -1):
    for b in (1, -1):
        ico += [(0, a, b * PHI), (a, b * PHI, 0), (b * PHI, 0, a)]
N = np.array(ico, float); N /= np.linalg.norm(N, axis=1)[:, None]
n0 = N[0]
lower = [0] + [i for i in range(12) if abs(N[i] @ n0 - 1 / 5 ** 0.5) < 1e-6]
upper = [i for i in range(12) if i not in lower]
base_up = [i for i in upper if N[i] @ n0 < -0.99][0]
neighbours = [(i, j) for i in range(12) for j in range(i + 1, 12) if abs(N[i] @ N[j] - 1 / 5 ** 0.5) < 1e-6]
assert len(neighbours) == 30

def unit(x): return x / np.linalg.norm(x)

def frames(L, pattern, s_side, s_base):
    """face -> (centre, x axis (bump), y axis, normal), and the module's centre offset along its bump axis."""
    ri = L / 2 * math.sqrt(5 / 2 + 11 / 10 * 5 ** 0.5)
    out = {}
    for f in range(12):
        nn = N[f]
        c = ri * nn
        if f in (0, base_up):
            side = [g for g in (lower if f == 0 else upper) if g != f][0]
            bx = unit(N[side] - (N[side] @ nn) * nn)          # base: bump toward the edge it shares with one side face
            s = s_base
        else:
            pole = n0 if f in lower else N[base_up]
            apex = unit(-(pole - (pole @ nn) * nn))           # in the face, away from its cup's base: toward the rim
            bx = apex if pattern == 2 else -apex
            s = s_side
        by = np.cross(nn, bx)
        out[f] = (c + s * bx, bx, by, nn, c)
    return out

def plate(L, f, fr):
    """the face's pentagon in the module's own (x, y) coords."""
    ri = L / 2 * math.sqrt(5 / 2 + 11 / 10 * 5 ** 0.5)
    Rf = L / (2 * math.sin(math.radians(36)))
    mc, bx, by, nn, c = fr[f]
    # a vertex of the face: the dodecahedron's vertices are where 3 faces meet; take the face's 5 nearest neighbours' midpoints
    nb = [g for g in range(12) if abs(N[g] @ N[f] - 1 / 5 ** 0.5) < 1e-6]
    mids = [unit(N[g] - (N[g] @ N[f]) * N[f]) for g in nb]     # edge midpoint directions
    ang = sorted(math.atan2(m @ by, m @ bx) for m in mids)
    a = L / (2 * math.tan(math.radians(36)))
    pts = []
    for t in ang:
        for dt in (-36, 36):
            th = t + math.radians(dt)
            pts.append((math.atan2(math.sin(th), math.cos(th)), (Rf * math.cos(th), Rf * math.sin(th))))
    pts = sorted(set((round(p[0], 6), round(p[1][0], 6), round(p[1][1], 6)) for p in pts))
    off = np.array([(mc - c) @ bx, (mc - c) @ by])
    return Polygon([(x - off[0], y - off[1]) for _, x, y in pts])

def sample(poly, h0, h1, step=0.6):
    x0, y0, x1, y1 = poly.bounds
    xs, ys = np.meshgrid(np.arange(x0, x1, step), np.arange(y0, y1, step))
    xs, ys = xs.ravel(), ys.ravel()
    m = contains_xy(poly, xs, ys)
    hs = np.linspace(h0, h1, 4)
    return [(xs[m], ys[m], h) for h in hs]

SAMPLES = [sample(p, h0, h1) for p, h0, h1 in LAYERS]
GROWN = [(p.buffer(CLEAR), h0 - CLEAR, h1 + CLEAR) for p, h0, h1 in LAYERS]

def collide(fa, fb, fr):
    ma, ax, ay, an, _ = fr[fa]
    mb, bx, by, bn, _ = fr[fb]
    for layer in SAMPLES:
        for xs, ys, h in layer:
            P = ma[None, :] + xs[:, None] * ax + ys[:, None] * ay + h * an    # world points of A
            d = P - mb
            lx, ly, lh = d @ bx, d @ by, d @ bn
            for poly, h0, h1 in GROWN:
                m = (lh >= h0) & (lh <= h1)
                if m.any() and contains_xy(poly, lx[m], ly[m]).any():
                    return True
    return False

def fits(L, pattern, s_side, s_base):
    fr = frames(L, pattern, s_side, s_base)
    for f in range(12):
        pl = plate(L, f, fr)
        inner = pl.buffer(-HOLE_KEEP)
        if not all(inner.contains(Point(h)) for h in HOLES): return False, "holes"
        if not pl.buffer(-0.8).contains(SLOT): return False, "slot"
    for a, b in neighbours:
        if collide(a, b, fr) or collide(b, a, fr):
            kind = lambda f: "base" if f in (0, base_up) else ("side-lower" if f in lower else "side-upper")
            return False, f"touch {kind(a)}/{kind(b)}"
    return True, ""

if __name__ == "__main__":
    for pattern in (1, 2):
        best = None
        for L in np.arange(30.0, 24.9, -0.25):
            ok_any, whys = None, {}
            for s_side in np.arange(-3.0, 3.01, 0.5):
                for s_base in (0.0, -1.0, 1.0):
                    ok, why = fits(L, pattern, s_side, s_base)
                    if ok:
                        ok_any = (s_side, s_base); break
                    whys[why] = whys.get(why, 0) + 1
                if ok_any: break
            if ok_any:
                best = (L, ok_any)
            else:
                print(f"pattern {pattern}: {L:.2f} mm fails: {whys}", flush=True)
                break
        print(f"pattern {pattern}: smallest edge {best[0]:.2f} mm (side shift {best[1][0]:+.1f}, base shift {best[1][1]:+.1f})", flush=True)
