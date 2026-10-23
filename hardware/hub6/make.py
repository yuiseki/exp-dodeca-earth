"""Generate the hub6 KiCad project: the board that takes the six 1.28 inch round
LCDs (GC9A01, PH2.0 8-pin) of one cup of the dodecahedron (rev C, board A).

    /usr/bin/python3 make.py      # needs KiCad 10's pcbnew module

Rev C is two boards, both 2-layer. This one (A) is a regular pentagon whose
edges face the cup's five side plates: the display cables, a 74HC138 that turns
three address lines into the six chip selects, and a 2x5 pin header (J7) on its
underside. The XIAO ESP32-S3 sits on a small board of its own (hub6_xiao, board
B), whose 2x5 socket takes J7 from below. With the XIAO off this board, its
middle is free, and two layers carry everything:

- B.Cu: one ring (a circle round the centre) per shared signal, 3V3 innermost,
  then DIN, CLK, DC, RST, BL; GND fills the rest of the layer.
- F.Cu: straight lines only, which cross the rings freely. Every cable row
  reaches each ring by a radial stub to a via on it. The chip selects run in
  from the rows to the 74HC138 near the middle, A0..A2 from J7 to the chip. J7
  and the base display's holes (J6) reach the rings through two of the
  pentagon's corners, where no row's stubs are. GND fills the rest.

The display cables (PH2.0 at the display, bare 26 AWG wire at this end) are cut
to length and soldered straight into holes: a row of eight along each edge for
the side displays, coming down from above, and a 2x4 block (J6) for the base
display, coming up from below. Everything JLCPCB places is on the top side.

Writes the schematic, the board with every part placed and every connection
drawn (no autorouter), the project's symbol and footprint libraries and the
library tables. check.sh runs ERC, DRC and the schematic parity check,
test_hub6.py the netlist and the geometry. The parts and nets below are the
single source for both the schematic and the board.
"""
import json
import math
import os
import re
import uuid

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "hub6"
REV = "C"
LIB = "dodecahedron-earth"
KICAD = "/usr/share/kicad"
A_IN = 26.0  # pentagon: centre to the middle of an edge, mm
R_CIRC = A_IN / math.cos(math.radians(36))
ORIGIN = (100.0 + R_CIRC, 100.0 + R_CIRC)  # the board's centre on the PCB sheet

# --- geometry -----------------------------------------------------------------
# Cup coordinates: x right, y up, seen from above; (0, 0) is the pentagon's centre, on the
# cup's axis. A direction "theta" is the cup's azimuth, counter-clockwise from +x.
# KiCad's sheet has y down: pt() turns one into the other.


def e(theta):
    t = math.radians(theta)
    return (math.cos(t), math.sin(t))


def add(*vs):
    return (sum(v[0] for v in vs), sum(v[1] for v in vs))


def mul(k, v):
    return (k * v[0], k * v[1])


def frame(theta, u, v):
    """The point u along theta and v along theta + 90 (cup coordinates)."""
    return add(mul(u, e(theta)), mul(v, e(theta + 90)))


def outline_corners():
    return [mul(R_CIRC, e(18 + 72 * k)) for k in range(5)]


# The six displays, by plate number counting counter-clockwise from above in the cup
# standing on its base (simulate/v0.0.5/magnets.csv), then the base. Display d's cable
# goes to J(d+1); its chip select is net LCD_CS(d).
DISPLAYS = ["plate 1", "plate 2", "plate 3", "plate 4", "plate 5", "base"]
W_THETA = (198, 270, 342, 54, 126)  # the side plates; each side row runs along its edge
W_R = 22.0

# The display's PH2.0 pins, 1 to 8 (Waveshare 1.28inch LCD Module); wire n goes into hole n.
# VCC must be 3.3V: the module's TXB0108 level shifter takes its header-side logic levels
# from VCC, and at 5V it wants 0.65 x 5V = 3.25V for a high, which a 3.3V XIAO pin does not
# guarantee (ESP32-S3 VOH min 2.64V); at 3.3V it wants 2.15V.
PH_PINS = ["VCC", "GND", "DIN", "CLK", "CS", "DC", "RST", "BL"]
BUS_PIN = {"LCD_DIN": 3, "LCD_CLK": 4, "LCD_DC": 6, "LCD_RST": 7, "LCD_BL": 8}
# B.Cu rings, centre to the track's centre line. Nothing on B.Cu crosses them, so any order works.
RING = {"+3V3": 16.8, "LCD_DIN": 17.6, "LCD_CLK": 18.4, "LCD_DC": 19.2, "LCD_RST": 20.0, "LCD_BL": 20.8}
RING_W = {"+3V3": 0.4}
GND_VIA_R = 15.9  # each side row's GND pin also reaches the inner GND fill by a via here
CS_ENTRY_R = 15.5  # each side row's chip select runs radially in to here, then to the chip

