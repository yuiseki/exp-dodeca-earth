"""Plan the wiring that make.py draws: which XIAO pad carries which bus signal,
which 74HC138 output goes to which display, and where each chip select crosses
from the inner layer to the top.

    ../../.venv/bin/python assign.py        # needs shapely (the project venv has it); writes layout.json

The board has no autorouter step. Everything is a short straight line:

- The five shared bus signals (DIN, CLK, DC, RST, BL) run from their pad on the
  XIAO's right socket row along the ray from the board's centre out to a via on
  their ring (a circle on In2); the headers do the same.
- The 74HC138 (U1) sits under the XIAO. Its outputs Y0..Y5 each take a via beside
  the chip, run on In2 (free inside radius 12.4) as one straight line to a lane
  via, and from there on F.Cu to pin 5 (CS) of one header.
- A0, A1, A2 come from the left socket row (D7, D8, D9) straight to the chip.

Which pad, which output and where the lane vias go decide whether the lines clear
each other and the socket pads, so this script searches and writes layout.json.
Every item is a copper shape (a pad, a track of its width, a via) and two shapes
of different nets must stay CLEAR apart. test_hub6.py and KiCad's DRC are the
real checks; the geometry here mirrors make.py (copied constants).
"""
import itertools
import json
import math
import os
import sys

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
A_IN = 25.0
HEADER_R = A_IN - 3.3
HEADER_THETA = {d: -18 + 60 * ((d + 4) % 6) for d in range(6)}  # display d (plate 1..5, base) -> header angle
XIAO_PSI = 72 + 90
BUS = {"LCD_DIN": 12.9, "LCD_CLK": 13.7, "LCD_DC": 14.5, "LCD_RST": 15.3, "LCD_BL": 16.1}
BUS_PAD = {"LCD_DIN": 3, "LCD_CLK": 4, "LCD_DC": 6, "LCD_RST": 7, "LCD_BL": 8}
WIDTH, CLEAR, VIA_R, HEADER_PAD_R, SOCKET_PAD_R = 0.2, 0.15, 0.3, 0.7, 0.85
IN2_LIMIT = 12.4  # the bus rings start at 12.9 - 0.1; inside this radius In2 is free

# U1 in the XIAO's frame (x right, y toward the USB-C): pad rows at x = +-2.7, pitch 1.27.
# Right side pins 15..9 are Y0..Y6 (y = -3.175 ... 4.445). Their vias sit 1.8 outward of the pads.
Y_PIN_LOCAL_Y = {15: -3.175, 14: -1.905, 13: -0.635, 12: 0.635, 11: 1.905, 10: 3.175, 9: 4.445}
Y_VIA_X = 4.5
# the other vias around the chip and the capacitors (XIAO frame): VCC, E1/E2, GND, E3, C2 (10uF 0805), C3 (100nF 0603)
MISC_VIAS_LOCAL = [(4.5, -4.445), (-4.0, -0.635), (-4.0, 4.445), (-4.0, 1.905),
                   (-2.45, -6.9), (2.45, -6.9), (-2.275, 6.9), (2.275, 6.9)]
LANE_R = (11.2, 11.6, 12.0)
LANE_DELTA = range(-14, 15)  # degrees either side of the header's pad-5 direction


def polar(r, theta):
    t = math.radians(theta)
    return (r * math.cos(t), -r * math.sin(t))


def xiao_frame(lx, ly):
    c, s = math.cos(math.radians(XIAO_PSI)), math.sin(math.radians(XIAO_PSI))
    return (lx * c + ly * s, -lx * s + ly * c)


def header_pad(d, pin):
    """Pad position of header d, pin 1..8 (pin 1 at the counter-clockwise end)."""
    theta = HEADER_THETA[d]
    cx, cy = polar(HEADER_R, theta)
    phi = math.radians(theta + 90)
    lx = 7 - 2 * (pin - 1)
    return (cx + lx * math.cos(phi), cy - lx * math.sin(phi))


def ray_via(pad, radius):
    r = math.hypot(*pad)
    return (pad[0] / r * radius, pad[1] / r * radius)


def pad(p, r):
    return Point(p).buffer(r, 8)


def track(a, b):
    return LineString([a, b]).buffer(WIDTH / 2, 4)


def via(p):
    return Point(p).buffer(VIA_R, 8)


