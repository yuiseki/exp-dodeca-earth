"""Plan the wiring that make.py draws: which ring each shared signal runs on, which
74HC138 output goes to which display, and where each chip select crosses from the
inner layer to the top.

    ../../.venv/bin/python assign.py        # needs shapely (the project venv has it); writes layout.json

The board has no autorouter step. Every connection is a short straight line:

- The display cables are soldered straight into rows of eight holes. The five side
  displays' rows (W) sit along the pentagon's edges; the base display's row (F) sits
  just outside the XIAO's right socket row, its pins 3..8 level with the XIAO's D0..D5.
- The five shared signals (DIN, CLK, DC, RST, BL) each have a ring (a circle on In2).
  Every W row and the F row reach the rings by radial stubs on F.Cu, from the pad out
  (F) or in (W) to a via on the ring. The XIAO's pads for them sit level with the F
  row's pads and join them by a 2.88mm line, so the XIAO reaches the rings through F.
- The 74HC138 (U1) sits under the XIAO. Its outputs Y0..Y5 each take a via beside the
  chip and run on In2 (free inside the rings) to a lane via, and from there on F.Cu to
  pin 5 (CS) of a W row; the base display's chip select ends on In2 at F's pin 5.
- A0, A1, A2 come from the left socket row (D7, D8, D9) straight to the chip.

Which ring each signal takes decides whether the F and W stubs clear each other, and
which output and lane each chip select takes decides whether the In2 lines clear the
pads, so this script searches and writes layout.json. Every item is a copper shape
(a pad, a track of its width, a via); shapes of different nets stay CLEAR apart.
test_hub6.py and KiCad's DRC are the real checks; the geometry here mirrors make.py
(copied constants).
"""
import heapq
import itertools
import json
import math
import os
import sys

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

HERE = os.path.dirname(os.path.abspath(__file__))
W_THETA = [198, 270, 342, 54, 126]  # side display d (plate d + 1) -> the direction of its row
W_R = 22.0                          # W rows: distance of the hole row from the centre
XIAO_PSI = 162                      # the XIAO's right row (local +x) faces 162 degrees, over the base display's plug
F_X, F_Y1 = 10.5, 12.7             # F row in the XIAO frame: x, and y of pin 1 (pin n at F_Y1 - 2.54 (n - 1))
RADII = (17.6, 18.4, 19.2, 20.0, 20.8)
BUS_PAD = {"LCD_DIN": 3, "LCD_CLK": 4, "LCD_DC": 6, "LCD_RST": 7, "LCD_BL": 8}
BUS_XIAO = {"LCD_DIN": "D0", "LCD_CLK": "D1", "LCD_DC": "D3", "LCD_RST": "D4", "LCD_BL": "D5"}  # level with F pins 3, 4, 6, 7, 8
WIDTH, CLEAR, VIA_R, PAD_R = 0.2, 0.15, 0.3, 0.85
SQUARE_R = 0.85 * math.sqrt(2)  # the sockets' pin 1 pads are 1.7mm squares: their corners reach this far
IN2_LIMIT = 17.1  # the innermost ring is at 17.6; inside this radius In2 is free

# U1 in the XIAO's frame (x right, y toward the USB-C): pad rows at x = +-2.7, pitch 1.27.
# Right side pins 15..9 are Y0..Y6 (y = -3.175 ... 4.445). Their vias sit 1.8 outward of the pads.
Y_PIN_LOCAL_Y = {15: -3.175, 14: -1.905, 13: -0.635, 12: 0.635, 11: 1.905, 10: 3.175, 9: 4.445}
Y_VIA_X = 4.5
# the other vias around the chip and the capacitors (XIAO frame): VCC, E1/E2, GND, E3, C2 (10uF 0805), C3 (100nF 0603)
MISC_VIAS_LOCAL = [(4.5, -4.445), (-4.0, -0.635), (-4.0, 4.445), (-4.0, 1.905),
                   (-2.45, -6.9), (2.45, -6.9), (-2.275, 6.9), (2.275, 6.9)]
LANE_R = (16.1, 16.5, 16.9)
LANE_DELTA = range(-12, 13)  # degrees either side of the row's pad-5 direction


def polar(r, theta):
    t = math.radians(theta)
    return (r * math.cos(t), -r * math.sin(t))


def xiao_frame(lx, ly):
    c, s = math.cos(math.radians(XIAO_PSI)), math.sin(math.radians(XIAO_PSI))
    return (lx * c + ly * s, -lx * s + ly * c)