# The base display's holes (J6): a 2x4 block, numbered like a DIP-8 (1-4 along the outer row,
# 5-8 back along the inner row, 8 behind 1), facing the corner at 162 degrees: over the base
# display's plug (simulate/cables.py: centre (-8.68, 2.82), 9.1 from the axis at 162 degrees),
# 3.1 outward of it, clear of board B.
J6_THETA, J6_U = 162, 12.2
# J7, the 2x5 header to board B, faces the corner at 18 degrees: its outer column (5 pins)
# carries the shared signals out, its inner column 3V3, GND and the address lines.
J7_THETA, J7_U = 18, 11.23
CORNER_U = 16.0  # the lines from J6 and J7 gather here, 1 mm apart, then run straight out to their rings
CLEAR_U = 1.1    # first, every line runs straight out until it is this far beyond the outer row's centre line

# U1 (74HC138, SOIC-16) at the centre: local +x (the outputs' side) faces 198, local +y 108.
U1_THETA = 198


def header_nets(d):
    return {1: "+3V3", 2: "GND", 3: "LCD_DIN", 4: "LCD_CLK", 5: f"LCD_CS{d}", 6: "LCD_DC", 7: "LCD_RST", 8: "LCD_BL"}


# J7 by position: (column, lateral) -> net. Column "out" is at J7_U + 1.27, "in" at J7_U - 1.27;
# lateral counts along 108 degrees (J7_THETA + 90). Board B's socket takes the same positions.
J7_NETS = {("out", 5.08): "LCD_DIN", ("out", 2.54): "LCD_CLK", ("out", 0.0): "LCD_DC", ("out", -2.54): "LCD_RST", ("out", -5.08): "LCD_BL",
           ("in", 5.08): "GND", ("in", 2.54): "LCD_A2", ("in", 0.0): "LCD_A1", ("in", -2.54): "LCD_A0", ("in", -5.08): "+3V3"}

# 74HC138 (SOIC-16): 1 A0, 2 A1, 3 A2, 4 E1, 5 E2, 6 E3, 7 Y7, 8 GND, 9 Y6 ... 15 Y0, 16 VCC.
# E1 and E2 (active low) are tied to GND and E3 (active high) to 3V3, so it is always enabled.
# Which output selects which display follows from where each row's line arrives round the chip
# (counter-clockwise: plate 4, plate 5, base, plate 1, plate 2, plate 3): no line crosses another.
CS_OUTPUT = {3: 10, 4: 11, 5: 12, 0: 13, 1: 14, 2: 15}  # display d -> U1 pin (pin 15 - n is Yn)
U1_NETS = {1: "LCD_A0", 2: "LCD_A1", 3: "LCD_A2", 4: "GND", 5: "GND", 6: "+3V3", 8: "GND", 16: "+3V3"}
U1_NETS.update({pin: f"LCD_CS{d}" for d, pin in CS_OUTPUT.items()})

# --- parts ------------------------------------------------------------------
# ref: (symbol, value, footprint, LCSC part, pin -> net, placement)
# placement: (x, y, rotation) in cup coordinates (rotation counter-clockwise, as KiCad's), or
# "J7" (placed by place_j7).
SIDE_ROW_FP = f"{LIB}:Wire_1x08_P2.54_Tie"  # the side displays' rows, with two slots for a cable tie
BASE_FP = f"{LIB}:Wire_2x04_P2.54"
J7_FP = "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical"


def u1_local(x, y):
    """U1's footprint frame (KiCad's: +x the outputs' side, +y toward pin 8) to cup coordinates."""
    return add(mul(x, e(U1_THETA)), mul(y, e(U1_THETA - 90)))


PARTS = {}
for _d in range(5):
    PARTS[f"J{_d + 1}"] = (f"{LIB}:Cable_8P", DISPLAYS[_d], SIDE_ROW_FP, "", header_nets(_d),
                           (*mul(W_R, e(W_THETA[_d])), (W_THETA[_d] + 90) % 360))
