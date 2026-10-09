"""Build the v0.0.4 plates from v0.0.3: add magnet bosses.

The 2mm plate cannot be made thicker as a whole: the bevel eats 1/phi mm
per mm of thickness, and the upper screw holes and the slot's apex-side
corners are only ~2mm from the two edges next to the apex. So the plate
stays 2mm and gets small bosses, up to 5.5mm thick, that hold the magnets.

Where the magnets go is fixed by how two plates meet. On a rim edge (the
10 edges between the cups) the lower plate's apex is at one end and the
upper plate's apex at the other, so magnets can only face each other if
they sit at the same distance T from the same end:

- lower plate: a boss at its apex, a magnet T mm along each apex edge;
- upper plate: a boss at each of the two corners the apex edges end in,
  a magnet T mm along the apex edge from that corner.

The middle of the edge would work for both, but the slot's corner is there.
Each magnet gets a boss: a plan-view rectangle beside its edge, ALONG mm
along the edge and DEPTH mm inward, clipped to the bevel planes continued
upward so it stays in the plate's own pyramid. (7.5 x 6.5 is the smallest
that leaves every pocket a full 0.8mm wall and keeps 1.2mm from the screw
holes: a triangle at the vertex either left thin walls or covered a hole.)
Each magnet (3 x 1mm disc) sits in a blind pocket drilled square to
the bevel face, 0.2mm deeper than the magnet, centred in the boss thickness.

The base and top plates carry no magnets: lcd_pentagon_plate_cap.* are
v0.0.3's plate unchanged.

Writes lcd_pentagon_plate_{lower,upper}.step/.stl and magnets_{lower,upper}.json
(pocket positions in plate coordinates, for simulate/dodecahedron.py).

Run from this directory with the project venv:
    ../../../.venv/bin/python build.py [T_ALONG [ALONG [DEPTH]]]
"""
import json
import math
import sys

import gmsh
import numpy as np

SRC = "../v0.0.3/lcd_pentagon_plate.step"
PHI = (1 + math.sqrt(5)) / 2
BOSS_T = 5.5
ALONG = float(sys.argv[2]) if len(sys.argv) > 2 else 7.5
DEPTH = float(sys.argv[3]) if len(sys.argv) > 3 else 6.5
HOLES = [(sx * 13.35, sy * 9.3) for sx in (1, -1) for sy in (1, -1)]
HOLE_R = 1.9
SLOT = (-10.3, 10.3, 3.5, 13.5)
T_ALONG = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
MAGNET_D, MAGNET_T = 3.0, 1.0
POCKET_D, POCKET_L = MAGNET_D + 0.2, MAGNET_T + 0.2
WALL = 0.8
CENTER = np.array([0.0, -1.63, 0.0])
P = {
    "apex": np.array([0.0, 23.88952425056, 0.0]),
    "right": np.array([24.27050983124, 6.255966681787, 0.0]),
    "left": np.array([-24.27050983124, 6.255966681787, 0.0]),
    "bottom_right": np.array([15.0, -22.27572880706, 0.0]),
    "bottom_left": np.array([-15.0, -22.27572880706, 0.0]),
}
VARIANTS = {
    "lower": [("apex", ["right", "left"])],
    "upper": [("right", ["apex"]), ("left", ["apex"])],
}


def pentagon_corners():
    pts = []
    for _, tag in gmsh.model.getEntities(0):
        x, y, z = gmsh.model.getValue(0, tag, [])
        if abs(z) < 1e-9 and math.hypot(x, y) > 20:
            pts.append((x, y))
    assert len(pts) == 5, pts
    cx = sum(p[0] for p in pts) / 5
    cy = sum(p[1] for p in pts) / 5
    return sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx)), (cx, cy)


def frustum(corners, center, inradius, z0, z1):
    occ = gmsh.model.occ
    wires = []
    for z in (z0, z1):
        scale = (inradius - z / PHI) / inradius
        pts = [occ.addPoint(center[0] + (x - center[0]) * scale, center[1] + (y - center[1]) * scale, z) for x, y in corners]
        wires.append(occ.addWire([occ.addLine(pts[i], pts[(i + 1) % 5]) for i in range(5)]))
    return occ.addThruSections(wires, makeSolid=True, makeRuled=True)[0][1]


def inward(vertex, other):
    p0 = P[vertex]
    d = (P[other] - p0) / np.linalg.norm(P[other] - p0)
    u = np.array([d[1], -d[0], 0.0])
    if (p0 - CENTER) @ u < 0:
        u = -u
    return d, -u


def rect_prism(vertex, other, z0, z1):
    """Plan-view rectangle ALONG x DEPTH beside one rim edge, starting 2mm
    before the vertex and 1mm outside the edge; the bevel cone trims it."""
    occ = gmsh.model.occ
    d, inw = inward(vertex, other)
    p0 = P[vertex]
    poly = [p0 + a * d + b * inw for a, b in ((-2.0, -1.0), (ALONG, -1.0), (ALONG, DEPTH), (-2.0, DEPTH))]
    footprint_clearance(f"{vertex}->{other}", poly)
    pts = [occ.addPoint(x, y, z0) for x, y, _ in poly]
    loop = occ.addCurveLoop([occ.addLine(pts[i], pts[(i + 1) % 4]) for i in range(4)])
    out = occ.extrude([(2, occ.addPlaneSurface([loop]))], 0, 0, z1 - z0)
    return [t for dd, t in out if dd == 3][0]


def seg_dist(q, a, b):
    ab = b - a
    t = max(0.0, min(1.0, ((q - a) @ ab) / (ab @ ab)))
    return float(np.linalg.norm(q - (a + t * ab)))


