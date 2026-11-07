"""dodecahedron.py for the v0.0.6 cups: the displays' bump toward the apex (a vertex), the module at the plate's origin,
the plate's centre where 3d/pentagon/v0.0.6/build.py put it, and variant a's modules 2 mm up.

    ../.venv/bin/python v0_0_6.py a [--quick]     # writes v0.0.6-a/dodecahedron.3mf, _exploded.3mf, magnets.csv
    ../.venv/bin/python v0_0_6.py b [--quick]
"""
import importlib.util
import math
import os
import sys

import numpy as np

import dodecahedron as dd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("build_v006", os.path.join(HERE, "../3d/pentagon/v0.0.6/build.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

variant = sys.argv[1]
edge, rise, s_side, s_pole = B.VARIANTS[variant]
version = f"v0.0.6-{variant}"
R = edge / (2 * math.sin(math.radians(36)))
side_c = np.array([0.0, -s_side, 0.0])
pole_c = np.array([0.0, -s_pole, 0.0])

dd.EDGE = edge
dd.PLATE_CENTER, dd.PLATE_APEX = side_c, side_c + np.array([0.0, R, 0.0])
_plate_to_face = dd.plate_to_face


def plate_to_face(center, normal, vertex):
    """The pole plates (base and top, normal along z) have their own centre."""
    if abs(normal[2]) > 0.99:
        dd.PLATE_CENTER, dd.PLATE_APEX = pole_c, pole_c + np.array([0.0, R, 0.0])
        try:
            return _plate_to_face(center, normal, vertex)
        finally:
            dd.PLATE_CENTER, dd.PLATE_APEX = side_c, side_c + np.array([0.0, R, 0.0])
    return _plate_to_face(center, normal, vertex)


def plate_files(version, roles):
    d = f"../3d/pentagon/{version}"
    return [(f"{d}/lcd_pentagon_plate_pole.step", f"{d}/lcd_pentagon_plate_pole.stl", "cap") if r in ("base", "top")
            else (f"{d}/lcd_pentagon_plate_side.step", f"{d}/lcd_pentagon_plate_side.stl", "side") for r in roles]


dd.plate_to_face = plate_to_face
dd.plate_files = plate_files
# the display's bump (+x in its STEP) toward the plate's apex (+y), its PCB back `rise` mm outside the outer face
dd.DISPLAY_TO_PLATE = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, 0, 1, -dd.PCB_BACK_Z - rise], [0, 0, 0, 1]], float)

if __name__ == "__main__":
    sys.argv = [sys.argv[0], version] + sys.argv[2:]
    dd.main()
