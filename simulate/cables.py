"""Where the six display cables of one cup come out, and how far they must run.

The cup is the v0.0.5 common cup standing on its base (z up, z=0 on the outer
base face), as in dodecahedron.py. Each display's PH2.0 8-pin header sits at
x=-7.5, y=0 on the display (STEP frame), 5.6mm above the plate's outer face,
and the plug goes in along the plate's inward normal. PLUG is an assumed plug
height above the header top (not measured).

    ../.venv/bin/python cables.py    # prints the table, writes v0.0.5/cables.png
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import dodecahedron as dd

FACE_DIST = 33.40533
PLUG = 6.0
HEADER_TOP = np.array([0.0, 7.5, 5.6, 1.0])  # plate frame: header top centre; long axis along plate x


def connectors():
    placed = dd.two_cups(dd.dodecahedron_faces())
    roles = [r for r, *_ in placed]
    M = [dd.plate_to_face(c, n, v) for _, c, n, v, _ in placed]
    centres = [c for _, c, *_ in placed]
    lower = sorted((i for i, r in enumerate(roles) if r == "lower"), key=lambda i: math.atan2(centres[i][1], centres[i][0]))
    members = {f"plate {n}": i for n, i in enumerate(lower, 1)}
    members["base"] = next(i for i, r in enumerate(roles) if r == "base")
    out = {}
    for name, i in members.items():
        top = (M[i] @ HEADER_TOP)[:3] + [0, 0, FACE_DIST]
        inward = M[i][:3, :3] @ np.array([0, 0, 1.0])
        out[name] = dict(top=top, inward=inward, long=M[i][:3, :3] @ np.array([1.0, 0, 0]), exit=top + PLUG * inward)
    return out


def main():
    info = connectors()
    names = list(info)
    E = np.array([info[n]["exit"] for n in names])
    for n in names:
        t, e = info[n]["top"], info[n]["exit"]
        print(f"{n:8s} header top {np.round(t, 1)} azimuth {math.degrees(math.atan2(t[1], t[0])):7.1f} deg, "
              f"cable exit {np.round(e, 1)} (r {math.hypot(*e[:2]):.1f}, z {e[2]:.1f})")
    print("neighbouring side exits are", round(float(np.linalg.norm(E[0] - E[1])), 1), "mm apart")
    for z in (8, 14, 20, 26, 32):
        d = np.linalg.norm(E - np.array([0, 0, z]), axis=1)
        print(f"hub on the axis at z={z:2d}: straight runs {np.round(d).astype(int).tolist()} mm (longest {d.max():.0f})")

    fig, axs = plt.subplots(1, 2, figsize=(14, 7))
    ax = axs[0]
    th = np.linspace(0, 2 * math.pi, 200)
    ax.plot(29 * np.cos(th), 29 * np.sin(th), color="#bbb", lw=0.8, ls=":")
    for n, d in info.items():
        t, e, lg = d["top"], d["exit"], d["long"]
        l2 = lg[:2] / max(np.linalg.norm(lg[:2]), 1e-9)
        ax.plot(*zip(t[:2] - 10 * l2, t[:2] + 10 * l2), color="#555", lw=6, alpha=0.5, solid_capstyle="butt")
        ax.annotate("", xy=e[:2], xytext=t[:2], arrowprops=dict(arrowstyle="->", color="tab:red"))
        ax.text(t[0] * 1.17, t[1] * 1.17, n, ha="center", va="center", fontsize=10)
    ax.add_patch(plt.Circle((0, 0), 22, fill=False, color="tab:blue", lw=1.5, ls="--"))
    ax.set_aspect("equal"); ax.set_xlim(-42, 42); ax.set_ylim(-42, 42); ax.grid(alpha=0.3)
    ax.set_title("from above: header (grey bar), plug direction (red)", fontsize=10)
    ax = axs[1]
    for n, d in info.items():
        t, e = d["top"], d["exit"]
        ax.plot([math.hypot(*t[:2]), math.hypot(*e[:2])], [t[2], e[2]], color="tab:red")
        ax.text(math.hypot(*t[:2]) + 0.8, t[2] + 0.8, n, fontsize=8)
    ax.axhline(33.4, color="#999", ls="--")
    ax.set_xlabel("distance from the cup axis (mm)"); ax.set_ylabel("height above the base outer face (mm)")
    ax.set_title("side view: header top to cable exit; dashed = joint height", fontsize=10); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig("v0.0.5/cables.png", dpi=105)
    print("wrote v0.0.5/cables.png")


if __name__ == "__main__":
    main()
