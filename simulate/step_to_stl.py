"""Convert a STEP file to STL with gmsh, keeping the STEP's own frame.

    ../.venv/bin/python step_to_stl.py IN.step OUT.stl [max_edge_mm]
"""
import sys

import gmsh


def main():
    src, dst = sys.argv[1], sys.argv[2]
    max_edge = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMax", max_edge)
        gmsh.option.setNumber("Mesh.Binary", 1)
        gmsh.model.occ.importShapes(src)
        gmsh.model.occ.synchronize()
        gmsh.model.mesh.generate(2)
        gmsh.write(dst)
    finally:
        gmsh.finalize()
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
