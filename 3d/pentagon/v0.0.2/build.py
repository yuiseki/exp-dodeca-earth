"""Build plate v0.0.2 from v0.0.1: extend the connector slot 3mm toward
the pentagon's apex (+y) so there is room to plug the cable in.

The slot goes from x=+-10.3, y=3.5..11.5 to x=+-10.3, y=3.5..14.5. It
cannot grow sideways: the display's brass standoffs are 1.6mm from the
connector's ends. At the new corners the wall to the plate edge is
about 1.5mm.

Run from this directory with the project venv:
    ../../../.venv/bin/python build.py
"""
import gmsh

SRC = "../v0.0.1/lcd_pentagon_plate.step"
SLOT_X = (-10.3, 10.3)
SLOT_Y = (3.5, 14.5)


def main():
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        plate = gmsh.model.occ.importShapes(SRC)
        x0, x1 = SLOT_X
        y0, y1 = SLOT_Y
        cutter = gmsh.model.occ.addBox(x0, y0, -1, x1 - x0, y1 - y0, 4)
        result, _ = gmsh.model.occ.cut(plate, [(3, cutter)])
        gmsh.model.occ.synchronize()
        assert len(result) == 1 and result[0][0] == 3, result
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
