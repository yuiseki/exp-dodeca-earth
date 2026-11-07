"""Build v0.0.6 cups: the display modules' bump toward a vertex (the equator on the side plates), only each module's
round part kept inside its face (constrains.md, simulate/module_fit/round_contained.py).

    ../../../.venv/bin/python build.py a     # writes ../v0.0.6-a: edge 27.625 mm, modules 2 mm up on rings
    ../../../.venv/bin/python build.py b     # writes ../v0.0.6-b: edge 28.5625 mm, modules on the plate as now

Plate coordinates as in v0.0.3 and simulate/dodecahedron.py: the outer face is z = 0 (outward is -z), the pentagon's
apex toward +y. Unlike v0.0.5, the module's centre is the origin and its bump points to +y (the apex); the connector,
opposite the bump, goes through a slot on the -y side; the four 3.8 mm holes for its brass standoffs are where they
were, (+-13.35, +-9.3), which this turn leaves unchanged. The pentagon is placed around the module as the fit found:
its centre at (0, -s), s being the module's shift toward its bump.

The side plate gets v0.0.4's magnet bosses (v0.0.5's three, at the apex and the two corners at the rim), built by
v0.0.4's code on this plate, with the magnets 4.0 mm from their vertex instead of 5.0; the standoff holes are drilled
again afterwards, through the corner bosses that reach over them (redrill). The pole plate is the same plate without bosses: its bump also points at a vertex.
The cup is v0.0.5's: base plus five side plates, fused, standing on the base's outer face.

Variant a raises each module 2 mm on four rings (5.8 mm across) round its holes, on the plate's outer face. The
module's own brass standoffs (2.4 mm behind its PCB) then stop 0.4 mm into the plate, so the screws from inside need to
be longer than now.
"""
import importlib.util
import json
import math
import os
import sys

import gmsh
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../simulate"))
import dodecahedron as dd  # noqa: E402

PHI = (1 + math.sqrt(5)) / 2
THICKNESS = 2.0
HOLES = [(sx * 13.35, sy * 9.3) for sx in (1, -1) for sy in (1, -1)]
HOLE_R = 1.9
SLOT = (-10.3, 10.3, -13.5, -3.5)      # x0, x1, y0, y1: v0.0.2's slot turned with the module
RING_R = 2.9
MAGNET_T_ALONG = 4.0
VARIANTS = {
    # name: (edge, raise, side shift toward the bump, pole shift)   (round_contained.py, pole "round", side 0, base vertex)
    "a": (27.625, 2.0, 0.0, 0.0),
    "b": (28.5625, 0.0, -0.5, 0.0),
}


def load(name, path):
    """Import an older build.py. v0.0.4's reads its options from sys.argv when imported, so hide ours meanwhile."""
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, sys.argv[:1]
    try:
        spec.loader.exec_module(m)
    finally:
        sys.argv = argv
    return m


def pentagon(edge, cy):
    """Outer-face corners, apex first then round: the pentagon's centre at (0, cy)."""
    R = edge / (2 * math.sin(math.radians(36)))
    return [(R * math.cos(math.radians(90 + 72 * k)), cy + R * math.sin(math.radians(90 + 72 * k))) for k in range(5)], R


def plate_solid(edge, cy, rise):
    occ = gmsh.model.occ
    corners, R = pentagon(edge, cy)
    a = edge / (2 * math.tan(math.radians(36)))
    wires = []
    for z in (0.0, THICKNESS):
        s = (a - z / PHI) / a
        pts = [occ.addPoint(x * s, cy + (y - cy) * s, z) for x, y in corners]
        wires.append(occ.addWire([occ.addLine(pts[i], pts[(i + 1) % 5]) for i in range(5)]))
    body = occ.addThruSections(wires, makeSolid=True, makeRuled=True)
    solid = body
    if rise > 0:
        rings = [(3, occ.addCylinder(x, y, -rise, 0, 0, rise + 0.01, RING_R)) for x, y in HOLES]
        solid, _ = occ.fuse(solid, rings)
    cutters = [(3, occ.addCylinder(x, y, -rise - 1, 0, 0, THICKNESS + rise + 2, HOLE_R)) for x, y in HOLES]
    x0, x1, y0, y1 = SLOT
    cutters.append((3, occ.addBox(x0, y0, -1, x1 - x0, y1 - y0, THICKNESS + 2)))
    solid, _ = occ.cut(solid, cutters)
    occ.synchronize()
    assert len(solid) == 1, solid
    return solid, corners, R


def write_step_stl(dimtags_name):
    gmsh.write(dimtags_name + ".step")
    gmsh.clear()
    gmsh.model.occ.importShapes(dimtags_name + ".step")
    gmsh.model.occ.synchronize()
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 72)
    gmsh.option.setNumber("Mesh.MeshSizeMax", 2.0)
    gmsh.option.setNumber("Mesh.Binary", 1)
    gmsh.model.mesh.generate(2)
    gmsh.write(dimtags_name + ".stl")


