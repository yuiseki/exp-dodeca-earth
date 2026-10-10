"""Build v0.0.5: one cup, printed twice.

A cup is the base plate plus five side plates, fused into one solid. The
upper cup of the dodecahedron is exactly the lower cup turned 180 deg about
the x axis (checked plate by plate, matrix error 0), so one design serves
both, as long as each side plate can mate whichever way it is placed.

On a rim edge the two plates meet with opposite ends, so a magnet pair
needs a pocket at the same distance from the same end on both plates. So
the side plate carries a pocket at both ends of each of its two rim edges
(the v0.0.4 lower plate's apex pockets plus the v0.0.4 upper plate's corner
pockets): 3 bosses, 4 pockets. Only 20 of the 40 pockets get a magnet: the
lower cup gets them in its apex pockets, the upper cup in its corner
pockets. The base plate is v0.0.4's cap.

Writes lcd_pentagon_plate_side.step/.stl and magnets_side.json (via
v0.0.4's build.py), and lcd_cup.step/.stl, the cup standing on its outer
face, opening up, which is also how it is printed (the walls lean outward
26.6 deg from vertical, so no support is needed).

Run from this directory with the project venv:
    ../../../.venv/bin/python build.py
"""
import importlib.util
import os
import sys
from collections import Counter

import gmsh
import numpy as np
from stl import mesh

sys.path.insert(0, "../../../simulate")
import dodecahedron as dd

spec = importlib.util.spec_from_file_location("build_v004", "../v0.0.4/build.py")
b4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b4)

FACE_DIST = 33.40533  # centre of the dodecahedron to a face, edge 30mm
CAP = "../v0.0.4/lcd_pentagon_plate_cap"
SIDE = "lcd_pentagon_plate_side"


def place(tags, m):
    """Apply a rigid 4x4 transform with exact rotate/translate.

    gmsh's affineTransform turns the shapes into approximate B-spline
    copies (a plate lost 0.07% of its volume), so it is not used here."""
    r, t = np.asarray(m)[:3, :3], np.asarray(m)[:3, 3]
    assert np.allclose(r @ r.T, np.eye(3), atol=1e-9) and np.linalg.det(r) > 0
    w, vecs = np.linalg.eig(r)
    axis = np.real(vecs[:, np.argmin(abs(w - 1))])
    axis /= np.linalg.norm(axis)
    angle = float(np.arctan2(0.5 * axis @ np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]), (np.trace(r) - 1) / 2))
    if abs(angle) > 1e-12:
        gmsh.model.occ.rotate(tags, 0, 0, 0, *axis, angle)
    gmsh.model.occ.translate(tags, *t)


def build_side_plate():
    b4.VARIANTS["side"] = [("apex", ["right", "left"]), ("right", ["apex"]), ("left", ["apex"])]
    b4.build("side")


def build_cup():
    placed = dd.two_cups(dd.dodecahedron_faces())
    roles = [r for r, *_ in placed]
    transforms = [dd.plate_to_face(c, n, v) for _, c, n, v, _ in placed]
    members = [i for i, r in enumerate(roles) if r in ("base", "lower")]
    assert len(members) == 6, members
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        occ = gmsh.model.occ
        parts, expect = [], 0.0
        for i in members:
            tags = occ.importShapes((CAP if roles[i] == "base" else SIDE) + ".step")
            expect += sum(occ.getMass(d, t) for d, t in tags)
            place(tags, transforms[i])
            parts.append(tags)
        fused, _ = occ.fuse(parts[0], [t for p in parts[1:] for t in p])
        occ.synchronize()
        flip = np.eye(4)
        flip[2, 3] = FACE_DIST
        place(fused, flip)
        occ.synchronize()
        solids = gmsh.model.getEntities(3)
        vol = sum(occ.getMass(d, t) for d, t in solids)
        print(f"[cup] solids {len(solids)}, volume {vol:.1f} mm3 (6 plates sum to {expect:.1f})")
        assert len(solids) == 1 and abs(vol - expect) < 1.0, "fusing changed the material"
        gmsh.write("lcd_cup.step")
        gmsh.clear()
        gmsh.model.occ.importShapes("lcd_cup.step")
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 72)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 2.0)
        gmsh.option.setNumber("Mesh.Binary", 1)
        gmsh.model.mesh.generate(2)
        gmsh.write("lcd_cup.stl")
    finally:
        gmsh.finalize()


def report_stl(path):
    m = mesh.Mesh.from_file(path)
    v = m.vectors
    k = lambda p: tuple(np.round(p, 5))
    c = Counter()
    for t in v:
        a, b, d = k(t[0]), k(t[1]), k(t[2])
        c.update(tuple(sorted(e)) for e in ((a, b), (b, d), (d, a)))
    vol = float(np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum() / 6)
    print(f"[{path}] {len(v)} triangles, open edges {sum(1 for n in c.values() if n != 2)}, volume {vol:.1f} mm3, "
          f"size {np.round(m.max_ - m.min_, 2)}, file {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    build_side_plate()
    build_cup()
    report_stl("lcd_pentagon_plate_side.stl")
    report_stl("lcd_cup.stl")