# XIAO signal pads: J7 (right row) D0..D6, J8 (left row) D7..D10
RIGHT_ROW = {f"D{k}": xiao_frame(7.62, 7.62 - 2.54 * k) for k in range(7)}
LEFT_ROW = {f"D{7 + k}": xiao_frame(-7.62, -7.62 + 2.54 * k) for k in range(4)}
SOCKET_PADS = [xiao_frame(7.62, 7.62 - 2.54 * k) for k in range(7)] + [xiao_frame(-7.62, -7.62 + 2.54 * k) for k in range(7)]
MISC_VIAS = [xiao_frame(*p) for p in MISC_VIAS_LOCAL]


def header_copper():
    """Top-layer copper of the six headers: every pad, and the five bus stubs with their vias."""
    shapes = []
    for d in range(6):
        for pin in range(1, 9):
            shapes.append((pad(header_pad(d, pin), HEADER_PAD_R), f"J{d + 1}.{pin}"))
        for name, pin in BUS_PAD.items():
            p = header_pad(d, pin)
            v = ray_via(p, BUS[name])
            shapes.append((track(p, v), f"J{d + 1}.{pin}"))
            shapes.append((via(v), f"J{d + 1}.{pin}"))
    return shapes


HEADER_COPPER = header_copper()
SOCKET_COPPER = [(pad(p, SOCKET_PAD_R), "socket") for p in SOCKET_PADS]


def bus_copper(assign):
    """The XIAO's bus stubs: (shape, owner pad position)."""
    shapes = []
    for name, pin in assign.items():
        p = RIGHT_ROW[pin]
        v = ray_via(p, BUS[name])
        shapes.append((track(p, v), p))
        shapes.append((via(v), p))
    return shapes


def valid_bus_assignments():
    """Assignments of the five bus signals to right-row pads whose stubs and vias clear everything."""
    names = list(BUS)
    out = []
    for pins in itertools.permutations(RIGHT_ROW, len(names)):
        assign = dict(zip(names, pins))
        mine = bus_copper(assign)
        ok = True
        for shape, own in mine:
            for other, _ in HEADER_COPPER:
                if shape.distance(other) < CLEAR:
                    ok = False
            for other, label in SOCKET_COPPER:
                if other.buffer(0.01).contains(Point(own)):
                    continue  # its own pad
                if shape.distance(other) < CLEAR:
                    ok = False
        for (s1, o1), (s2, o2) in itertools.combinations(mine, 2):
            if o1 != o2 and s1.distance(s2) < CLEAR:
                ok = False
        if ok:
            out.append(assign)
    return out


def lane_candidates(d, xiao_copper):
    """Lane vias for header d: (cost, via position, F.Cu line to pad 5) that clear the top-layer copper."""
    target = header_pad(d, 5)
    ang0 = math.degrees(math.atan2(-target[1], target[0]))
    mine = f"J{d + 1}.5"
    out = []
    for r in LANE_R:
        for delta in LANE_DELTA:
            v = polar(r, ang0 + delta)
            line = track(v, target)
            vc = via(v)
            ok = True
            for shape, label in HEADER_COPPER:
                if label != mine and (line.distance(shape) < CLEAR or vc.distance(shape) < CLEAR):
                    ok = False
                    break
            if ok:
                for shape, _ in SOCKET_COPPER:
                    if line.distance(shape) < CLEAR or vc.distance(shape) < CLEAR:
                        ok = False
                        break
            if ok:
                for shape, _ in xiao_copper:
                    if line.distance(shape) < CLEAR or vc.distance(shape) < CLEAR:
                        ok = False
                        break
            if ok:
                out.append((abs(delta) + 0.3 * (r - 11.2), v, line))
    out.sort(key=lambda c: c[0])
    return out


def gap_waypoints():
    """Centres of the gaps between neighbouring pads of the two socket rows (In2 lines can pass there)."""
    pts = []
    for sx in (7.62, -7.62):
        for k in range(6):
            pts.append(xiao_frame(sx, -6.35 + 2.54 * k))
    return pts


WAYPOINTS = gap_waypoints()
TWELVE = [math.pi / 12 + k * math.pi / 6 for k in range(12)]


def disc_polygon(c, r):
    """A 12-sided polygon round the circle (c, r): a line that avoids it keeps r clear of c."""
    rr = r / math.cos(math.pi / 12)
    return Polygon([(c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)) for a in TWELVE])


