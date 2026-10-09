"""Minimal STEP (ISO-10303-21) entity parser.

Just enough to resolve CARTESIAN_POINT / DIRECTION / AXIS2_PLACEMENT_3D /
CIRCLE chains so we can pull out hole centers and radii without a full
OpenCASCADE / FreeCAD install.
"""
import re


def parse_entities(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    # join continuation lines: STEP statements end with ';'
    text = re.sub(r"\s+", " ", text)
    entities = {}
    for m in re.finditer(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*?)\)\s*;", text):
        eid, etype, args = m.groups()
        entities[int(eid)] = (etype, args)
    return entities


def get_point(entities, ref):
    etype, args = entities[ref]
    assert etype == "CARTESIAN_POINT", etype
    nums = re.search(r"\(([^()]*)\)", args).group(1)
    return tuple(float(x) for x in nums.split(","))


def get_direction(entities, ref):
    etype, args = entities[ref]
    assert etype == "DIRECTION", etype
    nums = re.search(r"\(([^()]*)\)", args).group(1)
    return tuple(float(x) for x in nums.split(","))


def get_axis_placement(entities, ref):
    etype, args = entities[ref]
    assert etype == "AXIS2_PLACEMENT_3D", etype
    parts = [p.strip() for p in args.split(",")]
    loc_ref = int(parts[1].lstrip("#"))
    axis_ref = int(parts[2].lstrip("#")) if parts[2].strip() != "$" else None
    refdir_ref = int(parts[3].lstrip("#")) if parts[3].strip() != "$" else None
    loc = get_point(entities, loc_ref)
    axis = get_direction(entities, axis_ref) if axis_ref else (0, 0, 1)
    refdir = get_direction(entities, refdir_ref) if refdir_ref else (1, 0, 0)
    return loc, axis, refdir


def get_circles(entities):
    circles = []
    for eid, (etype, args) in entities.items():
        if etype != "CIRCLE":
            continue
        parts = [p.strip() for p in args.split(",")]
        axis_ref = int(parts[1].lstrip("#"))
        radius = float(parts[2])
        loc, axis, refdir = get_axis_placement(entities, axis_ref)
        circles.append({"id": eid, "center": loc, "axis": axis, "refdir": refdir, "radius": radius})
    return circles