def redrill(name, rise):
    """Drill the standoff holes again, through the magnet bosses too (on a small plate a corner boss can reach over a
    hole), and check that each magnet pocket keeps a 0.8 mm wall to every hole."""
    with open(f"magnets_side.json") as f:
        mags = json.load(f)
    worst = math.inf
    for m in mags:
        c, n = np.array(m["face_center"]), np.array(m["normal"])
        for x, y in HOLES:
            # the pocket: a cylinder of radius 1.6 along -n from its face centre, 1.2 deep; sample its axis
            for t in np.linspace(0, 1.2, 7):
                q = c - t * n
                d = math.hypot(q[0] - x, q[1] - y) - HOLE_R - 1.6
                worst = min(worst, d)
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        occ = gmsh.model.occ
        solid = occ.importShapes(name + ".step")
        v0 = sum(occ.getMass(d, t) for d, t in solid)
        cutters = [(3, occ.addCylinder(x, y, -rise - 1, 0, 0, THICKNESS + rise + 8, HOLE_R)) for x, y in HOLES]
        solid, _ = occ.cut(solid, cutters)
        occ.synchronize()
        assert len(gmsh.model.getEntities(3)) == 1
        v1 = sum(occ.getMass(d, t) for d, t in solid)
        print(f"  redrilled the standoff holes through the bosses: removed {v0 - v1:.2f} mm3; "
              f"nearest magnet pocket to a hole {worst:.2f} mm" + (" (THIN)" if worst < 0.8 else ""), flush=True)
        write_step_stl(name)
    finally:
        gmsh.finalize()


def build(variant):
    edge, rise, s_side, s_pole = VARIANTS[variant]
    out = os.path.join(HERE, f"../v0.0.6-{variant}")
    os.makedirs(out, exist_ok=True)
    os.chdir(out)
    cy_side, cy_pole = -s_side, -s_pole
    # the plain plates
    for name, cy in (("pole", cy_pole), ("side_plain", cy_side)):
        gmsh.initialize()
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            solid, corners, R = plate_solid(edge, cy, rise)
            print(f"[{variant}] {name}: edge {edge}, centre (0, {cy:+.2f}), volume {gmsh.model.occ.getMass(3, solid[0][1]):.1f} mm3", flush=True)
            write_step_stl(f"lcd_pentagon_plate_{name}")
        finally:
            gmsh.finalize()
    # magnet bosses on the side plate, by v0.0.4's code
    corners, R = pentagon(edge, cy_side)
    b4 = load("build_v004", os.path.join(HERE, "../v0.0.4/build.py"))
    b4.SRC = "lcd_pentagon_plate_side_plain.step"
    b4.HOLES = HOLES
    b4.SLOT = SLOT
    b4.CENTER = np.array([0.0, cy_side, 0.0])
    names = ["apex", "left", "bottom_left", "bottom_right", "right"]
    b4.P = {n: np.array([x, y, 0.0]) for n, (x, y) in zip(names, corners)}
    b4.VARIANTS["side"] = [("apex", ["right", "left"]), ("right", ["apex"]), ("left", ["apex"])]
    # Magnets 4.0 mm from their vertex (v0.0.4/5: 5.0): on these smaller plates the corner bosses reach the standoff
    # holes, and at 5.0 mm a pocket comes within 0.05 (a) or 0.56 (b) mm of a hole; at 4.0, 1.04 and 1.48 mm. Both
    # cups use the same distance, so the pairs still face each other.
    b4.T_ALONG = MAGNET_T_ALONG
    b4.build("side")
    redrill("lcd_pentagon_plate_side", rise)
    # the cup
    dd.EDGE = edge
    dd.PLATE_CENTER = np.array([0.0, cy_side, 0.0])
    dd.PLATE_APEX = np.array([0.0, cy_side + R, 0.0])
    b5 = load("build_v005", os.path.join(HERE, "../v0.0.5/build.py"))
    placed = dd.two_cups(dd.dodecahedron_faces())
    roles = [r for r, *_ in placed]
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        occ = gmsh.model.occ
        parts, expect = [], 0.0
        for i, (role, c, n, v, _) in enumerate(placed):
            if role not in ("base", "lower"):
                continue
            # the pole plate's own centre differs from the side plate's when the shifts differ
            if role == "base":
                dd.PLATE_CENTER = np.array([0.0, cy_pole, 0.0])
                dd.PLATE_APEX = np.array([0.0, cy_pole + R, 0.0])
            m = dd.plate_to_face(c, n, v)
            dd.PLATE_CENTER = np.array([0.0, cy_side, 0.0])
            dd.PLATE_APEX = np.array([0.0, cy_side + R, 0.0])
            tags = occ.importShapes("lcd_pentagon_plate_pole.step" if role == "base" else "lcd_pentagon_plate_side.step")
            expect += sum(occ.getMass(d, t) for d, t in tags)
            b5.place(tags, m)
            parts.append(tags)
        fused, _ = occ.fuse(parts[0], [t for p in parts[1:] for t in p])
        occ.synchronize()
        flip = np.eye(4)
        flip[2, 3] = edge / 2 * math.sqrt(5 / 2 + 11 / 10 * math.sqrt(5))
        b5.place(fused, flip)
        occ.synchronize()
        solids = gmsh.model.getEntities(3)
        vol = sum(occ.getMass(d, t) for d, t in solids)
        print(f"[{variant}] cup: solids {len(solids)}, volume {vol:.1f} mm3 (6 plates sum to {expect:.1f})", flush=True)
        assert len(solids) == 1 and abs(vol - expect) < 1.0, "fusing changed the material"
        write_step_stl("lcd_cup")
    finally:
        gmsh.finalize()
    b5.report_stl("lcd_pentagon_plate_side.stl")
    b5.report_stl("lcd_pentagon_plate_pole.stl")
    b5.report_stl("lcd_cup.stl")
    with open("variant.json", "w") as f:
        json.dump({"variant": variant, "edge_mm": edge, "raise_mm": rise, "side_shift_mm": s_side, "pole_shift_mm": s_pole,
                   "side_bump": "toward the rim vertex (equator)", "pole_bump": "toward a vertex"}, f, indent=1)


if __name__ == "__main__":
    for v in sys.argv[1:] or VARIANTS:
        build(v)
