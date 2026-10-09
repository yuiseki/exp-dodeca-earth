"""Build v0.0.5: each cup (6 faces) as one solid instead of 6 plates.

The lower cup is the base plate plus the five lower side plates, the upper
cup the top plate plus the five upper side plates, all taken from v0.0.4
(same 2mm walls, bevels, display holes, slots, magnet bosses and pockets)
and placed on the dodecahedron exactly as simulate/dodecahedron.py does.
Fusing them removes the joints inside a cup, leaving a bowl.

Each cup is written standing on its outer base (or top) face, opening up,
which is also how it is printed: the side walls lean outward by 26.6 deg
from vertical, which needs no support.

Run from this directory with the project venv:
    ../../../.venv/bin/python build.py
"""
import os
import sys

import gmsh
import numpy as np
from stl import mesh

sys.path.insert(0, "../../../simulate")
import dodecahedron as dd

V4 = "../v0.0.4"
FACE_DIST = 33.40533  # centre of the dodecahedron to a face, edge 30mm
CUPS = {"lower": ("base", "lower"), "upper": ("top", "upper")}
KIND = {"base": "cap", "top": "cap", "lower": "lower", "upper": "upper"}


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


def build(cup):
    placed = dd.two_cups(dd.dodecahedron_faces())
    roles = [r for r, *_ in placed]
    transforms = [dd.plate_to_face(c, n, v) for _, c, n, v, _ in placed]
    members = [i for i, r in enumerate(roles) if r in CUPS[cup]]
    assert len(members) == 6, members
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        occ = gmsh.model.occ
        parts, expect = [], 0.0
        for i in members:
            tags = occ.importShapes(f"{V4}/lcd_pentagon_plate_{KIND[roles[i]]}.step")
            expect += sum(occ.getMass(d, t) for d, t in tags)
            place(tags, transforms[i])
            parts.append(tags)
        fused, _ = occ.fuse(parts[0], [t for p in parts[1:] for t in p])
        occ.synchronize()
        # Stand on the outer face of the base (z=-FACE_DIST) or top (z=+FACE_DIST), opening up.
        flip = np.eye(4) if cup == "lower" else np.diag([1.0, -1.0, -1.0, 1.0])
        flip[2, 3] = FACE_DIST
        place(fused, flip)
        occ.synchronize()
        solids = gmsh.model.getEntities(3)
        vol = sum(occ.getMass(d, t) for d, t in solids)
        x0, y0, z0, x1, y1, z1 = occ.getBoundingBox(*solids[0])
        print(f"[{cup} cup] solids {len(solids)}, volume {vol:.1f} mm3 (6 plates sum to {expect:.1f}), "
              f"size {x1 - x0:.2f} x {y1 - y0:.2f} x {z1 - z0:.2f} mm, z from {z0:.2f}")
        assert len(solids) == 1 and abs(vol - expect) < 1.0, "fusing changed the material"
        gmsh.write(f"lcd_cup_{cup}.step")
        gmsh.clear()
        gmsh.model.occ.importShapes(f"lcd_cup_{cup}.step")
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 72)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 2.0)
        gmsh.option.setNumber("Mesh.Binary", 1)
        gmsh.model.mesh.generate(2)
        gmsh.write(f"lcd_cup_{cup}.stl")
    finally:
        gmsh.finalize()


if __name__ == "__main__":
    for cup in CUPS:
        build(cup)
    for cup in CUPS:
        m = mesh.Mesh.from_file(f"lcd_cup_{cup}.stl")
        v = m.vectors
        k = lambda p: tuple(np.round(p, 5))
        from collections import Counter
        c = Counter()
        for t in v:
            a, b, d = k(t[0]), k(t[1]), k(t[2])
            c.update(tuple(sorted(e)) for e in ((a, b), (b, d), (d, a)))
        vol = float(np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum() / 6)
        print(f"[{cup} cup STL] {len(v)} triangles, open edges {sum(1 for n in c.values() if n != 2)}, volume {vol:.1f} mm3, "
              f"size {np.round(m.max_ - m.min_, 2)}, file {os.path.getsize(f'lcd_cup_{cup}.stl') / 1e6:.1f} MB")
