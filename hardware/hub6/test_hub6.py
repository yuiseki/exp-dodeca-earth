"""Check the routed board against the design (README.md), independently of make.py.

    /usr/bin/python3 -m pytest -q test_hub6.py
"""
import math
import os

import pcbnew
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))

# XIAO pin -> display cable pin, shared by all six displays (pins: 1 VCC, 2 GND, 3 DIN, 4 CLK, 5 CS, 6 DC, 7 RST, 8 BL).
# Which pin carries which signal is README.md's table: the base display's row (J6) runs beside the XIAO's
# right socket row, its pins 3, 4, 6, 7, 8 level with D0, D1, D3, D4, D5.
SHARED = {"D0": 3, "D1": 4, "D3": 6, "D4": 7, "D5": 8}
# the XIAO pins that carry the 74HC138's address A0, A1, A2 (U1 pins 1, 2, 3)
ADDRESS = {"D7": "1", "D8": "2", "D9": "3"}
# display d (header J(d+1): plate 1..5, base) -> the U1 output pin that selects it (pin 15 is Y0 ... pin 9 is Y6)
CS_PIN = {0: "15", 1: "14", 2: "13", 3: "12", 4: "10", 5: "11"}
# pins of the XIAO that are not connected
SPARE = ["D2", "D6", "D10"]
# XIAO pin -> (socket, pin): J7 takes XIAO pins 1-7 (D0-D6), J8 pins 8-14 (D7-D10, 3V3, GND, 5V)
_XIAO_NUMBER = {"D0": 1, "D1": 2, "D2": 3, "D3": 4, "D4": 5, "D5": 6, "D6": 7, "D7": 8,
                "D8": 9, "D9": 10, "D10": 11, "3V3": 12, "GND": 13, "5V": 14}
XIAO_PIN = {k: ("J7", str(n)) if n <= 7 else ("J8", str(n - 7)) for k, n in _XIAO_NUMBER.items()}
HEADERS = {d: f"J{d + 1}" for d in range(6)}
A_IN = 26.0
W_R = 22.0  # the side displays' hole rows, from the centre


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
    for c in ("C2", "C3"):
        assert same(pads, XIAO_PIN["3V3"], (c, "1"))
        assert same(pads, XIAO_PIN["GND"], (c, "2"))


def test_74hc138_power_and_enables(pads):
    """VCC and E3 (active high) on 3V3; E1, E2 (active low) and GND on GND: always enabled."""
    pads, _ = pads
    for pin in ("16", "6"):
        assert same(pads, XIAO_PIN["3V3"], ("U1", pin)), pin
    for pin in ("4", "5", "8"):
        assert same(pads, XIAO_PIN["GND"], ("U1", pin)), pin


def test_address_lines_run_from_the_xiao_to_the_decoder(pads):
    pads, _ = pads
    for xiao, u1 in ADDRESS.items():
        assert sorted(k for k, v in pads.items() if v == pads[("U1", u1)]) == sorted([("U1", u1), XIAO_PIN[xiao]]), xiao


def test_every_display_has_its_own_chip_select_from_a_decoder_output(pads):
    pads, _ = pads
    for d, j in HEADERS.items():
        assert same(pads, ("U1", CS_PIN[d]), (j, "5")), (d, j)
        # a chip select touches nothing but its decoder output and its header
        assert sorted(k for k, v in pads.items() if v == pads[(j, "5")]) == sorted([(j, "5"), ("U1", CS_PIN[d])])
    assert len({pads[(j, "5")] for j in HEADERS.values()}) == 6
    assert len(set(CS_PIN.values())) == 6


def test_unused_pins_are_unconnected(pads):
    pads, _ = pads
    for pin in SPARE:
        assert alone(pads, XIAO_PIN[pin]), pin
    for pin in ("7", "9"):  # the decoder's Y7 and Y6
        assert alone(pads, ("U1", pin)), pin
    assert len(SHARED) + len(ADDRESS) + len(SPARE) == 11  # D0-D10, none twice
    assert not set(SHARED) & set(ADDRESS) | set(SHARED) & set(SPARE) | set(ADDRESS) & set(SPARE)


