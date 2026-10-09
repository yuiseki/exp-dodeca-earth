"""Trace an ADVANCED_FACE's boundary loops into ordered polylines, with
circular arcs sampled into points, so we can draw the *real* outline of
a face (including any flats / tabs) instead of guessing from a scatter
of vertices.
"""
import re
import math

from parse_step import parse_entities, get_point, get_axis_placement


def _loop_ids(entities, bound_id):
    bt, ba = entities[bound_id]
    loop_ref = int(re.search(r"#(\d+)", ba).group(1))
    lt, la = entities[loop_ref]
    edge_refs = [int(x.lstrip("#")) for x in re.search(r"\(([^()]*)\)", la).group(1).split(",")]
    return edge_refs


def _vertex_point(entities, vid):
    vt, va = entities[vid]
    ref = int(re.search(r"#(\d+)", va).group(1))
    return get_point(entities, ref)


def trace_loop(entities, bound_id, arc_samples=24):
    edge_ids = _loop_ids(entities, bound_id)
    pts = []
    for oe in edge_ids:
        ot, oa = entities[oe]
        m = re.search(r",\*,\*,#(\d+),\.([TF])\.", oa)
        ec_ref = int(m.group(1))
        sense = m.group(2) == "T"
        et, ea = entities[ec_ref]
        parts = [p.strip() for p in ea.split(",")]
        v1, v2 = int(parts[1].lstrip("#")), int(parts[2].lstrip("#"))
        curve_ref = int(parts[3].lstrip("#"))
        p1 = _vertex_point(entities, v1)
        p2 = _vertex_point(entities, v2)
        if not sense:
            p1, p2 = p2, p1
        ct, ca = entities[curve_ref]
        if ct == "LINE":
            pts.append(p1)
        elif ct == "CIRCLE":
            cparts = [p.strip() for p in ca.split(",")]
            axis_ref = int(cparts[1].lstrip("#"))
            radius = float(cparts[2])
            center, axis, refdir = get_axis_placement(entities, axis_ref)
            yaxis = (
                axis[1] * refdir[2] - axis[2] * refdir[1],
                axis[2] * refdir[0] - axis[0] * refdir[2],
                axis[0] * refdir[1] - axis[1] * refdir[0],
            )

            def angle_of(p):
                dx = p[0] - center[0]
                dy = p[1] - center[1]
                dz = p[2] - center[2]
                cx = dx * refdir[0] + dy * refdir[1] + dz * refdir[2]
                cy = dx * yaxis[0] + dy * yaxis[1] + dz * yaxis[2]
                return math.atan2(cy, cx)

            a1 = angle_of(p1)
            a2 = angle_of(p2)
            if a2 <= a1:
                a2 += 2 * math.pi
            for i in range(arc_samples + 1):
                a = a1 + (a2 - a1) * i / arc_samples
                pt = tuple(
                    center[k] + radius * (math.cos(a) * refdir[k] + math.sin(a) * yaxis[k])
                    for k in range(3)
                )
                pts.append(pt)
        else:
            pts.append(p1)
    return pts


def face_bounds(entities, face_id):
    ft, fa = entities[face_id]
    bounds_str = re.search(r"\(([^()]*)\)", fa).group(1)
    return [int(x.lstrip("#")) for x in bounds_str.split(",")]
