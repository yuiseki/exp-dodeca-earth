"""Assemble twelve plates (and their displays) into a regular
dodecahedron and check the fit:

- each plate's outer corners land on the dodecahedron's vertices,
- no two parts overlap,
- every pair of plates sharing an edge touches across the whole bevel.

    ../.venv/bin/python dodecahedron.py v0.0.3   # writes v0.0.3/dodecahedron.3mf

Which way each plate is turned within its face (where its apex points)
is arbitrary here; it does not affect the fit.
"""
import itertools
import math
import os
import sys

import gmsh
import numpy as np
from stl import mesh

from overlay_stl import DISPLAY_COLOR, PCB_BACK_Z, PLATE_COLOR, write_3mf

DISPLAY_STEP = (
    "../3d/display/1.28inch_LCD_Module_3D_Drawing/"
    "1.28inch LCD Module 3D Drawing/0508.stp"
)
EDGE = 30.0
PHI = (1 + math.sqrt(5)) / 2
PLATE_CENTER = np.array([0.0, -1.63, 0.0])
PLATE_APEX = np.array([0.0, 23.88952425056, 0.0])


def dodecahedron_faces():
    """(center, outward normal, one vertex) for each face, edge length EDGE."""
    s = EDGE / (2 / PHI)
    verts = [np.array(v, float) for v in itertools.product((-1, 1), repeat=3)]
    for a, b in itertools.product((-1, 1), repeat=2):
        verts += [np.array((0, a / PHI, b * PHI)), np.array((a / PHI, b * PHI, 0)), np.array((b * PHI, 0, a / PHI))]
    verts = [v * s for v in verts]
    normals = []
    for a, b in itertools.product((-1, 1), repeat=2):
        normals += [(0, a * PHI, b), (a * PHI, b, 0), (b, 0, a * PHI)]
    faces = []
    for n in normals:
        n = np.array(n, float) / np.linalg.norm(n)
        d = [float(v @ n) for v in verts]
        top = [v for v, dv in zip(verts, d) if dv > max(d) - 1e-6]
        assert len(top) == 5
        faces.append((sum(top) / 5, n, top[0], top))
    return faces


def plate_to_face(center, normal, vertex):
    """4x4 transform from plate-local coords (outer face z=0, outward -z)
    onto a face: plate center -> face center, apex -> the given vertex."""
    u_l = (PLATE_APEX - PLATE_CENTER) / np.linalg.norm(PLATE_APEX - PLATE_CENTER)
    n_l = np.array([0.0, 0.0, -1.0])
    u = (vertex - center) / np.linalg.norm(vertex - center)
    local = np.column_stack([u_l, np.cross(u_l, n_l), n_l])
    world = np.column_stack([u, np.cross(u, normal), normal])
    r = world @ local.T
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = center - r @ PLATE_CENTER
    return m


# Display STEP -> plate-local: the -90 deg turn used in overlay.py, and
# the PCB back face (z=0.45 in the STEP) onto the plate's outer face z=0.
DISPLAY_TO_PLATE = np.array([[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 1, -PCB_BACK_Z], [0, 0, 0, 1]], float)


def apply(m, tris):
    flat = tris.reshape(-1, 3)
    return (flat @ m[:3, :3].T + m[:3, 3]).reshape(tris.shape)


def main():
    version = sys.argv[1]
    plate_step = f"../3d/pentagon/{version}/lcd_pentagon_plate.step"
    plate_stl = f"../3d/pentagon/{version}/lcd_pentagon_plate.stl"
    os.makedirs(version, exist_ok=True)

    faces = dodecahedron_faces()
    transforms = [plate_to_face(c, n, v) for c, n, v, _ in faces]

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        plates, displays = [], []
        for m in transforms:
            p = gmsh.model.occ.importShapes(plate_step)
            gmsh.model.occ.affineTransform(p, list(m[:3].ravel()))
            plates.append(p)
            d = gmsh.model.occ.importShapes(DISPLAY_STEP)
            gmsh.model.occ.affineTransform(d, list((m @ DISPLAY_TO_PLATE)[:3].ravel()))
            displays.append(d)
        gmsh.model.occ.synchronize()

        corner_err = []
        for (c, n, v, top), p in zip(faces, plates):
            pts = []
            for _, tag in gmsh.model.getBoundary(p, combined=False, recursive=True):
                x = np.array(gmsh.model.getValue(0, tag, []))
                pts.append(x)
            for vert in top:
                corner_err.append(min(np.linalg.norm(x - vert) for x in pts))
        print(f"plate corners vs dodecahedron vertices: max distance {max(corner_err):.2e} mm")

        def vol(dimtags):
            return sum(gmsh.model.occ.getMass(d, t) for d, t in dimtags)

        def overlap(a, b):
            out, _ = gmsh.model.occ.intersect(a, b, removeObject=False, removeTool=False)
            v = vol(out)
            if out:
                gmsh.model.occ.remove(out, recursive=True)
            return v

        adjacent = set()
        for i, j in itertools.combinations(range(12), 2):
            shared = sum(1 for a in faces[i][3] for b in faces[j][3] if np.linalg.norm(a - b) < 1e-6)
            if shared == 2:
                adjacent.add((i, j))
        print(f"adjacent face pairs: {len(adjacent)}")

        worst = {"plate-plate": 0.0, "display-display": 0.0, "plate-display": 0.0}
        for i, j in itertools.combinations(range(12), 2):
            worst["plate-plate"] = max(worst["plate-plate"], overlap(plates[i], plates[j]))
            worst["display-display"] = max(worst["display-display"], overlap(displays[i], displays[j]))
            worst["plate-display"] = max(worst["plate-display"], overlap(plates[i], displays[j]), overlap(plates[j], displays[i]))
        for i in range(12):
            worst["plate-display"] = max(worst["plate-display"], overlap(plates[i], displays[i]))
        gmsh.model.occ.synchronize()
        for k, v in worst.items():
            print(f"largest overlap {k}: {v:.4f} mm3")

        # Contact: fragment adjacent plate pairs and measure the face they share.
        areas = []
        for i, j in sorted(adjacent):
            a = gmsh.model.occ.copy(plates[i])
            b = gmsh.model.occ.copy(plates[j])
            out, _ = gmsh.model.occ.fragment(a, b)
            gmsh.model.occ.synchronize()
            vols = [t for d, t in out if d == 3]
            faces_a = {t for _, t in gmsh.model.getBoundary([(3, vols[0])], oriented=False)}
            faces_b = set()
            for t in vols[1:]:
                faces_b |= {s for _, s in gmsh.model.getBoundary([(3, t)], oriented=False)}
            shared = faces_a & faces_b
            areas.append(sum(gmsh.model.occ.getMass(2, s) for s in shared))
            gmsh.model.occ.remove(out, recursive=True)
            gmsh.model.occ.synchronize()
        print(f"shared bevel area per edge: min {min(areas):.2f}, max {max(areas):.2f} mm2")
    finally:
        gmsh.finalize()

    plate_tris = mesh.Mesh.from_file(plate_stl).vectors.astype(np.float64)
    from overlay_stl import display_triangles

    disp_tris = apply(DISPLAY_TO_PLATE, display_triangles())
    parts = []
    for k, m in enumerate(transforms):
        parts.append((f"plate {k + 1}", PLATE_COLOR, apply(m, plate_tris)))
        parts.append((f"display {k + 1}", DISPLAY_COLOR, apply(m, disp_tris)))
    write_3mf(f"{version}/dodecahedron.3mf", parts)


if __name__ == "__main__":
    main()
