"""Find which XIAO pin should carry which signal so that every connection can be
drawn as short straight lines on the top layer without crossing anything.

    ../../.venv/bin/python assign.py        # needs shapely (the project venv has it)

The board has no autorouter step. Each shared bus signal (DIN, CLK, DC, RST, BL)
runs from its XIAO socket pad along the ray from the board's centre out to its
ring (a circle on In2) and takes a via there; each select (CS) runs from its
pad to the start of its header's pad-5 lane, then along the lane (also a ray
from the centre) to the header. Whether those lines clear each other depends on
which pad carries which signal, so this script searches for an assignment by
hill climbing on the number of clashes and prints the pin table make.py uses.

The geometry mirrors make.py (copied constants; test_hub6.py and KiCad's DRC are
the real checks).
"""
import itertools
import math
import random
import sys

from shapely.geometry import LineString, Point

A_IN = 22.5
HEADER_R = A_IN - 3.3
HEADER_THETA = {d: -18 + 60 * ((d + 4) % 6) for d in range(6)}  # display d (plate 1..5, base) -> header angle
XIAO_PSI = 72 + 90
BUS = {"LCD_DIN": 12.9, "LCD_CLK": 13.7, "LCD_DC": 14.5, "LCD_RST": 15.3, "LCD_BL": 16.1}
BUS_PAD = {"LCD_DIN": 3, "LCD_CLK": 4, "LCD_DC": 6, "LCD_RST": 7, "LCD_BL": 8}
LANE_START = 11.8  # CS lines run radially from here out to the header
WIDTH, CLEAR, VIA_R, PAD_R, SOCKET_R = 0.2, 0.15, 0.3, 0.7, 0.85


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


# XIAO signal pads: pin name -> position. J7: D0..D6 (pin k at local (7.62, 7.62 - 2.54 (k-1))),
# J8: D7..D10 (pin k at local (-7.62, -7.62 + 2.54 (k-1)))
PADS = {}
for k in range(1, 8):
    PADS[f"D{k - 1}"] = xiao_frame(7.62, 7.62 - 2.54 * (k - 1))
for k in range(1, 5):
    PADS[f"D{6 + k}"] = xiao_frame(-7.62, -7.62 + 2.54 * (k - 1))
OTHER_SOCKET_PADS = [xiao_frame(7.62, 7.62 - 2.54 * k) for k in range(0, 7)] + [xiao_frame(-7.62, -7.62 + 2.54 * k) for k in range(0, 7)]


def route(func, pad):
    """The F.Cu polyline and the via (or None) of one signal from its XIAO pad."""
    if func in BUS:
        r = BUS[func]
        ux, uy = pad[0] / math.hypot(*pad), pad[1] / math.hypot(*pad)
        via = (ux * r, uy * r)
        return LineString([pad, via]), via
    d = int(func[2:])  # "CS3" -> display 3
    theta = HEADER_THETA[d]
    target = header_pad(d, 5)
    ang = math.degrees(math.atan2(-target[1], target[0]))
    q = polar(LANE_START, ang)
    return LineString([pad, q, target]), None


def fixed_obstacles():
    obs = []  # (shapely geometry, clearance radius)
    for d in range(6):
        for pin in range(1, 9):
            obs.append((Point(header_pad(d, pin)).buffer(PAD_R), f"J{d + 1}.{pin}"))
        for name, pin in BUS_PAD.items():
            p = header_pad(d, pin)
            ux, uy = p[0] / math.hypot(*p), p[1] / math.hypot(*p)
            via = (ux * BUS[name], uy * BUS[name])
            obs.append((LineString([p, via]).buffer(WIDTH / 2), f"stub {name} J{d + 1}"))
            obs.append((Point(via).buffer(VIA_R), f"via {name} J{d + 1}"))
    return obs


def clashes(assign):
    """Number of pairs of lines (or a line and an obstacle) closer than the rules allow."""
    lines = {}
    vias = {}
    for func, pin in assign.items():
        ls, via = route(func, PADS[pin])
        lines[func] = ls
        if via:
            vias[func] = Point(via).buffer(VIA_R)
    n = 0
    names = list(lines)
    for a, b in itertools.combinations(names, 2):
        if lines[a].distance(lines[b]) < WIDTH + CLEAR:
            n += 1
        if b in vias and lines[a].distance(vias[b]) < WIDTH / 2 + CLEAR:
            n += 1
        if a in vias and lines[b].distance(vias[a]) < WIDTH / 2 + CLEAR:
            n += 1
        if a in vias and b in vias and vias[a].distance(vias[b]) < CLEAR:
            n += 1
    for func, pin in assign.items():
        own = f"J{int(func[2:]) + 1}.5" if func.startswith("CS") else None
        for g, label in OBS:
            if label == own:
                continue
            if lines[func].distance(g) < WIDTH / 2 + CLEAR:
                n += 1
            if func in vias and vias[func].distance(g) < CLEAR:
                n += 1
        for k, p in enumerate(OTHER_SOCKET_PADS):
            if Point(p).distance(Point(PADS[pin])) < 0.01:
                continue
            if lines[func].distance(Point(p)) < WIDTH / 2 + SOCKET_R + CLEAR:
                n += 1
    return n


OBS = fixed_obstacles()
FUNCS = list(BUS) + [f"CS{d}" for d in range(6)]


def search(seed, iterations=4000):
    rnd = random.Random(seed)
    pins = list(PADS)
    rnd.shuffle(pins)
    assign = dict(zip(FUNCS, pins))
    cost = clashes(assign)
    for _ in range(iterations):
        if cost == 0:
            return assign, 0
        a, b = rnd.sample(FUNCS, 2)
        assign[a], assign[b] = assign[b], assign[a]
        c = clashes(assign)
        if c <= cost:
            cost = c
        else:
            assign[a], assign[b] = assign[b], assign[a]
    return assign, cost


if __name__ == "__main__":
    best = None
    for seed in range(int(sys.argv[1]) if len(sys.argv) > 1 else 40):
        assign, cost = search(seed)
        print(f"seed {seed}: {cost} clashes", flush=True)
        if best is None or cost < best[1]:
            best = (assign, cost)
        if cost == 0:
            break
    assign, cost = best
    print(f"\nbest: {cost} clashes")
    for func in FUNCS:
        print(f"  {func:8s} -> {assign[func]}")