def w_pad(d, pin):
    """Hole of W row d, pin 1..8 (pin 1 at the counter-clockwise end)."""
    cx, cy = polar(W_R, W_THETA[d])
    tx, ty = polar(1.0, W_THETA[d] + 90)
    t = 8.89 - 2.54 * (pin - 1)
    return (cx + t * tx, cy + t * ty)


def f_pad(pin):
    return xiao_frame(F_X, F_Y1 - 2.54 * (pin - 1))


def ray_via(p, radius):
    r = math.hypot(*p)
    return (p[0] / r * radius, p[1] / r * radius)


def disc(p, r):
    return Point(p).buffer(r, 8)


def track(a, b):
    return LineString([a, b]).buffer(WIDTH / 2, 4)


def via(p):
    return disc(p, VIA_R)


def row_net(pin, cs):
    return {1: "+3V3", 2: "GND", 5: cs}.get(pin) or next(n for n, p in BUS_PAD.items() if p == pin)


# XIAO socket pads (J7 right row D0..D6, J8 left row D7..5V) and their nets
RIGHT_ROW = {f"D{k}": xiao_frame(7.62, 7.62 - 2.54 * k) for k in range(7)}
LEFT_ROW = {name: xiao_frame(-7.62, -7.62 + 2.54 * k) for k, name in enumerate(["D7", "D8", "D9", "D10", "3V3", "GND", "5V"])}
SOCKET_NET = {pin: net for net, pin in BUS_XIAO.items()}
SOCKET_NET.update({"D7": "LCD_A0", "D8": "LCD_A1", "D9": "LCD_A2", "3V3": "+3V3", "GND": "GND"})
SOCKET_PADS = list(RIGHT_ROW.values()) + list(LEFT_ROW.values())
SQUARE_PADS = [RIGHT_ROW["D0"], LEFT_ROW["D7"]]  # J7 pin 1 and J8 pin 1
MISC_VIAS = [xiao_frame(*p) for p in MISC_VIAS_LOCAL]


def top_copper(rings):
    """F.Cu shapes that do not depend on the chip selects: (shape, net)."""
    shapes = []
    for name, p in list(RIGHT_ROW.items()) + list(LEFT_ROW.items()):
        shapes.append((disc(p, SQUARE_R if p in SQUARE_PADS else PAD_R), SOCKET_NET.get(name, f"nc {name}")))
    for net, pin in BUS_XIAO.items():
        shapes.append((track(RIGHT_ROW[pin], f_pad(BUS_PAD[net])), net))
    for pin in range(1, 9):
        shapes.append((disc(f_pad(pin), PAD_R), row_net(pin, "LCD_CS5")))
        for d in range(5):
            shapes.append((disc(w_pad(d, pin), PAD_R), row_net(pin, f"LCD_CS{d}")))
    for net, pin in BUS_PAD.items():
        for p in [f_pad(pin)] + [w_pad(d, pin) for d in range(5)]:
            v = ray_via(p, rings[net])
            shapes += [(track(p, v), net), (via(v), net)]
    return shapes


def clashes(shapes):
    for (a, na), (b, nb) in itertools.combinations(shapes, 2):
        if na != nb and a.distance(b) < CLEAR:
            return True
    return False


def ring_orders():
    """Ring radius per shared signal, for every order whose stubs clear each other and the pads."""
    nets = list(BUS_PAD)
    out = []
    for radii in itertools.permutations(RADII):
        rings = dict(zip(nets, radii))
        if not clashes(top_copper(rings)):
            out.append(rings)
    return out


def lane_candidates(d, copper):
    """Lane vias for W row d: (cost, via position, F.Cu line to pad 5) that clear the top-layer copper."""
    target = w_pad(d, 5)
    ang0 = math.degrees(math.atan2(-target[1], target[0]))
    mine = f"LCD_CS{d}"
    out = []
    for r in LANE_R:
        for delta in LANE_DELTA:
            v = polar(r, ang0 + delta)
            line, vc = track(v, target), via(v)
            if all(n == mine or (line.distance(s) >= CLEAR and vc.distance(s) >= CLEAR) for s, n in copper):
                out.append((abs(delta) + 0.3 * (r - LANE_R[0]), v, line))
    out.sort(key=lambda c: c[0])
    return out


def gap_waypoints():
    """Centres of the gaps between neighbouring pads of the two socket rows and of the F row (In2 lines pass there)."""
    pts = []
    for sx in (7.62, -7.62):
        for k in range(6):
            pts.append(xiao_frame(sx, -6.35 + 2.54 * k))
    for k in range(7):
        pts.append(xiao_frame(F_X, F_Y1 - 1.27 - 2.54 * k))
    return pts


WAYPOINTS = gap_waypoints()
TWELVE = [math.pi / 12 + k * math.pi / 6 for k in range(12)]