class In2Router:
    """Shortest In2 paths inside the free disc, as polylines through the corners of the obstacles
    (a visibility graph). The static obstacles are fixed; paths placed earlier are added per query."""

    def __init__(self, sources):
        self.sources = sources
        self.static = [(p, 0.85 + CLEAR + WIDTH / 2) for p in SOCKET_PADS] + [(p, VIA_R + CLEAR + WIDTH / 2) for p in MISC_VIAS]
        self.src_poly = [disc_polygon(p, VIA_R + CLEAR + WIDTH / 2) for p in sources]
        self.polys = [disc_polygon(c, r) for c, r in self.static]
        self.nodes = list(WAYPOINTS)
        for poly in self.polys + self.src_poly:
            self.nodes += [q for q in poly.exterior.coords[:-1] if math.hypot(*q) <= IN2_LIMIT]
        self.nodes += list(sources)
        self.visible = {}
        self.static_shape = prep(unary_union(self.polys).buffer(-1e-4))
        self.src_shrunk = [pl.buffer(-1e-4) for pl in self.src_poly]

    @staticmethod
    def _clear(a, b, obstacles):
        seg = LineString([a, b])
        return not any(o.intersects(seg) for o in obstacles)

    def route(self, i, target, placed):
        """Path from source i to target, or None. `placed` are earlier paths (LineStrings)."""
        others = [prep(pl) for j, pl in enumerate(self.src_shrunk) if j != i]
        dyn = [prep(pl.buffer(WIDTH + CLEAR - 1e-4)) for pl in placed]
        nodes = self.nodes + [target]
        src = self.sources[i]
        dist = {src: 0.0}
        prev = {}
        queue = [(0.0, src)]
        done = set()
        import heapq
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
                    self.visible[key] = self._clear(u, v, [self.static_shape])
                if not self.visible[key]:
                    continue
                if not self._clear(u, v, others + dyn):
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


def solve(bus_assign, y_pins, per_display=10):
    xiao_copper = bus_copper(bus_assign) if bus_assign else []
    ysrc = [xiao_frame(Y_VIA_X, Y_PIN_LOCAL_Y[p]) for p in y_pins]
    cands = {d: lane_candidates(d, xiao_copper)[:per_display] for d in range(6)}
    if any(not c for c in cands.values()):
        return None
    router = In2Router(ysrc)
    chosen = {}

    def compatible(c, o):
        _, va, fa, la = c
        _, vb, fb, lb = o[:4]
        vca, vcb = via(va), via(vb)
        return not (fa.distance(fb) < CLEAR or vca.distance(vcb) < CLEAR
                    or la.distance(lb) < CLEAR or la.distance(vcb) < CLEAR or lb.distance(vca) < CLEAR
                    or fa.distance(vcb) < CLEAR or fb.distance(vca) < CLEAR)

    def rec(i, used):
        if i == 6:
            return True
        for d in range(6):
            if d in used:
                continue
            for cost, v, fline in cands[d]:
                placed = [c[3] for c in chosen.values()]
                path = router.route(i, v, placed)
                if path is None:
                    continue
                line = LineString(path).buffer(WIDTH / 2, 4)
                entry = (cost, v, fline, line)
                if any(not compatible(entry, o) for o in chosen.values()):
                    continue
                chosen[i] = entry + (d, path)
                used.add(d)
                if rec(i + 1, used):
                    return True
                used.discard(d)
                del chosen[i]
        return False

    if not rec(0, set()):
        return None
    return {y_pins[i]: {"display": c[4], "lane_via": c[1], "in2": c[5]} for i, c in chosen.items()}


def main():
    y_pins = (15, 14, 13, 12, 11, 10)
    plan = solve(None, y_pins, per_display=6)
    if not plan:
        print("no plan for the chip selects")
        return 1
    # the chip-select lanes first (they only have to clear the headers and sockets), then a bus assignment whose
    # XIAO stubs clear them
    lanes = []
    for pin, v in plan.items():
        d = v["display"]
        lanes.append(track(v["lane_via"], header_pad(d, 5)))
        lanes.append(via(v["lane_via"]))
    buses = valid_bus_assignments()
    ok = [b for b in buses if all(s.distance(l) >= CLEAR for s, _ in bus_copper(b) for l in lanes)]
    print(f"{len(buses)} bus assignments clear the headers, {len(ok)} of them also the chip-select lanes", flush=True)
    if not ok:
        print("no bus assignment fits")
        return 1
    bus = ok[0]
    print(f"bus: {bus}\n  U1 pins {y_pins}")
    for pin, v in plan.items():
        print(f"  pin {pin} -> display {v['display']} lane via {tuple(round(c, 2) for c in v['lane_via'])} In2 {[tuple(round(c, 2) for c in q) for q in v['in2']]}")
    with open(os.path.join(HERE, "layout.json"), "w") as f:
        json.dump({"bus": bus, "y": {str(p): v for p, v in plan.items()}}, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