PARTS["J6"] = (f"{LIB}:Cable_8P", DISPLAYS[5], BASE_FP, "", header_nets(5), (*mul(J6_U, e(J6_THETA)), J6_THETA - 90))
PARTS.update({
    # hand-soldered from below; its pins go down into board B's socket
    "J7": (f"{LIB}:Header_2x05", "to board B", J7_FP, "", None, "J7"),
    "U1": (f"{LIB}:74HC138", "74HC138", "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", "C5602", U1_NETS, (0.0, 0.0, U1_THETA)),
    # bulk for the six displays (about 190mA) on the 3V3 line from J7, and U1's decoupling at its VCC
    "C2": ("Device:C", "10uF", "Capacitor_SMD:C_0805_2012Metric", "C15850", {1: "+3V3", 2: "GND"}, (*u1_local(-6.0, -7.15), U1_THETA + 90)),
    "C3": ("Device:C", "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", {1: "+3V3", 2: "GND"}, (*u1_local(1.0, -6.975), U1_THETA + 90)),
})


def uid():
    return str(uuid.uuid4())


# --- S-expression helpers ---------------------------------------------------


def find_block(text, head):
    """Return the balanced (...) block starting with `head`."""
    i = text.index(head)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
        elif text[j] == '"':
            j = text.index('"', j + 1)
    raise ValueError(head)


def lib_symbol(lib, name, path):
    block = find_block(open(path).read(), f'(symbol "{name}"')
    assert "(extends" not in block, name
    return block.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)


def pin_names(block):
    """pin number -> pin name."""
    return {m.group(2): m.group(1) for m in re.finditer(r'\(name "([^"]*)".*?\(number "([^"]+)"', block, re.S)}


def unconnected_net(ref, num, name):
    """The name KiCad gives the net of an unconnected pin."""
    return f"unconnected-({ref}-{name}-Pad{num})" if name and name != num else f"unconnected-({ref}-Pad{num})"


def pins_of(block):
    """pin number -> (x, y) connection point, symbol coordinates (y up)."""
    pins = {}
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) [-\d.]+\).*?\(number "([^"]+)"', block, re.S):
        pins[m.group(3)] = (float(m.group(1)), float(m.group(2)))
    return pins


# --- project symbol library ---------------------------------------------------