def disc_polygon(c, r):
    """A 12-sided polygon round the circle (c, r): a line that avoids it keeps r clear of c."""
    rr = r / math.cos(math.pi / 12)
    return Polygon([(c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)) for a in TWELVE])


class In2Router:
    """Shortest In2 paths inside the free disc, as polylines through the corners of the obstacles
    (a visibility graph). The static obstacles are fixed; the sources, the F row's pin 5 (the
    base display's chip select ends there) and paths placed earlier are obstacles per query."""

    def __init__(self, sources, f_cs):
        self.sources = sources
        self.f_cs = f_cs
        pads = SOCKET_PADS + [f_pad(p) for p in range(1, 9) if p != 5]
        static = [(p, (SQUARE_R if p in SQUARE_PADS else PAD_R) + CLEAR + WIDTH / 2) for p in pads]
        static += [(p, VIA_R + CLEAR + WIDTH / 2) for p in MISC_VIAS]
        polys = [disc_polygon(c, r) for c, r in static]
        self.src_poly = [disc_polygon(p, VIA_R + CLEAR + WIDTH / 2) for p in sources]
        self.f_cs_poly = disc_polygon(f_cs, PAD_R + CLEAR + WIDTH / 2)
        self.nodes = list(WAYPOINTS)
        for poly in polys + self.src_poly + [self.f_cs_poly]:
            self.nodes += [q for q in poly.exterior.coords[:-1] if math.hypot(*q) <= IN2_LIMIT]
        self.nodes += list(sources)
        self.visible = {}
        self.static_shape = prep(unary_union(polys).buffer(-1e-4))
        self.src_shrunk = [pl.buffer(-1e-4) for pl in self.src_poly]
        self.f_cs_shrunk = self.f_cs_poly.buffer(-1e-4)

    @staticmethod
    def _clear(a, b, obstacles):
        seg = LineString([a, b])
        return not any(o.intersects(seg) for o in obstacles)

    def route(self, i, target, placed):
        """Path from source i to target, or None. `placed` are earlier paths (LineStrings)."""
        others = [prep(pl) for j, pl in enumerate(self.src_shrunk) if j != i]
        if target != self.f_cs:
            others.append(prep(self.f_cs_shrunk))
        dyn = [prep(pl.buffer(WIDTH + CLEAR - 1e-4)) for pl in placed]
        nodes = self.nodes + [target]
        src = self.sources[i]
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


def solve(copper, y_pins, per_display=8):
    ysrc = [xiao_frame(Y_VIA_X, Y_PIN_LOCAL_Y[p]) for p in y_pins]
    cands = {d: lane_candidates(d, copper)[:per_display] for d in range(5)}
    if any(not c for c in cands.values()):
        return None
    cands[5] = [(0.0, f_pad(5), None)]  # the base display: In2 straight to F's pin 5
    router = In2Router(ysrc, f_pad(5))
    chosen = {}

    def compatible(c, o):
        _, va, fa, la = c
        _, vb, fb, lb = o[:4]
        if fa is None or fb is None:  # F's pin 5 is a pad, not a lane: only the In2 lines can meet it
            return la.distance(lb) >= CLEAR
        vca, vcb = via(va), via(vb)
        return not (fa.distance(fb) < CLEAR or vca.distance(vcb) < CLEAR
                    or la.distance(lb) < CLEAR or la.distance(vcb) < CLEAR or lb.distance(vca) < CLEAR
                    or fa.distance(vcb) < CLEAR or fb.distance(vca) < CLEAR)

    def rec(i, used):
        if i == len(ysrc):
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
    return {y_pins[i]: {"display": c[4], "lane_via": None if c[4] == 5 else c[1], "in2": c[5]}
            for i, c in chosen.items()}


def main():
    orders = ring_orders()
    print(f"{len(orders)} of 120 ring orders clear the stubs", flush=True)
    y_pins = (15, 14, 13, 12, 11, 10)
    for rings in orders:
        plan = solve(top_copper(rings), y_pins)
        if plan:
            break
    else:
        print("no plan for the chip selects")
        return 1
    print(f"rings: {rings}\n  U1 pins {y_pins}")
    for pin, v in plan.items():
        lane = v["lane_via"] and tuple(round(c, 2) for c in v["lane_via"])
        print(f"  pin {pin} -> display {v['display']} lane via {lane} In2 {[tuple(round(c, 2) for c in q) for q in v['in2']]}")
    with open(os.path.join(HERE, "layout.json"), "w") as f:
        json.dump({"rings": rings, "bus": BUS_XIAO, "y": {str(p): v for p, v in plan.items()}}, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
