"""Check the routed board against the design (README.md), independently of make.py.

    /usr/bin/python3 -m pytest -q test_hub6.py
"""
import math
import os

import pcbnew
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))

# XIAO pin -> display PH2.0 pin, shared by all six displays (pins: 1 VCC, 2 GND, 3 DIN, 4 CLK, 5 CS, 6 DC, 7 RST, 8 BL).
# Which pin carries which signal is README.md's table (found by assign.py).
SHARED = {"D2": 3, "D5": 4, "D7": 6, "D8": 7, "D10": 8}
# display d (header J(d+1): plate 1..5, base) -> the XIAO pin that selects it
CS_PIN = {0: "D6", 1: "D3", 2: "D9", 3: "D1", 4: "D0", 5: "D4"}
# XIAO pin -> (socket, pin): J7 takes XIAO pins 1-7 (D0-D6), J8 pins 8-14 (D7-D10, 3V3, GND, 5V)
_XIAO_NUMBER = {"D0": 1, "D1": 2, "D2": 3, "D3": 4, "D4": 5, "D5": 6, "D6": 7, "D7": 8,
                "D8": 9, "D9": 10, "D10": 11, "3V3": 12, "GND": 13, "5V": 14}
XIAO_PIN = {k: ("J7", str(n)) if n <= 7 else ("J8", str(n - 7)) for k, n in _XIAO_NUMBER.items()}
HEADERS = {d: f"J{d + 1}" for d in range(6)}
A_IN = 22.5


@pytest.fixture(scope="module")
def pads():
    board = pcbnew.LoadBoard(os.path.join(HERE, "hub6.kicad_pcb"))
    out = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNumber():
                out[(fp.GetReference(), p.GetNumber())] = p.GetNetCode()
    return out, board


def same(pads, a, b):
    return pads[a] == pads[b] and pads[a] != 0


def alone(pads, key):
    net = pads[key]
    return [k for k, v in pads.items() if v == net] == [key]


def test_shared_lines_reach_every_display(pads):
    pads, _ = pads
    for pin, ph in SHARED.items():
        for j in HEADERS.values():
            assert same(pads, XIAO_PIN[pin], (j, str(ph))), (pin, j, ph)


def test_power(pads):
    pads, _ = pads
    # the displays run on 3V3, not 5V: their level shifter's logic threshold follows VCC
    for j in HEADERS.values():
        assert same(pads, XIAO_PIN["3V3"], (j, "1"))
        assert same(pads, XIAO_PIN["GND"], (j, "2"))
    assert alone(pads, XIAO_PIN["5V"])
    assert same(pads, XIAO_PIN["3V3"], ("C2", "1"))
    assert same(pads, XIAO_PIN["GND"], ("C2", "2"))


def test_every_display_has_its_own_chip_select_straight_from_a_xiao_pin(pads):
    pads, _ = pads
    for d, j in HEADERS.items():
        assert same(pads, XIAO_PIN[CS_PIN[d]], (j, "5")), (d, j)
    assert len({pads[(j, "5")] for j in HEADERS.values()}) == 6
    assert len(set(CS_PIN.values()) | set(SHARED)) == 11  # all of D0-D10, none twice


def test_no_other_connections(pads):
    pads, _ = pads
    for d, j in HEADERS.items():  # a display's CS touches nothing but its XIAO pin
        assert sorted(k for k, v in pads.items() if v == pads[(j, "5")]) == sorted([(j, "5"), XIAO_PIN[CS_PIN[d]]])