def box_symbol(name, ref, left, right, width=15.24):
    """A rectangle with pins: left/right are lists of (number, name, type), top to bottom."""
    n = max(len(left), len(right))
    top = (n - 1) * 2.54 / 2
    h = top + 2.54
    out = [f'(symbol "{name}" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)',
           f'(property "Reference" "{ref}" (at 0 {h + 1.27:.2f} 0) (effects (font (size 1.27 1.27))))',
           f'(property "Value" "{name}" (at 0 {-h - 1.27:.2f} 0) (effects (font (size 1.27 1.27))))',
           '(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           '(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
           f'(symbol "{name}_0_1" (rectangle (start {-width / 2:.2f} {h:.2f}) (end {width / 2:.2f} {-h:.2f}) (stroke (width 0.254) (type default)) (fill (type background))))',
           f'(symbol "{name}_1_1"']
    for side, pins in ((-1, left), (1, right)):
        for i, (num, pname, ptype) in enumerate(pins):
            x = side * (width / 2 + 2.54)
            y = top - i * 2.54
            ang = 0 if side < 0 else 180
            out.append(f'(pin {ptype} line (at {x:.2f} {y:.2f} {ang}) (length 2.54) (name "{pname}" (effects (font (size 1.27 1.27)))) (number "{num}" (effects (font (size 1.27 1.27)))))')
    out.append("))")
    return "\n".join(out)


def project_symbols():
    hc_left = [(str(i), n, "passive") for i, n in ((1, "A0"), (2, "A1"), (3, "A2"), (4, "E1"), (5, "E2"), (6, "E3"), (7, "Y7"), (8, "GND"))]
    hc_right = [("16", "VCC", "passive")] + [(str(15 - n), f"Y{n}", "passive") for n in range(7)]
    return {
        "74HC138": box_symbol("74HC138", "U", hc_left, hc_right),
        "Cable_8P": box_symbol("Cable_8P", "J", [(str(i), PH_PINS[i - 1], "passive") for i in range(1, 9)], [], width=5.08),
        "Header_2x05": box_symbol("Header_2x05", "J", [(str(i), str(i), "passive") for i in (1, 3, 5, 7, 9)],
                                  [(str(i), str(i), "passive") for i in (2, 4, 6, 8, 10)], width=7.62),
    }


def write_symbol_lib(symbols):
    body = "\n".join(symbols.values())
    with open(os.path.join(HERE, f"{LIB}.kicad_sym"), "w") as f:
        f.write(f"(kicad_symbol_lib (version 20231120) (generator \"make.py\")\n{body}\n)\n")


# --- project footprints -------------------------------------------------------


def write_footprints():
    pretty = os.path.join(HERE, f"{LIB}.pretty")
    os.makedirs(pretty, exist_ok=True)
    for old in ("Wire_1x08_P2.54.kicad_mod", "XIAO_ESP32S3_Outline.kicad_mod"):
        if os.path.exists(os.path.join(pretty, old)):
            os.remove(os.path.join(pretty, old))
    # A row of eight holes for a display cable's bare wires (26 AWG stranded, about 0.5mm of
    # copper), soldered straight in: 1.0mm drills in 1.7mm pads, 2.54 apart so the insulation
    # (about 1.2mm) sits side by side. Pin 1 at +x, marked on the silkscreen (round pads all:
    # a square pad's corners would reach the stubs beside it). Two 1.3 x 2.9 slots, 2.0 outward
    # (+y) and beyond the row's ends, for a 2.5mm cable tie that holds the cable down.
    lines = ['(footprint "Wire_1x08_P2.54_Tie" (version 20240108) (generator "make.py") (layer "F.Cu")',
             '(descr "Eight holes for a cable\'s bare 26 AWG wires, soldered in, with two slots for a cable tie")',
             '(attr through_hole exclude_from_pos_files exclude_from_bom)',
             '(property "Reference" "REF**" (at 0 -2.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
             '(property "Value" "Cable_8P" (at 0 2.2 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
             '(fp_rect (start -9.85 -0.95) (end 9.85 0.95) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
             '(fp_text user "1" (at 10.5 0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))']
    for p in range(1, 9):
        lines.append(f'(pad "{p}" thru_hole circle (at {8.89 - 2.54 * (p - 1):.2f} 0) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask") (remove_unused_layers no))')
    for x in (-10.9, 10.9):
        lines.append(f'(pad "" np_thru_hole oval (at {x:.2f} 2.0 90) (size 2.9 1.3) (drill oval 2.9 1.3) (layers "*.Cu" "*.Mask"))')
    lines.append(")")
    with open(os.path.join(pretty, "Wire_1x08_P2.54_Tie.kicad_mod"), "w") as f:
        f.write("\n".join(lines) + "\n")
    # The base display's cable in a 2x4 block of the same holes, numbered like a DIP-8: 1-4 along
    # the -y row from -x, 5-8 back along the +y row (8 behind 1). Pin 1 marked on the silkscreen.
    pos = {1: (-3.81, -1.27), 2: (-1.27, -1.27), 3: (1.27, -1.27), 4: (3.81, -1.27),
           5: (3.81, 1.27), 6: (1.27, 1.27), 7: (-1.27, 1.27), 8: (-3.81, 1.27)}
    lines = ['(footprint "Wire_2x04_P2.54" (version 20240108) (generator "make.py") (layer "F.Cu")',
             '(descr "Eight holes for a cable\'s bare 26 AWG wires in two rows of four, numbered like a DIP-8")',
             '(attr through_hole exclude_from_pos_files exclude_from_bom)',
             '(property "Reference" "REF**" (at 0 -3.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
             '(property "Value" "Cable_8P" (at 0 3.2 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
             '(fp_rect (start -4.75 -2.2) (end 4.75 2.2) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
             '(fp_text user "1" (at -5.4 -1.27 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))']
    for p, (x, y) in pos.items():
        lines.append(f'(pad "{p}" thru_hole circle (at {x:.2f} {y:.2f}) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask") (remove_unused_layers no))')
    lines.append(")")
    with open(os.path.join(pretty, "Wire_2x04_P2.54.kicad_mod"), "w") as f:
        f.write("\n".join(lines) + "\n")


# --- schematic ----------------------------------------------------------------

# on the 2.54mm grid so every pin lands on the connection grid
SCH_POS = {ref: (round(x / 2.54) * 2.54, round(y / 2.54) * 2.54) for ref, (x, y) in
           {"J7": (40, 70), "C2": (110, 70), "C3": (130, 70), "U1": (175, 70),
            "J1": (30, 150), "J2": (75, 150), "J3": (120, 150), "J4": (165, 150), "J5": (210, 150), "J6": (255, 150)}.items()}


def all_libs(symbols):
    libs = {"Device:C": lib_symbol("Device", "C", f"{KICAD}/symbols/Device.kicad_sym")}
    for name, block in symbols.items():
        libs[f"{LIB}:{name}"] = block.replace(f'(symbol "{name}"', f'(symbol "{LIB}:{name}"', 1)
    return libs


def write_schematic(libs, nets_of):
    root = uid()
    out = [f'(kicad_sch (version 20231120) (generator "make.py") (generator_version "10.0") (uuid "{root}") (paper "A4")',
           f'(title_block (title "dodecahedron-earth {NAME}") (rev "{REV}") (comment 1 "Board A: 6 soldered cables (PH2.0 at the display) to 1.28 inch round LCDs, 74HC138, header to the XIAO board"))',
           "(lib_symbols", *libs.values(), ")"]
    for ref, (lib_id, value, fp, lcsc, _, _) in PARTS.items():
        nets = nets_of[ref]
        x, y = SCH_POS[ref]
        pins = pins_of(libs[lib_id])
        props = [("Reference", ref, 0, -1), ("Value", value, 0, 1), ("Footprint", fp, 0, 0), ("Datasheet", "", 0, 0)]
        if lcsc:
            props.append(("LCSC", lcsc, 0, 0))
        out.append(f'(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom {"yes" if lcsc else "no"}) (on_board yes) (dnp no) (uuid "{uid()}")')
        top = min(-py for _, py in pins.values()) + y
        bottom = max(-py for _, py in pins.values()) + y
        for pname, pval, _, where in props:
            hide = " hide" if where == 0 else ""
            py = top - 3.81 if where < 0 else (bottom + 3.81 if where > 0 else y)
            out.append(f'(property "{pname}" "{pval}" (at {x:.2f} {py:.2f} 0) (effects (font (size 1.27 1.27)){hide}))')
        for num in pins:
            out.append(f'(pin "{num}" (uuid "{uid()}"))')
        out.append(f'(instances (project "{NAME}" (path "/{root}" (reference "{ref}") (unit 1)))))')
        for num, (px, py) in pins.items():
            net = nets.get(int(num))
            ax, ay = x + px, y - py
            if net is None:
                out.append(f'(no_connect (at {ax:.2f} {ay:.2f}) (uuid "{uid()}"))')
                continue
            left = px < 0 or (abs(px) < 1e-6 and py > 0)
            ang, just = (180, "right") if left else (0, "left")
            out.append(f'(global_label "{net}" (shape passive) (at {ax:.2f} {ay:.2f} {ang}) (effects (font (size 1.27 1.27)) (justify {just})) (uuid "{uid()}"))')
    out.append('(sheet_instances (path "/" (page "1")))')
    out.append(")")
    with open(os.path.join(HERE, f"{NAME}.kicad_sch"), "w") as f:
        f.write("\n".join(out) + "\n")


# --- board --------------------------------------------------------------------


def mm(v):
    return pcbnew.FromMM(v)


def pt(p):
    """Cup coordinates (mm) to a point on the sheet."""
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + p[0]), mm(ORIGIN[1] - p[1]))


