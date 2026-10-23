"""Check the routed board (rev C, board A) against the design (README.md), independently of make.py.

    ./check.sh      # or: /usr/bin/python3 -m pytest -q test_hub6.py
"""
import math
import os

import pcbnew
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))

# Display cable pins: 1 VCC, 2 GND, 3 DIN, 4 CLK, 5 CS, 6 DC, 7 RST, 8 BL.
SHARED = {"LCD_DIN": 3, "LCD_CLK": 4, "LCD_DC": 6, "LCD_RST": 7, "LCD_BL": 8}
HEADERS = {d: f"J{d + 1}" for d in range(6)}  # display d (plate 1..5, base) -> its holes
# J7 (to board B) by position: (radial distance along 18 degrees, distance along 108 degrees) -> signal.
# Board B's socket (hardware/hub6_xiao) takes the same positions, so this table is the contract between them.
J7 = {(12.5, 5.08): "LCD_DIN", (12.5, 2.54): "LCD_CLK", (12.5, 0.0): "LCD_DC", (12.5, -2.54): "LCD_RST", (12.5, -5.08): "LCD_BL",
      (9.96, 5.08): "GND", (9.96, 2.54): "LCD_A2", (9.96, 0.0): "LCD_A1", (9.96, -2.54): "LCD_A0", (9.96, -5.08): "+3V3"}
# display d -> the U1 output pin that selects it (pin 15 - n is Yn); the firmware's address of display d is 15 - pin
CS_PIN = {0: "13", 1: "14", 2: "15", 3: "10", 4: "11", 5: "12"}
A_IN = 26.0
W_R = 22.0
PLUG = (-8.68, 2.82)  # the base display's plug, from above (simulate/cables.py)


@pytest.fixture(scope="module")
def board():
    return pcbnew.LoadBoard(os.path.join(HERE, "hub6.kicad_pcb"))


@pytest.fixture(scope="module")
def pads(board):
    return {(fp.GetReference(), p.GetNumber()): p.GetNetCode() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNumber()}


