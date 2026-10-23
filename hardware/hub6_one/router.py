"""Shortest paths for tracks on one copper layer among round obstacles: a visibility graph through
the corners of 12-sided polygons drawn round each obstacle (a path that avoids the polygon keeps
the obstacle's clearance), plus given waypoints. hub6_one routes the chip selects on B.Cu with it,
inside the rings. Adapted from rev B's assign.py (In2Router).
"""
import heapq
import math

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

TWELVE = [math.pi / 12 + k * math.pi / 6 for k in range(12)]


def disc_polygon(c, r):
    rr = r / math.cos(math.pi / 12)
    return Polygon([(c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)) for a in TWELVE])


class Router:
    """obstacles: [(centre, keep-out radius)] fixed for every query; limit: paths stay inside this
    radius from the origin; extra: optional per-query obstacles (centre, radius), by key."""

    def __init__(self, obstacles, waypoints, limit, width, clear):
        self.width, self.clear, self.limit = width, clear, limit
        polys = [disc_polygon(c, r) for c, r in obstacles]
        self.static = prep(unary_union(polys).buffer(-1e-4))
        self.nodes = [w for w in waypoints if math.hypot(*w) <= limit]
        for poly in polys:
            self.nodes += [q for q in poly.exterior.coords[:-1] if math.hypot(*q) <= limit]
        self.visible = {}

    def _clear(self, a, b, obstacles):
        seg = LineString([a, b])
        return not any(o.intersects(seg) for o in obstacles)

    def route(self, src, target, placed, extra=()):
        """Path from src to target avoiding the static obstacles, `extra` [(centre, radius)] and
        earlier paths `placed` (point lists), or None."""
        ex = [prep(disc_polygon(c, r).buffer(-1e-4)) for c, r in extra]
        ex_nodes = [q for c, r in extra for q in disc_polygon(c, r).exterior.coords[:-1] if math.hypot(*q) <= self.limit]
        dyn = [prep(LineString(p).buffer(self.width + self.clear - 1e-4)) for p in placed]
        nodes = self.nodes + ex_nodes + [target]
        dist = {src: 0.0}
        prev = {}
        queue = [(0.0, src)]
        done = set()
        while queue:
            d, u = heapq.heappop(queue)
            if u in done:
                continue
            done.add(u)
            if u == target:
                break
            for v in nodes:
                if v in done or v == u:
                    continue
                key = (u, v)
                if key not in self.visible:
                    self.visible[key] = self._clear(u, v, [self.static])
                if not self.visible[key] or not self._clear(u, v, ex + dyn):
                    continue
                nd = d + math.dist(u, v)
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(queue, (nd, v))
        if target not in prev:
            return None
        path = [target]
        while path[-1] != src:
            path.append(prev[path[-1]])
        return path[::-1]
