import math, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly
import fit

def project(P, view):
    view = view / np.linalg.norm(view)
    up = np.array([0, 0, 1.0]) - view[2] * view; up /= np.linalg.norm(up)
    right = np.cross(up, view)
    return np.stack([P @ right, P @ up], axis=-1), P @ view

def draw(ax, L, pattern, s_side, s_base, title):
    fr = fit.frames(L, pattern, s_side, s_base)
    view = -fit.n0 * 0.75 + np.array([0.0, 0.0, -0.66])   # from beside and above the lower cup's base, as in the photos
    view = fit.unit(fit.N[fit.lower[1]] + 1.4 * fit.n0) * -1
    items = []
    for f in range(12):
        mc, bx, by, nn, c = fr[f]
        if nn @ view > -0.05:   # facing away
            continue
        pl = fit.plate(L, f, fr)
        ring = np.array(pl.exterior.coords)
        P = mc + ring[:, :1] * bx + ring[:, 1:2] * by
        items.append((P, "#f2f0ea", "#999", 0.6))
        for poly, h0, h1, col in ((fit.LAYERS[0][0], 0, 1.6, "#2b6b3f"), (fit.LAYERS[1][0], 1.6, 3.75, "#151515")):
            ring = np.array(poly.exterior.coords)
            P = mc + ring[:, :1] * bx + ring[:, 1:2] * by + h1 * nn
            items.append((P, col, col, 0.0))
        t = np.linspace(0, 2 * math.pi, 90)
        r = 32.4 / 2
        P = mc + (r * np.cos(t))[:, None] * bx + (r * np.sin(t))[:, None] * by + 3.8 * nn
        items.append((P, "#3a7fd0" if f in (0, fit.base_up) else "#4fb3a0", "none", 0.0))
    # whole faces back to front (by the plate's centre); within a face: plate, PCB, glass, picture
    groups = [items[k:k + 4] for k in range(0, len(items), 4)]
    def depth(g):
        _, z = project(g[0][0], view); return z.mean()
    for P, fc, ec, lw in [it for g in sorted(groups, key=depth, reverse=True) for it in g]:
        xy, _ = project(P, view)
        ax.add_patch(MPoly(xy, closed=True, facecolor=fc, edgecolor=ec, linewidth=lw))
    ax.set_xlim(-60, 60); ax.set_ylim(-60, 60); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title, fontsize=11)

fig, axs = plt.subplots(1, 2, figsize=(12, 6.2), dpi=130)
draw(axs[0], 30.0, 1, -2.0, 0.0, "pattern 1: bump toward the pole, edge 30.00 mm")
draw(axs[1], 28.75, 2, 0.0, -1.0, "pattern 2: bump toward the equator, edge 28.75 mm")
plt.tight_layout(); plt.savefig("patterns.png")
print("ok")