def footprint_clearance(vertex, poly):
    """Plan-view distance from a convex boss footprint to each hole's rim and to the slot."""
    tri = [np.array(t[:2]) for t in poly]
    edges = [(tri[i], tri[(i + 1) % len(tri)]) for i in range(len(tri))]

    def inside(q):
        s = [(b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0]) for a, b in edges]
        return all(x >= 0 for x in s) or all(x <= 0 for x in s)

    worst = math.inf
    for h in HOLES:
        q = np.array(h)
        d = 0.0 if inside(q) else min(seg_dist(q, a, b) for a, b in edges)
        worst = min(worst, d - HOLE_R)
    x0, x1, y0, y1 = SLOT
    corners = [np.array(c) for c in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    slot_d = min(min(seg_dist(c, a, b) for a, b in edges) for c in corners)
    slot_in = any(inside(c) for c in corners) or any(x0 <= t[0] <= x1 and y0 <= t[1] <= y1 for t in tri)
    print(f"  boss at {vertex}: clearance to the nearest hole rim {worst:.2f} mm" + (", COVERS a hole" if worst < 0 else "")
          + f"; to the slot {-slot_d if slot_in else slot_d:.2f} mm" + (" (overlaps)" if slot_in else ""))


def pocket_geometry(vertex, other):
    p0 = P[vertex]
    d, inw = inward(vertex, other)
    u = -inw
    z_face = BOSS_T / 2 + POCKET_L / 2 / math.sqrt(1 + PHI ** 2)
    face = p0 + T_ALONG * d - (z_face / PHI) * u + np.array([0, 0, z_face])
    n = (u + np.array([0, 0, 1 / PHI])) / math.sqrt(1 + 1 / PHI ** 2)
    return face, n


def volume(tag):
    return gmsh.model.occ.getMass(3, tag)


def build(name):
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        occ = gmsh.model.occ
        plate = occ.importShapes(SRC)
        occ.synchronize()
        v_plate = sum(volume(t) for _, t in plate)
        corners, center = pentagon_corners()
        (ax, ay), (bx, by) = corners[0], corners[1]
        inradius = abs((bx - ax) * (ay - center[1]) - (ax - center[0]) * (by - ay)) / math.hypot(bx - ax, by - ay)
        cone = frustum(corners, center, inradius, -1.0, BOSS_T + 1.0)

        solid = plate
        for vertex, others in VARIANTS[name]:
            for other in others:
                boss, _ = occ.intersect([(3, rect_prism(vertex, other, 1.0, BOSS_T))], [(3, cone)], removeTool=False)
                solid, _ = occ.fuse(solid, boss)
        occ.remove([(3, cone)])
        occ.synchronize()
        assert len(solid) == 1 and len(gmsh.model.getEntities(3)) == 1, (solid, gmsh.model.getEntities(3))
        v_blank = volume(solid[0][1])
        blank = occ.copy(solid)
        print(f"[{name}] plate {v_plate:.1f} mm3, with bosses {v_blank:.1f} mm3 (bosses add {v_blank - v_plate:.1f})")

        magnets = []
        for vertex, others in VARIANTS[name]:
            for other in others:
                face, n = pocket_geometry(vertex, other)
                cyl = occ.addCylinder(*(face + 0.5 * n), *(-(0.5 + POCKET_L) * n), POCKET_D / 2)
                solid, _ = occ.cut(solid, [(3, cyl)])
                probe = occ.addCylinder(*face, *(-2.0 * n), POCKET_D / 2 + WALL)
                inside, _ = occ.intersect([(3, probe)], [(3, blank[0][1])], removeObject=True, removeTool=False)
                ratio = sum(volume(t) for _, t in inside) / (math.pi * (POCKET_D / 2 + WALL) ** 2 * 2.0)
                occ.remove(inside, recursive=True)
                print(f"[{name}] pocket at {vertex} toward {other}: material in the {WALL}mm-wall zone behind the face {100 * ratio:.1f}%")
                magnets.append({
                    "vertex": vertex, "toward": other,
                    "face_center": face.tolist(), "normal": n.tolist(),
                    "magnet_base": (face - (POCKET_L - MAGNET_T) * n).tolist(),
                    "magnet_axis": (-MAGNET_T * n).tolist(),
                    "diameter": MAGNET_D, "thickness": MAGNET_T,
                })
        occ.remove([(3, blank[0][1])])
        occ.synchronize()
        assert len(solid) == 1 and len(gmsh.model.getEntities(3)) == 1, (solid, gmsh.model.getEntities(3))
        expect = len(magnets) * math.pi * (POCKET_D / 2) ** 2 * POCKET_L
        print(f"[{name}] pockets removed {v_blank - volume(solid[0][1]):.2f} mm3, expected {expect:.2f} mm3")

        occ.synchronize()
        gmsh.write(f"lcd_pentagon_plate_{name}.step")
        # Mesh the STEP as written: the working model still holds the cut tools.
        gmsh.clear()
        gmsh.model.occ.importShapes(f"lcd_pentagon_plate_{name}.step")
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 72)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 2.0)
        gmsh.option.setNumber("Mesh.Binary", 1)
        gmsh.model.mesh.generate(2)
        gmsh.write(f"lcd_pentagon_plate_{name}.stl")
    finally:
        gmsh.finalize()
    with open(f"magnets_{name}.json", "w") as f:
        json.dump(magnets, f, indent=1)


if __name__ == "__main__":
    for name in VARIANTS:
        build(name)
    print("wrote lcd_pentagon_plate_{lower,upper}.step/.stl and magnets_{lower,upper}.json")
