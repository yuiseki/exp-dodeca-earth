"""Write the pentagon plate and the 1.28" LCD module assembled, for
viewing in a slicer or mesh viewer: as one STL, and as a 3MF that keeps
them as two objects with their own colours (STL has no colour).

The display STEP is meshed with gmsh (which bundles OpenCASCADE), mapped
into the plate frame with the same -90 deg rotation as overlay.py, and
the plate is lifted to sit flush on the PCB's back face (z=0.45 in the
display STEP), with the brass standoffs and the connector passing
through it.

Run from simulate/ with the project venv (deps in requirements.txt):
    ../.venv/bin/python overlay_stl.py v0.0.2
"""
import os
import sys
import zipfile
from collections import Counter

import gmsh
import numpy as np
from stl import mesh

DISPLAY_STEP = (
    "../3d/display/1.28inch_LCD_Module_3D_Drawing/"
    "1.28inch LCD Module 3D Drawing/0508.stp"
)
PLATE_COLOR = "#F28C28FF"
DISPLAY_COLOR = "#1F5FBFFF"

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


def indexed(tris):
    keys = np.round(tris.reshape(-1, 3), 5)
    verts, inverse = np.unique(keys, axis=0, return_inverse=True)
    return verts, inverse.reshape(-1, 3)


def check_closed_and_outward(name, verts, faces):
    directed = Counter()
    for a, b, c in faces:
        directed.update(((a, b), (b, c), (c, a)))
    bad = [e for e, n in directed.items() if n != 1 or directed.get((e[1], e[0]), 0) != 1]
    if bad:
        raise ValueError(f"{name}: {len(bad)} edges are open or inconsistently wound")
    p = verts[faces]
    volume = np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6
    if volume <= 0:
        raise ValueError(f"{name}: faces point inward (volume {volume:.1f})")
    print(f"{name}: closed, outward, volume {volume:.1f} mm3")


def write_3mf(path, parts):
    materials = "".join(f'<base name="{name}" displaycolor="{color}"/>' for name, color, _ in parts)
    objects, items = [], []
    for i, (name, _, tris) in enumerate(parts):
        verts, faces = indexed(tris)
        check_closed_and_outward(name, verts, faces)
        vs = "".join(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in verts)
        ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
        oid = i + 2
        objects.append(
            f'<object id="{oid}" name="{name}" type="model" pid="1" pindex="{i}">'
            f"<mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>"
        )
        items.append(f'<item objectid="{oid}"/>')
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources><basematerials id="1">{materials}</basematerials>{"".join(objects)}</resources>'
        f'<build>{"".join(items)}</build></model>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
    print(f"wrote {path}")


def main():
    version = sys.argv[1]
    os.makedirs(version, exist_ok=True)
    plate_stl = f"../3d/pentagon/{version}/lcd_pentagon_plate.stl"
    out_stl = f"{version}/overlay.stl"
    out_3mf = f"{version}/overlay.3mf"

    disp = display_triangles()
    x, y, z = disp[..., 0].copy(), disp[..., 1].copy(), disp[..., 2].copy()
    disp[..., 0], disp[..., 1], disp[..., 2] = y, -x, z

    plate = mesh.Mesh.from_file(plate_stl).vectors.astype(np.float64)
    plate[..., 2] += PCB_BACK_Z

    for name, v in (("display", disp), ("plate", plate)):
        print(f"{name}: {len(v)} triangles, min {v.reshape(-1, 3).min(0).round(2)}, max {v.reshape(-1, 3).max(0).round(2)}")

    tris = np.concatenate([disp, plate])
    out = mesh.Mesh(np.zeros(len(tris), dtype=mesh.Mesh.dtype))
    out.vectors = tris
    out.save(out_stl)
    print(f"wrote {out_stl} ({len(tris)} triangles)")

    write_3mf(out_3mf, [("plate", PLATE_COLOR, plate), ("display", DISPLAY_COLOR, disp)])


if __name__ == "__main__":
    main()
