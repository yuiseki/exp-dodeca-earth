"""Build plate v0.0.3 from v0.0.2: bevel the five sides so that twelve
plates close into a regular dodecahedron.

Adjacent faces of a regular dodecahedron meet at arccos(-1/sqrt(5)) =
116.565 deg, so each side wall lies on the bisector, at half that angle
(58.28 deg) to the outer face. tan(58.28 deg) is exactly the golden
ratio, so at depth z into the plate the outline is inset by z / phi:
1.236mm on the inner face of the 2mm plate.

The outer face is z=0, where the display's PCB sits (screens face out);
it keeps the 30mm edges. The inner face z=2, where the connector pokes
through, faces the dodecahedron's center.

After the bevel the walls on the inner face are 0.82mm outside the two
holes nearest the apex, and 1.12mm at the slot's apex-side corners.

Run from this directory with the project venv:
    ../../../.venv/bin/python build.py
"""
import math

import gmsh

SRC = "../v0.0.2/lcd_pentagon_plate.step"
THICKNESS = 2.0
PHI = (1 + math.sqrt(5)) / 2


def outer_vertices():
    """The 5 pentagon corners on the outer face z=0, in order."""
    pts = []
    for _, tag in gmsh.model.getEntities(0):
        x, y, z = gmsh.model.getValue(0, tag, [])
        if abs(z) < 1e-9 and math.hypot(x, y) > 20:
            pts.append((x, y))
    assert len(pts) == 5, pts
    cx = sum(p[0] for p in pts) / 5
    cy = sum(p[1] for p in pts) / 5
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx)), (cx, cy)


def pentagon_wire(corners, center, inradius, z):
    """Pentagon at height z whose sides follow the bevel planes."""
    cx, cy = center
    scale = (inradius - z / PHI) / inradius
    pts = [gmsh.model.occ.addPoint(cx + (x - cx) * scale, cy + (y - cy) * scale, z) for x, y in corners]
    lines = [gmsh.model.occ.addLine(pts[i], pts[(i + 1) % 5]) for i in range(5)]
    return gmsh.model.occ.addWire(lines)


def main():
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        plate = gmsh.model.occ.importShapes(SRC)
        gmsh.model.occ.synchronize()
        corners, center = outer_vertices()
        (ax, ay), (bx, by) = corners[0], corners[1]
        inradius = abs((bx - ax) * (ay - center[1]) - (ax - center[0]) * (by - ay)) / math.hypot(bx - ax, by - ay)

        # Extend the frustum 1mm beyond both faces so no face of it
        # coincides with a face of the plate.
        frustum = gmsh.model.occ.addThruSections(
            [pentagon_wire(corners, center, inradius, -1.0), pentagon_wire(corners, center, inradius, THICKNESS + 1.0)],
            makeSolid=True,
            makeRuled=True,
        )
        result, _ = gmsh.model.occ.intersect(plate, frustum)
        gmsh.model.occ.synchronize()
        assert len(result) == 1 and result[0][0] == 3, result
        print(f"pentagon center {center}, inradius {inradius:.4f}, inner-face inset {THICKNESS / PHI:.4f}")
        print(f"volume {gmsh.model.occ.getMass(3, result[0][1]):.1f} mm3")
        gmsh.write("lcd_pentagon_plate.step")
        # 72 segments per circle keeps the 3.8mm holes >= 3.796mm across
        # the flats; the 3.5mm standoffs must pass through them.
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 72)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 2.0)
        gmsh.option.setNumber("Mesh.Binary", 1)
        gmsh.model.mesh.generate(2)
        gmsh.write("lcd_pentagon_plate.stl")
    finally:
        gmsh.finalize()
    print("wrote lcd_pentagon_plate.step, lcd_pentagon_plate.stl")


if __name__ == "__main__":
    main()