def test_xiao_sockets_are_two_rows_15_24_apart_with_d0_and_5v_at_the_usb_end(pads):
    _, board = pads
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    pad = {(r, p.GetNumber()): p.GetPosition() for r in ("J7", "J8") for p in fps[r].Pads()}
    d0, d6, d7, v5 = pad[("J7", "1")], pad[("J7", "7")], pad[("J8", "1")], pad[("J8", "7")]
    dist = lambda a, b: pcbnew.ToMM(math.hypot(a.x - b.x, a.y - b.y))
    assert dist(d0, v5) == pytest.approx(15.24)  # D0 and 5V face each other across the XIAO
    assert dist(d0, d6) == pytest.approx(15.24)  # a row is 6 pitches long
    assert dist(v5, d7) == pytest.approx(15.24)
    # D0 and 5V are the pins at the USB-C end: the XIAO's USB-C points at 72 degrees (a corner)
    mid = pcbnew.VECTOR2I((d0.x + v5.x) // 2, (d0.y + v5.y) // 2)
    centre = pcbnew.VECTOR2I((d0.x + d6.x + d7.x + v5.x) // 4, (d0.y + d6.y + d7.y + v5.y) // 4)
    angle = math.degrees(math.atan2(-(mid.y - centre.y), mid.x - centre.x)) % 360
    assert angle == pytest.approx(72, abs=0.01)


def board_centre(board):
    xs, ys = [], []
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            for p in (d.GetStart(), d.GetEnd()):
                xs.append(pcbnew.ToMM(p.x)); ys.append(pcbnew.ToMM(p.y))
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def test_outline_is_a_regular_hexagon(pads):
    _, board = pads
    segs = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    assert len(segs) == 6
    lengths = [pcbnew.ToMM(math.hypot(s.GetEnd().x - s.GetStart().x, s.GetEnd().y - s.GetStart().y)) for s in segs]
    side = 2 * A_IN / math.sqrt(3)
    assert lengths == pytest.approx([side] * 6, abs=0.01)


def test_headers_sit_on_the_six_edges_60_degrees_apart_pin_1_counter_clockwise(pads):
    pads_, board = pads
    cx, cy = board_centre(board)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    angles = []
    for d, j in HEADERS.items():
        fp = fps[j]
        x, y = pcbnew.ToMM(fp.GetPosition().x) - cx, -(pcbnew.ToMM(fp.GetPosition().y) - cy)
        assert math.hypot(x, y) == pytest.approx(A_IN - 3.3, abs=0.01)
        angles.append(math.degrees(math.atan2(y, x)) % 360)
        p = {pd.GetNumber(): pd.GetPosition() for pd in fp.Pads() if pd.GetNumber()}
        p1 = (pcbnew.ToMM(p["1"].x) - cx, -(pcbnew.ToMM(p["1"].y) - cy))
        p8 = (pcbnew.ToMM(p["8"].x) - cx, -(pcbnew.ToMM(p["8"].y) - cy))
        assert p8[0] * p1[1] - p8[1] * p1[0] > 0, j  # pin 1 is counter-clockwise of pin 8 seen from above
    # plate 1 is the one 222 degrees round, then 282 (plate 2), 342 (plate 3), 42, 102, 162 (the base)
    assert angles == pytest.approx([222, 282, 342, 42, 102, 162], abs=0.01)


def rect(cx, cy, w, h, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(cx + dx * c - dy * s, cy + dx * s + dy * c) for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def seg_dist(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    t = max(0.0, min(1.0, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    return math.hypot(p[0] - (ax + t * (bx - ax)), p[1] - (ay + t * (by - ay)))


def poly_dist(a, b):
    """Distance between two convex polygons that do not overlap."""
    return min([seg_dist(p, b[i], b[(i + 1) % len(b)]) for p in a for i in range(len(b))] +
               [seg_dist(p, a[i], a[(i + 1) % len(a)]) for p in b for i in range(len(a))])


def test_xiao_outline_clears_every_header_pad(pads):
    """The XIAO sits 8.5mm up, over the middle: the plugs above the headers must clear it."""
    _, board = pads
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    x1 = fps["X1"]
    cx, cy = pcbnew.ToMM(x1.GetPosition().x), pcbnew.ToMM(x1.GetPosition().y)
    rot = x1.GetOrientationDegrees()
    # the outline's local rectangles (the board and the USB-C), in the footprint's frame
    body = rect(0, 0.065, 17.9, 21.07, 0)
    usb = rect(0, 11.35, 9.0, 1.5, 0)
    def to_board(pts):
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        return [(cx + x * c + y * s, cy - x * s + y * c) for x, y in pts]
    outline = [to_board(body), to_board(usb)]
    worst = 99.0
    for j in HEADERS.values():
        for pd in fps[j].Pads():
            sz = pd.GetSize()
            quad = rect(pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y), pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y), -pd.GetOrientationDegrees())
            for o in outline:
                worst = min(worst, poly_dist(o, quad))
    assert worst >= 0.5, f"XIAO outline is {worst:.2f}mm from a header pad"


def test_every_assembled_part_is_on_the_top_side(pads):
    """Economic PCBA places one side only."""
    _, board = pads
    for fp in board.GetFootprints():
        if fp.HasField("LCSC") and fp.GetFieldText("LCSC"):
            assert fp.GetLayer() == pcbnew.F_Cu, fp.GetReference()


def test_power_comes_from_the_planes(pads):
    """GND (In1) and +3V3 (B.Cu) are planes: every through-hole pad reaches them
    directly and the surface-mount pads by a via, so power needs no long tracks."""
    _, board = pads
    for net in ("GND", "+3V3"):
        length = sum(pcbnew.ToMM(t.GetLength()) for t in board.GetTracks()
                     if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == net)
        assert length <= 25.0, (net, length)
    zones = {(board.GetLayerName(z.GetLayer()), z.GetNetname()) for z in board.Zones()}
    assert zones == {("In1.Cu", "GND"), ("B.Cu", "+3V3")}, zones