def cup(pos):
    """A point on the sheet to cup coordinates (mm)."""
    return (pcbnew.ToMM(pos.x) - ORIGIN[0], ORIGIN[1] - pcbnew.ToMM(pos.y))


def load_fp(fp_id):
    lib, name = fp_id.split(":")
    path = os.path.join(HERE, f"{LIB}.pretty") if lib == LIB else f"{KICAD}/footprints/{lib}.pretty"
    fp = pcbnew.FootprintLoad(path, name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def place_j7(board, fp):
    """J7 on the underside, its two columns of five tangential at J7_U -+ 1.27 along J7_THETA."""
    board.Add(fp)
    fp.SetPosition(pt((0.0, 0.0)))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees((J7_THETA + rot) % 360)
        cs = [cup(p.GetPosition()) for p in fp.Pads()]
        us = sorted({round(c[0] * e(J7_THETA)[0] + c[1] * e(J7_THETA)[1], 3) for c in cs})
        if len(us) == 2:
            break
    cx = sum(c[0] for c in cs) / len(cs)
    cy = sum(c[1] for c in cs) / len(cs)
    target = mul(J7_U, e(J7_THETA))
    fp.SetPosition(pt(add(cup(fp.GetPosition()), (target[0] - cx, target[1] - cy))))


def j7_pin_nets():
    """J7's pin number -> net, from where each pin lands (J7_NETS)."""
    board = pcbnew.BOARD()
    fp = load_fp(J7_FP)
    place_j7(board, fp)
    nets = {}
    for p in fp.Pads():
        c = cup(p.GetPosition())
        u = c[0] * e(J7_THETA)[0] + c[1] * e(J7_THETA)[1]
        v = c[0] * e(J7_THETA + 90)[0] + c[1] * e(J7_THETA + 90)[1]
        col = "out" if u > J7_U else "in"
        nets[int(p.GetNumber())] = J7_NETS[(col, round(v / 2.54) * 2.54 + 0.0)]
    assert len(set(nets.values())) == 10, nets
    return nets


def write_board(libs, nets_of):
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.3)
    corners = outline_corners()
    # fabrication files are written from the lower left corner of the board's bounding box
    ds.SetAuxOrigin(pt((min(x for x, _ in corners), min(y for _, y in corners))))
    ds.SetGridOrigin(pt((min(x for x, _ in corners), min(y for _, y in corners))))
    nets = {}

    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            nets[name] = n
        return nets[name]

    for ref, (lib_id, value, fp_id, lcsc, _, place) in PARTS.items():
        fp = load_fp(fp_id)
        fp.SetReference(ref)
        fp.SetValue(value)
        if lcsc:
            fp.SetField("LCSC", lcsc)
            field = fp.GetField("LCSC")
            field.SetVisible(False)
            field.SetLayer(pcbnew.F_Fab)
        if fp_id in (SIDE_ROW_FP, BASE_FP):
            fp.Reference().SetVisible(False)  # a label of our own, below
            fp.Value().SetVisible(False)
        if ref in ("C2", "C3", "U1", "J7"):
            fp.Reference().SetVisible(False)  # see the schematic
        if ref == "J7":
            fp.Value().SetVisible(False)
            # hand-soldered: not in JLCPCB's BOM or placement file
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        if place == "J7":
            place_j7(board, fp)
        else:
            board.Add(fp)
            fp.SetPosition(pt(place[:2]))
            fp.SetOrientationDegrees(place[2] % 360)
        names = pin_names(libs[lib_id])
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num:
                # the schematic names an unconnected pin's net after the pin
                pad.SetNet(net(nets_of[ref].get(int(num)) or unconnected_net(ref, num, names.get(num))))

    for a, b in zip(corners, corners[1:] + corners[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pt(a))
        seg.SetEnd(pt(b))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(mm(0.1))
        board.Add(seg)

    def along(theta):
        """Text angle that runs along a row facing theta, the right way up."""
        a = (theta + 90) % 360
        return a - 180 if 90 < a <= 270 else a
    short = ["P1", "P2", "P3", "P4", "P5", "BASE"]
    labels = [(short[d], mul(W_R - 2.0, e(W_THETA[d])), pcbnew.F_SilkS, along(W_THETA[d])) for d in range(5)]
    labels += [(f"J{d + 1} {DISPLAYS[d]}", mul(W_R - 2.0, e(W_THETA[d])), pcbnew.B_SilkS, along(W_THETA[d])) for d in range(5)]
    labels += [("BASE", mul(J6_U - 3.4, e(J6_THETA)), pcbnew.F_SilkS, along(J6_THETA)),
               ("J6 base (from below)", mul(J6_U - 3.4, e(J6_THETA)), pcbnew.B_SilkS, along(J6_THETA)),
               ("J7 to board B", mul(J7_U - 3.6, e(J7_THETA)), pcbnew.B_SilkS, along(J7_THETA)),
               (f"hub6 rev {REV}", mul(7.0, e(270)), pcbnew.B_SilkS, 0)]
    for text, p, layer, angle in labels:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(pt(p))
        t.SetLayer(layer)
        t.SetMirrored(layer == pcbnew.B_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        t.SetTextThickness(mm(0.15))
        t.SetTextAngleDegrees(angle)
        board.Add(t)

    route(board, net)

    # GND fills both layers round everything else; thermal spokes on the hand-soldered holes
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(net("GND"))
        outline = zone.Outline()
        outline.NewOutline()
        for c in corners:
            p = pt(c)
            outline.Append(p.x, p.y)
        zone.SetLocalClearance(mm(0.3))
        zone.SetMinThickness(mm(0.2))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetThermalReliefGap(mm(0.3))
        zone.SetThermalReliefSpokeWidth(mm(0.4))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        board.Add(zone)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(os.path.join(HERE, f"{NAME}.kicad_pcb"))


# --- the wiring -----------------------------------------------------------------
# Drawn here, not autorouted. B.Cu has only the rings (and GND round them); F.Cu has every other
# line, each a short straight run or a few, and crosses the rings freely.
TRACK_W, POWER_W, VIA_D, VIA_DRILL = 0.2, 0.3, 0.6, 0.3
RING_STEP_DEG = 3.0

# The chip selects from the side rows: from CS_ENTRY_R to U1's output pad, through these points
# in U1's frame (+x the outputs' side, at 198 degrees; +y toward pin 8, at 108). Lines that arrive
# from the inputs' side go round an end of the chip, outside the lines nearer it.
CS_PATH = {
    0: [(8.0, -0.635)],                                 # plate 1, straight in (pin 13)
    1: [(5.6, -1.905)],                                 # plate 2, along the chip to pin 14
    2: [(-8.0, -10.2), (4.4, -10.2), (4.4, -3.175)],    # plate 3, round the pin 1 end to pin 15, outside VCC and C3
    3: [(-5.0, 7.0), (3.8, 7.0), (3.8, 3.175)],         # plate 4, round the pin 8 end to pin 10
    4: [(4.8, 12.0), (4.8, 1.905)],                     # plate 5, along the chip to pin 11
}
J6_CS_PATH = [(6.0, 8.2), (6.0, 0.635)]                 # the base display, from J6 pin 5 to pin 12
# A0, A1, A2 from J7 straight across to pins 1, 2, 3 (each through a point level with its pad)
A_PATH_X = -6.0
VCC_Y = 6.2   # 3V3 from J7 runs past C2 and C3, then up into pin 16, round the pin 1 end
GND_VIA_X = -4.6  # pins 4, 5 (one via between them) and 8


def route(board, net):
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    pad = {(r, p.GetNumber()): p for r, f in fps.items() for p in f.Pads() if p.GetNumber()}
    on_ring = {name: [] for name in RING}

    def pos(ref, num):
        return cup(pad[(ref, str(num))].GetPosition())

    def track(name, pts, layer=pcbnew.F_Cu, width=None):
        w = width or (POWER_W if name in ("+3V3", "GND") else TRACK_W)
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pt(a))
            t.SetEnd(pt(b))
            t.SetWidth(mm(w))
            t.SetLayer(layer)
            t.SetNet(net(name))
            board.Add(t)

    def via(name, p):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(p))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(mm(VIA_D))
        v.SetDrill(mm(VIA_DRILL))
        v.SetNet(net(name))
        board.Add(v)

    def to_ring(name, pts, d):
        """A line through pts that goes on from the last, along the unit vector d, to a via on name's ring."""
        b = pts[-1]
        # the point b + s d with |b + s d| = R
        bd = b[0] * d[0] + b[1] * d[1]
        root = math.sqrt(bd * bd - (b[0] ** 2 + b[1] ** 2 - RING[name] ** 2))
        s = min(x for x in (-bd - root, -bd + root) if x > 0)  # the first crossing ahead
        end = add(b, mul(s, d))
        track(name, pts + [end])
        via(name, end)
        on_ring[name].append(math.degrees(math.atan2(end[1], end[0])) % 360)

    # the side rows: radial stubs to the rings; GND to a via inside them; CS in towards U1
    for d in range(5):
        ref = f"J{d + 1}"
        for num, name in header_nets(d).items():
            p = pos(ref, num)
            r = math.hypot(*p)
            unit = (p[0] / r, p[1] / r)
            if name in RING:
                to_ring(name, [p], mul(-1, unit))
            elif name == "GND":
                track(name, [p, mul(GND_VIA_R, unit)])
                via(name, mul(GND_VIA_R, unit))
            else:
                entry = mul(CS_ENTRY_R, unit)
                target = pos("U1", CS_OUTPUT[d])
                track(name, [p, entry] + [u1_local(*q) for q in CS_PATH[d]] + [target])

    # J6 and J7 reach the rings through a corner: from the outer row's pads, and from the inner
    # row's through the gaps between the outer pads, the lines gather 1 mm apart at CORNER_U.
    def corner(theta, u_out, lines):
        """lines: (lateral, net, start points), in order along theta + 90."""
        k = len(lines)
        for i, (v, name, pts) in enumerate(lines):
            t = (i - (k - 1) / 2) * 1.0
            to_ring(name, pts + [frame(theta, u_out + CLEAR_U, v), frame(theta, CORNER_U, t)], e(theta))

    def gap_path(ref, num, theta, u_out, v_gap):
        """From an inner pad, out through the gap at v_gap in the outer row (at u_out)."""
        p = pos(ref, num)
        return [p, frame(theta, u_out - 1.27, v_gap)]

    def uv(theta, p):
        return (p[0] * e(theta)[0] + p[1] * e(theta)[1], p[0] * e(theta + 90)[0] + p[1] * e(theta + 90)[1])

    j6 = header_nets(5)
    u_out = J6_U + 1.27
    lines = []
    for num, name in j6.items():
        if name not in RING:
            continue
        u, v = uv(J6_THETA, pos("J6", num))
        if u > J6_U:
            lines.append((v, name, [pos("J6", num)]))
        else:  # inner row (pins 6, 7, 8): out through the gap on pin 4's side of the outer pad in front
            lines.append((v - 1.27, name, gap_path("J6", num, J6_THETA, u_out, v - 1.27)))
    corner(J6_THETA, u_out, sorted(lines))

    j7 = nets_of_j7()
    u_out = J7_U + 1.27
    lines = []
    for num, name in j7.items():
        u, v = uv(J7_THETA, pos("J7", num))
        if name in BUS_PIN:
            lines.append((v, name, [pos("J7", num)]))
        elif name == "+3V3":
            lines.append((v + 1.27, name, gap_path("J7", num, J7_THETA, u_out, v + 1.27)))
    corner(J7_THETA, u_out, sorted(lines))

    # the base display's chip select, and the address lines
    track("LCD_CS5", [pos("J6", 5)] + [u1_local(*q) for q in J6_CS_PATH] + [pos("U1", CS_OUTPUT[5])])
    for k, name in enumerate(("LCD_A0", "LCD_A1", "LCD_A2")):
        num = next(n for n, v in j7.items() if v == name)
        target = pos("U1", 1 + k)
        level = (A_PATH_X, -4.445 + 1.27 * k)
        track(name, [pos("J7", num), u1_local(*level), target])
    # 3V3 from J7 to C2, C3 and pin 16; E3 (pin 6) from pin 16 under the chip's body
    v3 = next(n for n, v in j7.items() if v == "+3V3")
    j7p = pos("J7", v3)
    c2, c3 = pos("C2", 1), pos("C3", 1)
    p16 = pos("U1", 16)
    track("+3V3", [j7p, u1_local(-8.6, -VCC_Y), c2, c3, u1_local(2.475, -VCC_Y), p16])
    track("+3V3", [p16, u1_local(1.0, -3.6), u1_local(-1.0, 1.0), u1_local(-1.6, 1.905), pos("U1", 6)])
    # GND: pins 4 and 5 to one via beside them, pin 8 to its own; the capacitors' GND pads to vias
    track("GND", [pos("U1", 4), u1_local(GND_VIA_X, 0.0), pos("U1", 5)])
    via("GND", u1_local(GND_VIA_X, 0.0))
    track("GND", [pos("U1", 8), u1_local(GND_VIA_X, 4.445)])
    via("GND", u1_local(GND_VIA_X, 4.445))
    for ref in ("C2", "C3"):
        p1, p2 = pos(ref, 1), pos(ref, 2)
        d = (p2[0] - p1[0], p2[1] - p1[1])
        n = math.hypot(*d)
        v = add(p2, mul(1.05 / n, d))
        track("GND", [p2, v])
        via("GND", v)

    # the rings: closed circles through every via on them, in steps of RING_STEP_DEG
    for name, radius in RING.items():
        stops = sorted(set(on_ring[name]) | {round(a * RING_STEP_DEG, 6) for a in range(int(360 / RING_STEP_DEG))})
        pts = [mul(radius, e(a)) for a in stops]
        track(name, pts + pts[:1], layer=pcbnew.B_Cu, width=RING_W.get(name, TRACK_W))