def outline_centre(board):
    """The pentagon's centre: the mean of its corners."""
    pts = [d.GetStart() for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    return sum(pcbnew.ToMM(p.x) for p in pts) / len(pts), sum(pcbnew.ToMM(p.y) for p in pts) / len(pts)


def from_above(board, pos):
    """A point on the sheet relative to the outline's centre, y up (seen from above)."""
    cx, cy = outline_centre(board)
    return pcbnew.ToMM(pos.x) - cx, -(pcbnew.ToMM(pos.y) - cy)


def pad_xy(board, ref, num):
    fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
    return from_above(board, next(p for p in fp.Pads() if p.GetNumber() == num).GetPosition())


def j7_pin(board, signal):
    """J7's pin number for a signal, found by position."""
    fp = next(f for f in board.GetFootprints() if f.GetReference() == "J7")
    a, b = math.radians(18), math.radians(108)
    for p in fp.Pads():
        x, y = from_above(board, p.GetPosition())
        u, v = x * math.cos(a) + y * math.sin(a), x * math.cos(b) + y * math.sin(b)
        for (cu, cv), name in J7.items():
            if abs(u - cu) < 0.01 and abs(v - cv) < 0.01 and name == signal:
                return ("J7", p.GetNumber())
    raise KeyError(signal)


def same(pads, a, b):
    return pads[a] == pads[b] and pads[a] != 0


def members(pads, key):
    return sorted(k for k, v in pads.items() if v == pads[key])


def test_j7_has_its_ten_signals_where_board_b_expects_them(board, pads):
    names = board.GetNetsByNetcode()
    for signal in J7.values():
        assert names[pads[j7_pin(board, signal)]].GetNetname() == signal, signal


def test_shared_lines_reach_every_display(board, pads):
    for signal, ph in SHARED.items():
        for j in HEADERS.values():
            assert same(pads, j7_pin(board, signal), (j, str(ph))), (signal, j)


def test_power(board, pads):
    # the displays run on 3V3, not 5V: their level shifter's logic threshold follows VCC
    v3, gnd = j7_pin(board, "+3V3"), j7_pin(board, "GND")
    for j in HEADERS.values():
        assert same(pads, v3, (j, "1"))
        assert same(pads, gnd, (j, "2"))
    for c in ("C2", "C3"):
        assert same(pads, v3, (c, "1"))
        assert same(pads, gnd, (c, "2"))


def test_74hc138_power_and_enables(board, pads):
    """VCC and E3 (active high) on 3V3; E1, E2 (active low) and GND on GND: always enabled."""
    for pin in ("16", "6"):
        assert same(pads, j7_pin(board, "+3V3"), ("U1", pin)), pin
    for pin in ("4", "5", "8"):
        assert same(pads, j7_pin(board, "GND"), ("U1", pin)), pin


def test_address_lines_run_from_j7_to_the_decoder(board, pads):
    for k, signal in enumerate(("LCD_A0", "LCD_A1", "LCD_A2")):
        assert members(pads, ("U1", str(1 + k))) == sorted([("U1", str(1 + k)), j7_pin(board, signal)]), signal


def test_every_display_has_its_own_chip_select_from_a_decoder_output(pads):
    for d, j in HEADERS.items():
        # a chip select touches nothing but its decoder output and its holes
        assert members(pads, (j, "5")) == sorted([(j, "5"), ("U1", CS_PIN[d])]), (d, j)
    assert len({pads[(j, "5")] for j in HEADERS.values()}) == 6
    for pin in ("7", "9"):  # the decoder's Y7 and Y6
        assert members(pads, ("U1", pin)) == [("U1", pin)], pin


def test_two_copper_layers(board):
    assert board.GetCopperLayerCount() == 2


def test_outline_is_a_regular_pentagon_with_its_edges_facing_the_side_plates(board):
    segs = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    assert len(segs) == 5
    lengths = [pcbnew.ToMM(math.hypot(s.GetEnd().x - s.GetStart().x, s.GetEnd().y - s.GetStart().y)) for s in segs]
    assert lengths == pytest.approx([2 * A_IN * math.tan(math.radians(36))] * 5, abs=0.01)
    mids = sorted(math.degrees(math.atan2(*reversed([(a + b) / 2 for a, b in zip(from_above(board, s.GetStart()), from_above(board, s.GetEnd()))]))) % 360 for s in segs)
    assert mids == pytest.approx([54, 126, 198, 270, 342], abs=0.01)  # the cup's five side plates


def test_side_rows_sit_along_the_five_edges_pin_1_counter_clockwise(board):
    for d, theta in enumerate((198, 270, 342, 54, 126)):  # plate 1 .. plate 5
        j = HEADERS[d]
        p1, p8 = pad_xy(board, j, "1"), pad_xy(board, j, "8")
        mid = ((p1[0] + p8[0]) / 2, (p1[1] + p8[1]) / 2)
        assert math.hypot(*mid) == pytest.approx(W_R, abs=0.01), j
        assert math.degrees(math.atan2(mid[1], mid[0])) % 360 == pytest.approx(theta, abs=0.01), j
        assert math.dist(p1, p8) == pytest.approx(7 * 2.54), j
        assert p8[0] * p1[1] - p8[1] * p1[0] > 0, j  # pin 1 is counter-clockwise of pin 8 seen from above


def test_base_holes_are_a_dip8_block_near_the_base_plug(board):
    """J6: 1-4 along the outer row (away from the centre), 5-8 back along the inner one, 8 behind 1;
    within 4mm of the base display's plug, so its wires come straight up."""
    p = {n: pad_xy(board, "J6", str(n)) for n in range(1, 9)}
    for n in (1, 2, 3):
        assert math.dist(p[n], p[n + 1]) == pytest.approx(2.54)
        assert math.dist(p[9 - n], p[8 - n]) == pytest.approx(2.54)
    for n in range(1, 5):
        assert math.dist(p[n], p[9 - n]) == pytest.approx(2.54)
        assert math.hypot(*p[n]) > math.hypot(*p[9 - n])
    centre = (sum(x for x, _ in p.values()) / 8, sum(y for _, y in p.values()) / 8)
    assert math.dist(centre, PLUG) <= 4.0


def test_cable_holes_take_26awg_wire(board):
    """The cables (26 AWG stranded, about 0.5mm copper) are soldered straight in."""
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for j in HEADERS.values():
        for pd in fps[j].Pads():
            if pd.GetNumber():
                assert 0.9 <= pcbnew.ToMM(pd.GetDrillSize().x) <= 1.2, (j, pd.GetNumber())
                assert pd.GetAttribute() == pcbnew.PAD_ATTRIB_PTH


def test_side_rows_have_two_slots_for_a_cable_tie_outside_the_row(board):
    """A 2.5mm cable tie through two slots holds each side cable down beyond its holes."""
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for d in range(5):
        slots = [pd for pd in fps[HEADERS[d]].Pads() if pd.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
        assert len(slots) == 2, d
        for pd in slots:
            sz = sorted((pcbnew.ToMM(pd.GetDrillSize().x), pcbnew.ToMM(pd.GetDrillSize().y)))
            assert sz[0] >= 1.2 and sz[1] >= 2.8, sz
            assert math.hypot(*from_above(board, pd.GetPosition())) > W_R + 1.0


def test_assembled_parts_on_top_and_j7_underneath(board):
    """Economic PCBA places one side only; J7's pins point down into board B's socket."""
    for fp in board.GetFootprints():
        if fp.HasField("LCSC") and fp.GetFieldText("LCSC"):
            assert fp.GetLayer() == pcbnew.F_Cu, fp.GetReference()
    j7 = next(f for f in board.GetFootprints() if f.GetReference() == "J7")
    assert j7.GetLayer() == pcbnew.B_Cu


def test_b_cu_carries_only_the_rings(board):
    """Nothing else runs on B.Cu, so F.Cu lines can cross the rings anywhere: each ring is a
    circle round the centre, 3V3 innermost, and every via on B.Cu sits on its own net's ring
    or inside the innermost one (GND, to the fill there)."""
    rings = {}
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_TRACE_T and t.GetLayer() == pcbnew.B_Cu:
            r = [math.hypot(*from_above(board, p)) for p in (t.GetStart(), t.GetEnd())]
            assert r[0] == pytest.approx(r[1], abs=0.001), t.GetNetname()
            rings.setdefault(t.GetNetname(), set()).add(round(r[0], 2))
    assert all(len(v) == 1 for v in rings.values()), rings
    radius = {k: v.pop() for k, v in rings.items()}
    assert set(radius) == {"+3V3"} | set(SHARED)
    assert min(radius, key=radius.get) == "+3V3"
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            r = math.hypot(*from_above(board, t.GetPosition()))
            if t.GetNetname() in radius:
                assert r == pytest.approx(radius[t.GetNetname()], abs=0.01), t.GetNetname()
            else:
                assert t.GetNetname() == "GND" and r < radius["+3V3"] - 0.5, (t.GetNetname(), r)
    zones = {(board.GetLayerName(z.GetLayer()), z.GetNetname()) for z in board.Zones()}
    assert zones == {("F.Cu", "GND"), ("B.Cu", "GND")}, zones
