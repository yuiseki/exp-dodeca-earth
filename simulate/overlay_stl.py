"""Write a single STL with the pentagon plate and the 1.28" LCD module
assembled, for viewing in a slicer or mesh viewer.

The display STEP is meshed with gmsh (which bundles OpenCASCADE), mapped
into the plate frame with the same -90 deg rotation as overlay.py, and
the plate is lifted to sit flush on the PCB's back face (z=0.45 in the
display STEP), with the brass standoffs and the connector passing
through it.

Run from simulate/ with the project venv (deps in requirements.txt):
    ../.venv/bin/python overlay_stl.py
"""
import gmsh
import numpy as np
from stl import mesh

PLATE_STL = "../3d/pentagon/v0.0.1/lcd_pentagon_plate.stl"
DISPLAY_STEP = (
    "../3d/display/1.28inch_LCD_Module_3D_Drawing/"
    "1.28inch LCD Module 3D Drawing/0508.stp"
)
OUT = "v0.0.1/overlay.stl"

PCB_BACK_Z = 0.45


def display_triangles():
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 1.0)
        gmsh.model.occ.importShapes(DISPLAY_STEP)
        gmsh.model.occ.synchronize()
        gmsh.model.mesh.generate(2)
        node_tags, coords, _ = gmsh.model.mesh.getNodes()
        xyz = coords.reshape(-1, 3)
        index = {tag: i for i, tag in enumerate(node_tags)}
        _, elem_nodes = gmsh.model.mesh.getElementsByType(2)
        tris = np.array([index[t] for t in elem_nodes]).reshape(-1, 3)
        return xyz[tris]
    finally:
        gmsh.finalize()


def main():
    disp = display_triangles()
    x, y, z = disp[..., 0].copy(), disp[..., 1].copy(), disp[..., 2].copy()
    disp[..., 0], disp[..., 1], disp[..., 2] = y, -x, z

    plate = mesh.Mesh.from_file(PLATE_STL).vectors.astype(np.float64)
    plate[..., 2] += PCB_BACK_Z

    for name, v in (("display", disp), ("plate", plate)):
        print(f"{name}: {len(v)} triangles, min {v.reshape(-1, 3).min(0).round(2)}, max {v.reshape(-1, 3).max(0).round(2)}")

    tris = np.concatenate([disp, plate])
    out = mesh.Mesh(np.zeros(len(tris), dtype=mesh.Mesh.dtype))
    out.vectors = tris
    out.save(OUT)
    print(f"wrote {OUT} ({len(tris)} triangles)")


if __name__ == "__main__":
    main()