def nets_of_j7():
    return j7_pin_nets()


def write_project():
    pro = {
        "board": {"design_settings": {"rules": {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.6,
                                                "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.3}}},
        "net_settings": {
            "classes": [
                {"name": "Default", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3},
            ],
            "netclass_patterns": [],
        },
        "meta": {"filename": f"{NAME}.kicad_pro", "version": 1},
    }
    with open(os.path.join(HERE, f"{NAME}.kicad_pro"), "w") as f:
        json.dump(pro, f, indent=2)
    with open(os.path.join(HERE, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table (version 7)\n'
                f'  (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") (options "") (descr ""))\n'
                '  (lib (name "Device") (type "KiCad") (uri "${KICAD10_SYMBOL_DIR}/Device.kicad_sym") (options "") (descr ""))\n)\n')
    with open(os.path.join(HERE, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table (version 7)\n'
                f'  (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.pretty") (options "") (descr ""))\n')
        for lib in ("Capacitor_SMD", "Connector_PinHeader_2.54mm", "Package_SO"):
            f.write(f'  (lib (name "{lib}") (type "KiCad") (uri "${{KICAD10_FOOTPRINT_DIR}}/{lib}.pretty") (options "") (descr ""))\n')
        f.write(")\n")


def main():
    symbols = project_symbols()
    libs = all_libs(symbols)
    write_symbol_lib(symbols)
    write_footprints()
    write_project()
    nets_of = {ref: (p[4] if p[4] is not None else j7_pin_nets()) for ref, p in PARTS.items()}
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    write_schematic(libs, nets_of)
    write_board(libs, nets_of)
    print(f"wrote {NAME}.kicad_sch, {NAME}.kicad_pcb")


if __name__ == "__main__":
    main()