def test_xiao_sockets_are_two_rows_15_24_apart_with_d0_and_5v_at_the_usb_end(pads):
    _, board = pads
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    pad = {(r, p.GetNumber()): p.GetPosition() for r in ("J7", "J8") for p in fps[r].Pads()}
    d0, d6, d7, v5 = pad[("J7", "1")], pad[("J7", "7")], pad[("J8", "1")], pad[("J8", "7")]
    dist = lambda a, b: pcbnew.ToMM(math.hypot(a.x - b.x, a.y - b.y))
    assert dist(d0, v5) == pytest.approx(15.24)  # D0 and 5V face each other across the XIAO
    assert dist(d0, d6) == pytest.approx(15.24)  # a row is 6 pitches long
    assert dist(v5, d7) == pytest.approx(15.24)
    # D0 and 5V are the pins at the USB-C end: the XIAO's USB-C points at 72 degrees
    mid = pcbnew.VECTOR2I((d0.x + v5.x) // 2, (d0.y + v5.y) // 2)
    centre = pcbnew.VECTOR2I((d0.x + d6.x + d7.x + v5.x) // 4, (d0.y + d6.y + d7.y + v5.y) // 4)
    angle = math.degrees(math.atan2(-(mid.y - centre.y), mid.x - centre.x)) % 360
    assert angle == pytest.approx(72, abs=0.01)


def outline_centre(board):
    """The pentagon's centre: the mean of its corners."""
    pts = [d.GetStart() for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    return sum(pcbnew.ToMM(p.x) for p in pts) / len(pts), sum(pcbnew.ToMM(p.y) for p in pts) / len(pts)


def test_outline_is_a_regular_pentagon_with_its_edges_facing_the_side_plates(pads):
    _, board = pads
    segs = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    assert len(segs) == 5
    lengths = [pcbnew.ToMM(math.hypot(s.GetEnd().x - s.GetStart().x, s.GetEnd().y - s.GetStart().y)) for s in segs]
    side = 2 * A_IN * math.tan(math.radians(36))
    assert lengths == pytest.approx([side] * 5, abs=0.01)
    cx, cy = outline_centre(board)
    mids = sorted(math.degrees(math.atan2(-((pcbnew.ToMM(s.GetStart().y) + pcbnew.ToMM(s.GetEnd().y)) / 2 - cy),
                                          (pcbnew.ToMM(s.GetStart().x) + pcbnew.ToMM(s.GetEnd().x)) / 2 - cx)) % 360 for s in segs)
    assert mids == pytest.approx([54, 126, 198, 270, 342], abs=0.01)  # the cup's five side plates


def pad_xy(board, ref, num):
    """Pad position relative to the outline's centre, y up (seen from above)."""
    cx, cy = outline_centre(board)
    fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
    p = next(pd for pd in fp.Pads() if pd.GetNumber() == num).GetPosition()
    return pcbnew.ToMM(p.x) - cx, -(pcbnew.ToMM(p.y) - cy)


def test_side_rows_sit_along_the_five_edges_pin_1_counter_clockwise(pads):
    _, board = pads
    for d, theta in enumerate((198, 270, 342, 54, 126)):  # plate 1 .. plate 5
        j = HEADERS[d]
        p1, p8 = pad_xy(board, j, "1"), pad_xy(board, j, "8")
        mid = ((p1[0] + p8[0]) / 2, (p1[1] + p8[1]) / 2)
        assert math.hypot(*mid) == pytest.approx(W_R, abs=0.01), j
        assert math.degrees(math.atan2(mid[1], mid[0])) % 360 == pytest.approx(theta, abs=0.01), j
        assert math.dist(p1, p8) == pytest.approx(7 * 2.54), j
        assert p8[0] * p1[1] - p8[1] * p1[0] > 0, j  # pin 1 is counter-clockwise of pin 8 seen from above


def test_base_row_runs_beside_the_xiao_level_with_its_pins(pads):
    """J6 (the base display) runs 2.88mm outside the right socket row (0.8mm clear of the socket's body,
    for the iron), each shared pin level with its XIAO pin: the shared lines are short straight links."""
    _, board = pads
    for xiao, ph in SHARED.items():
        assert math.dist(pad_xy(board, *XIAO_PIN[xiao]), pad_xy(board, "J6", str(ph))) == pytest.approx(10.5 - 7.62), xiao
    # over the base display's plug (simulate/cables.py: centre (-8.68, 2.82), long axis at 72 degrees)
    p1, p8 = pad_xy(board, "J6", "1"), pad_xy(board, "J6", "8")
    mid = ((p1[0] + p8[0]) / 2, (p1[1] + p8[1]) / 2)
    assert math.dist(mid, (-8.68, 2.82)) <= 5.0
    assert math.degrees(math.atan2(p1[1] - p8[1], p1[0] - p8[0])) % 180 == pytest.approx(72, abs=0.01)


def test_cable_holes_take_26awg_wire(pads):
    """The cables (26 AWG stranded, about 0.5mm copper) are soldered straight in."""
    _, board = pads
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for j in HEADERS.values():
        for pd in fps[j].Pads():
            if pd.GetNumber():
                assert 0.9 <= pcbnew.ToMM(pd.GetDrillSize().x) <= 1.2, (j, pd.GetNumber())
                assert pd.GetAttribute() == pcbnew.PAD_ATTRIB_PTH


def test_side_rows_have_two_slots_for_a_cable_tie_outside_the_row(pads):
    """A 2.5mm cable tie through two slots holds each side cable down beyond its holes."""
    _, board = pads
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for d in range(5):
        slots = [pd for pd in fps[HEADERS[d]].Pads() if pd.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
        assert len(slots) == 2, d
        for pd in slots:
            sz = sorted((pcbnew.ToMM(pd.GetDrillSize().x), pcbnew.ToMM(pd.GetDrillSize().y)))
            assert sz[0] >= 1.2 and sz[1] >= 2.8, sz
            p = pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)
            cx, cy = outline_centre(board)
            assert math.hypot(p[0] - cx, p[1] - cy) > W_R + 1.0


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


def test_xiao_outline_clears_every_cable_hole(pads):
    """The XIAO sits 8.5mm up, over the middle: every cable hole is outside its outline, for the iron."""
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
            if not pd.GetNumber():
                continue
            sz = pd.GetSize()
            quad = rect(pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y), pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y), -pd.GetOrientationDegrees())
            for o in outline:
                worst = min(worst, poly_dist(o, quad))
    assert worst >= 0.3, f"XIAO outline is {worst:.2f}mm from a cable hole"


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


def test_decoder_and_capacitors_sit_under_the_xiao(pads):
    """U1, C2 and C3 are between the socket rows, under the XIAO (8.5mm up): inside its outline."""
    _, board = pads
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    x1 = fps["X1"]
    cx, cy = pcbnew.ToMM(x1.GetPosition().x), pcbnew.ToMM(x1.GetPosition().y)
    rot = math.radians(x1.GetOrientationDegrees())
    for ref in ("U1", "C2", "C3"):
        for pd in fps[ref].Pads():
            px, py = pcbnew.ToMM(pd.GetPosition().x) - cx, pcbnew.ToMM(pd.GetPosition().y) - cy
            lx = px * math.cos(rot) - py * math.sin(rot)  # back to the XIAO's frame
            ly = px * math.sin(rot) + py * math.cos(rot)
            assert abs(lx) <= 8.95 - 4.0 and abs(ly) <= 10.47 - 2.0, (ref, pd.GetNumber(), lx, ly)


def test_decoder_lines_stay_inside_the_free_part_of_in2(pads):
    """The five bus rings start at radius 17.6 on In2; the chip-select lines run inside 17.1."""
    _, board = pads
    cx, cy = outline_centre(board)
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_TRACE_T and t.GetLayer() == pcbnew.In2_Cu and t.GetNetname().startswith("LCD_CS"):
            for p in (t.GetStart(), t.GetEnd()):
                assert math.hypot(pcbnew.ToMM(p.x) - cx, pcbnew.ToMM(p.y) - cy) <= 17.1 + 1e-6, t.GetNetname()
