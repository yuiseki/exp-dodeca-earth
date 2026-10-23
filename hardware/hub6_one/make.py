"""Generate hub6_one (draft): one 2-layer board for the six 1.28 inch round LCDs (GC9A01,
PH2.0 8-pin) of one cup, with the XIAO ESP32-S3 on it: the alternative to rev C's two boards.

    PYTHONPATH=/usr/lib/python3/dist-packages:<venv site-packages, for shapely> /usr/bin/python3 make.py

A regular pentagon whose edges face the cup's five side plates. The XIAO hangs under it, flat side
up (its battery wires leave through its pin headers' gap), plugged into two 8.5 mm female sockets
on the underside (the same part as cubic-earth's hub3, soldered by hand), so seen from above its pins are mirrored.
It sits 3 mm off the middle toward 342 degrees, clear of the base display's plug below. A
74HC138 between the sockets, on top, turns three XIAO pins into the six chip selects.

- B.Cu: one ring per shared signal (3V3 innermost, then the five), and inside them the chip
  selects, routed between the XIAO's pins (router.py); GND fills the rest.
- F.Cu: straight lines only, which cross the rings freely: each cable row's radial stubs to its
  rings; the XIAO's five bus pins out to their rings through the pentagon's corner at 162
  degrees, the base display's holes (J6, a 2x4 block) through the corner at 90; the chip
  selects from each row in to a via just inside the rings; A0..A2, 3V3 round the chip. GND fills
  the rest.

The display cables (PH2.0 at the display, bare 26 AWG at this end) are soldered straight into
holes: a row of eight along each edge for the side displays, from above, and J6 for the base
display, from below, past the XIAO's end. Everything JLCPCB places is on the top side.
"""
import json
import math
import os
import re
import uuid

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "hub6_one"
REV = "D (draft)"
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

# The XIAO hangs under the middle, its frame: +x toward 162 (the column D0..D6), +y toward 72,
# centred (XIAO_X, XIAO_Y) (off the middle so that it clears the base display's connector and J6's holes
# clear its end). Seen from above (it is
# mirrored, flat side up): D0..D6 up the +x column from the USB-C end (-y), 5V, GND, 3V3, D10..D7 up
# the -x column.
XIAO_PSI = 162
XIAO_Y = -2.5
XIAO_X = -3.0  # toward 342: in its 8.5 mm sockets the XIAO hangs low, and so clears the base display's plug
XIAO_W, XIAO_L = 17.79, 21.145
XIAO_COL = {**{f"D{k}": (7.62, -7.62 + 2.54 * k) for k in range(7)},
            **{n: (-7.62, -7.62 + 2.54 * k) for k, n in enumerate(["5V", "GND", "3V3", "D10", "D9", "D8", "D7"])}}
XIAO_NUMBER = {"D0": 1, "D1": 2, "D2": 3, "D3": 4, "D4": 5, "D5": 6, "D6": 7, "D7": 8, "D8": 9, "D9": 10,
               "D10": 11, "3V3": 12, "GND": 13, "5V": 14}
# which XIAO pin carries which signal: the bus from the +x column (in order along it, so the lines
# to the corner at 162 do not cross), A0..A2 from the -x column level with U1's pins 1..3
XIAO_NETS = {"D1": "LCD_BL", "D2": "LCD_RST", "D3": "LCD_DC", "D4": "LCD_CLK", "D5": "LCD_DIN",
             "D10": "LCD_A0", "D9": "LCD_A1", "D8": "LCD_A2", "3V3": "+3V3", "GND": "GND"}


def xf(lx, ly):
    """The XIAO's frame (relative to the board's centre) to cup coordinates."""
    return add(mul(lx, e(XIAO_PSI)), mul(ly, e(XIAO_PSI - 90)))


def xiao_pad(name):
    x, y = XIAO_COL[name]
    return xf(x + XIAO_X, y + XIAO_Y)


# The base display's holes (J6): a 2x4 block, numbered like a DIP-8 (1-4 along the outer row, 5-8
# back along the inner one, 8 behind 1), facing the corner at 90 degrees, beyond the XIAO's far end
# (away from its USB-C).
J6_THETA, J6_U = 90, 12.5
CORNER_U = 16.0  # the lines from J6 and the XIAO gather here, 1 mm apart, then run straight out to their rings
CLEAR_U = 1.1    # first, every line runs straight out until it is this far beyond its pads' centre line

# U1 (74HC138, SOIC-16) between the XIAO's columns, on top, its frame the XIAO's (outputs toward
# +x), centred U1_Y along y.
U1_Y = 2.5
Y_VIA_X = 4.5     # each output's via beside its pad, down to B.Cu
LANE_R = (15.2, 15.6, 16.0)  # where a side row's chip select goes down to B.Cu
LANE_DELTA = range(-14, 15)  # degrees either side of its pad 5
BCU_LIMIT = 16.2  # B.Cu: the chip selects stay inside this (the 3V3 ring's inner edge is at 16.6)


def header_nets(d):
    return {1: "+3V3", 2: "GND", 3: "LCD_DIN", 4: "LCD_CLK", 5: f"LCD_CS{d}", 6: "LCD_DC", 7: "LCD_RST", 8: "LCD_BL"}


# 74HC138 (SOIC-16): 1 A0, 2 A1, 3 A2, 4 E1, 5 E2, 6 E3, 7 Y7, 8 GND, 9 Y6 ... 15 Y0, 16 VCC.
# E1 and E2 (active low) are tied to GND and E3 (active high) to 3V3, so it is always enabled.
# Which output selects which display is the router's choice (route_chip_selects), written to the
# board; the nets here start without the outputs.
U1_NETS = {1: "LCD_A0", 2: "LCD_A1", 3: "LCD_A2", 4: "GND", 5: "GND", 6: "+3V3", 8: "GND", 16: "+3V3"}
CS_OUTPUT = {3: 10, 5: 11, 4: 12, 0: 13, 1: 14, 2: 15}  # display d -> U1 pin (pin 15 - n is Yn); Y6 (pin 9) and Y7 unused

# --- parts ------------------------------------------------------------------
# ref: (symbol, value, footprint, LCSC part, pin -> net, placement)
# placement: (x, y, rotation) in cup coordinates (rotation counter-clockwise, as KiCad's).
SIDE_ROW_FP = f"{LIB}:Wire_1x08_P2.54_Tie"  # the side displays' rows, with two slots for a cable tie
BASE_FP = f"{LIB}:Wire_2x04_P2.54"
XIAO_FP = f"{LIB}:XIAO_ESP32S3_Hanging"  # its outline only (board only, no pads)
SOCKET_FP = "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical"


def u1_local(x, y):
    """U1's footprint frame to cup coordinates."""
    return xf(x + XIAO_X, y + U1_Y)


PARTS = {}
for _d in range(5):
    PARTS[f"J{_d + 1}"] = (f"{LIB}:Cable_8P", DISPLAYS[_d], SIDE_ROW_FP, "", header_nets(_d),
                           (*mul(W_R, e(W_THETA[_d])), (W_THETA[_d] + 90) % 360))
PARTS["J6"] = (f"{LIB}:Cable_8P", DISPLAYS[5], BASE_FP, "", header_nets(5), (*mul(J6_U, e(J6_THETA)), J6_THETA - 90))
PARTS.update({
    # The XIAO itself plugs in by hand: on the schematic only. It hangs under the board, flat side up,
    # its pin headers in two 1x7 female sockets (8.5 mm) on the underside: J7 the D0..D6 column, J8
    # the other (each socket's pins take the nets of the XIAO pins they hold, place_sockets).
    "U2": (f"{LIB}:XIAO_ESP32S3", "XIAO ESP32S3", "", "", {XIAO_NUMBER[k]: v for k, v in XIAO_NETS.items()}, None),
    # soldered by hand (XFCN PM254V-11-07-H85, LCSC C2832270 as on cubic-earth's hub3): not in the BOM
    "J7": (f"{LIB}:Socket_1x07", "XIAO D0-D6", SOCKET_FP, "", None, "socket"),
    "J8": (f"{LIB}:Socket_1x07", "XIAO 5V-D7", SOCKET_FP, "", None, "socket"),
    "X1": (None, "XIAO", XIAO_FP, "", {}, (*xf(XIAO_X, XIAO_Y), XIAO_PSI)),
    "U1": (f"{LIB}:74HC138", "74HC138", "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", "C2674688", U1_NETS, (*xf(XIAO_X, U1_Y), XIAO_PSI)),
    # bulk for the six displays (about 190mA) on the 3V3 line from the XIAO, and U1's decoupling
    # pad 1 of each on the 3V3 line, which runs 1.0 beyond the XIAO's 3V3 pin
    "C2": ("Device:C", "10uF", "Capacitor_SMD:C_0805_2012Metric", "C15850", {1: "+3V3", 2: "GND"}, (*xf(XIAO_X - 3.5, XIAO_Y - 2.54 - 1.0 - 0.95), XIAO_PSI - 90 + 180)),
    "C3": ("Device:C", "100nF", "Capacitor_SMD:C_0603_1608Metric", "C14663", {1: "+3V3", 2: "GND"}, (*xf(XIAO_X + 1.0, XIAO_Y - 2.54 - 1.0 - 0.775), XIAO_PSI - 90 + 180)),
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
        "Socket_1x07": box_symbol("Socket_1x07", "J", [(str(i), str(i), "passive") for i in range(1, 8)], [], width=5.08),
        "XIAO_ESP32S3": box_symbol("XIAO_ESP32S3", "U", [(str(XIAO_NUMBER[f"D{k}"]), f"D{k}", "bidirectional") for k in range(7)],
                                   [(str(XIAO_NUMBER[n]), n, "power_out" if n in ("5V", "GND", "3V3") else "bidirectional")
                                    for n in ("5V", "GND", "3V3", "D10", "D9", "D8", "D7")]),
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
    # Where the XIAO ESP32-S3 hangs under the board in its two sockets (15.24 apart), flat side up,
    # USB-C toward -y: its outline on B.Fab. No pads (the sockets have them), no courtyard.
    lines = ['(footprint "XIAO_ESP32S3_Hanging" (version 20240108) (generator "make.py") (layer "F.Cu")',
             '(descr "Outline of a Seeed XIAO ESP32-S3 hanging under the board in two 1x7 sockets, flat side up, USB-C toward -y")',
             '(attr board_only exclude_from_pos_files exclude_from_bom)',
             '(property "Reference" "REF**" (at 0 -12 0) (layer "F.Fab") (hide yes) (effects (font (size 1 1) (thickness 0.15))))',
             '(property "Value" "XIAO" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1 1) (thickness 0.15))))',
             f'(fp_rect (start {-XIAO_W / 2:.3f} {-XIAO_L / 2:.3f}) (end {XIAO_W / 2:.3f} {XIAO_L / 2:.3f}) (stroke (width 0.12) (type default)) (fill none) (layer "B.Fab"))',
             f'(fp_rect (start -4.5 {-XIAO_L / 2 - 1.3:.3f}) (end 4.5 {-XIAO_L / 2:.3f}) (stroke (width 0.12) (type default)) (fill none) (layer "B.Fab"))',
             '(fp_text user "XIAO (under, flat side up)" (at 0 -9.2 0) (layer "B.Fab") (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))']
    lines.append(")")
    with open(os.path.join(pretty, "XIAO_ESP32S3_Hanging.kicad_mod"), "w") as f:
        f.write("\n".join(lines) + "\n")


# --- schematic ----------------------------------------------------------------

# on the 2.54mm grid so every pin lands on the connection grid
SCH_POS = {ref: (round(x / 2.54) * 2.54, round(y / 2.54) * 2.54) for ref, (x, y) in
           {"U2": (40, 70), "J7": (15, 70), "J8": (75, 70), "C2": (110, 70), "C3": (130, 70), "U1": (175, 70),
            "J1": (30, 150), "J2": (75, 150), "J3": (120, 150), "J4": (165, 150), "J5": (210, 150), "J6": (255, 150)}.items()}


def all_libs(symbols):
    libs = {"Device:C": lib_symbol("Device", "C", f"{KICAD}/symbols/Device.kicad_sym")}
    for name, block in symbols.items():
        libs[f"{LIB}:{name}"] = block.replace(f'(symbol "{name}"', f'(symbol "{LIB}:{name}"', 1)
    return libs


def write_schematic(libs, nets_of):
    root = uid()
    out = [f'(kicad_sch (version 20231120) (generator "make.py") (generator_version "10.0") (uuid "{root}") (paper "A4")',
           f'(title_block (title "dodecahedron-earth {NAME}") (rev "{REV}") (comment 1 "XIAO ESP32-S3 + 74HC138 + 6 soldered cables (PH2.0 at the display) to 1.28 inch round LCDs"))',
           "(lib_symbols", *libs.values(), ")"]
    for ref, (lib_id, value, fp, lcsc, _, _) in PARTS.items():
        if lib_id is None:
            continue  # board only (the XIAO's outline)
        nets = nets_of[ref]
        x, y = SCH_POS[ref]
        pins = pins_of(libs[lib_id])
        props = [("Reference", ref, 0, -1), ("Value", value, 0, 1), ("Footprint", fp, 0, 0), ("Datasheet", "", 0, 0)]
        if lcsc:
            props.append(("LCSC", lcsc, 0, 0))
        out.append(f'(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom {"yes" if lcsc else "no"}) (on_board {"yes" if fp else "no"}) (dnp no) (uuid "{uid()}")')
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


def place_socket(board, fp, ref):
    """J7 (the D0..D6 column) or J8 on the underside, its pins on the XIAO pins of that column.
    Returns pin number -> XIAO pin name."""
    names = [n for n, (x, _) in XIAO_COL.items() if (x > 0) == (ref == "J7")]
    targets = [xiao_pad(n) for n in names]
    board.Add(fp)
    fp.SetPosition(pt((0.0, 0.0)))
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees((XIAO_PSI + rot) % 360)
        cs = [cup(p.GetPosition()) for p in fp.Pads()]
        if len({round(uv(XIAO_PSI, q)[0], 2) for q in cs}) == 1:  # the pins in a line along the column
            break
    cx = sum(q[0] for q in cs) / len(cs) - sum(t[0] for t in targets) / len(targets)
    cy = sum(q[1] for q in cs) / len(cs) - sum(t[1] for t in targets) / len(targets)
    fp.SetPosition(pt(add(cup(fp.GetPosition()), (-cx, -cy))))
    out = {}
    for p in fp.Pads():
        c = cup(p.GetPosition())
        name = min(names, key=lambda n: math.dist(xiao_pad(n), c))
        assert math.dist(xiao_pad(name), c) < 0.01, (ref, p.GetNumber())
        out[int(p.GetNumber())] = name
    return out


def socket_nets(ref):
    """J7's or J8's pin number -> net (the net of the XIAO pin it holds; None if that pin is unused)."""
    fp = load_fp(SOCKET_FP)
    return {k: XIAO_NETS.get(n) for k, n in place_socket(pcbnew.BOARD(), fp, ref).items()}


def write_board(libs, nets_of, plan):
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
        if not fp_id:
            continue
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
        if ref in ("C2", "C3", "U1", "J7", "J8", "X1"):
            fp.Reference().SetVisible(False)  # see the schematic
        if place == "socket":
            place_socket(board, fp, ref)
            fp.Value().SetVisible(False)
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        else:
            board.Add(fp)
            fp.SetPosition(pt(place[:2]))
            fp.SetOrientationDegrees(place[2] % 360)
        if lib_id is None:
            continue
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
    labels += [("BASE", frame(J6_THETA, J6_U, -6.6), pcbnew.F_SilkS, along(J6_THETA + 90)),
               ("J6 base", frame(J6_THETA, J6_U, -6.6), pcbnew.B_SilkS, along(J6_THETA + 90)),
               (f"hub6_one rev {REV}", mul(13.5, e(18)), pcbnew.B_SilkS, along(18))]
    # Every cable hole's signal (PH_PINS), on both sides: a wire in the wrong hole is the easy
    # mistake. Side rows: just outside each hole, reading outward. J6: outward of its outer row and
    # inward of its inner row, reading along J6_THETA.
    def radial(theta):
        a = theta % 360
        return a - 180 if 90 < a <= 270 else a
    for d in range(5):
        for k in range(1, 9):
            q = add(row_pad(d, k), mul(2.25, e(W_THETA[d])))
            for layer in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                labels.append((PH_PINS[k - 1], q, layer, radial(W_THETA[d])))
    for k in range(1, 9):
        u, v = uv(J6_THETA, j6_pad(k))
        q = frame(J6_THETA, u + (2.25 if u > J6_U else -2.25), v)
        for layer in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            labels.append((PH_PINS[k - 1], q, layer, radial(J6_THETA)))
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

    route(board, net, plan)

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
# Drawn here, not autorouted, except the chip selects' B.Cu parts (router.py). B.Cu has the rings,
# the chip selects inside them and GND; F.Cu every other line, each straight or nearly.
TRACK_W, POWER_W, VIA_D, VIA_DRILL = 0.2, 0.3, 0.6, 0.3
CLEAR = 0.15
RING_STEP_DEG = 3.0
GND_VIAS_U1 = [(-0.8, 0.0), (-0.8, 4.445)]  # under U1's body (its frame): pins 4 and 5 share one, pin 8 the other


def row_pad(d, num):
    """Cup coordinates of pad num of side row d (pin 1 counter-clockwise)."""
    return add(mul(W_R, e(W_THETA[d])), mul(8.89 - 2.54 * (num - 1), e(W_THETA[d] + 90)))


J6_LOCAL = {1: (-3.81, -1.27), 2: (-1.27, -1.27), 3: (1.27, -1.27), 4: (3.81, -1.27),
            5: (3.81, 1.27), 6: (1.27, 1.27), 7: (-1.27, 1.27), 8: (-3.81, 1.27)}


def j6_pad(num):
    phi = J6_THETA - 90
    x, y = J6_LOCAL[num]
    return add(mul(J6_U, e(J6_THETA)), mul(x, e(phi)), mul(y, e(phi - 90)))


def u1_pad(num):
    if num <= 8:
        return u1_local(-2.475, -4.445 + 1.27 * (num - 1))
    return u1_local(2.475, 4.445 - 1.27 * (num - 9))


def uv(theta, p):
    return (p[0] * e(theta)[0] + p[1] * e(theta)[1], p[0] * e(theta + 90)[0] + p[1] * e(theta + 90)[1])


def ring_end(name, b, d):
    """The point b + s d (d a unit vector, s > 0) where the line first meets name's ring."""
    bd = b[0] * d[0] + b[1] * d[1]
    root = math.sqrt(bd * bd - (b[0] ** 2 + b[1] ** 2 - RING[name] ** 2))
    s = min(x for x in (-bd - root, -bd + root) if x > 0)
    return add(b, mul(s, d))


def fixed_wiring():
    """Every F.Cu line and via but the chip selects': ([(net, points, width)], [(net, via)])."""
    lines, vias = [], []

    def to_ring(name, pts, d):
        end = ring_end(name, pts[-1], d)
        lines.append((name, pts + [end], POWER_W if name == "+3V3" else TRACK_W))
        vias.append((name, end))

    # the side rows: radial stubs to the rings; GND to a via inside them
    for d in range(5):
        for num, name in header_nets(d).items():
            p = row_pad(d, num)
            r = math.hypot(*p)
            unit = (p[0] / r, p[1] / r)
            if name in RING:
                to_ring(name, [p], mul(-1, unit))
            elif name == "GND":
                lines.append((name, [p, mul(GND_VIA_R, unit)], POWER_W))
                vias.append((name, mul(GND_VIA_R, unit)))

    def corner(theta, u_out, group):
        """group: (lateral, net, start points), in order along theta + 90."""
        k = len(group)
        for i, (v, name, pts) in enumerate(sorted(group)):
            t = (i - (k - 1) / 2) * 1.0
            to_ring(name, pts + [frame(theta, u_out + CLEAR_U, v), frame(theta, CORNER_U, t)], e(theta))

    # J6 through the corner at J6_THETA: the outer row's pads straight out, the inner row's through
    # the gaps between the outer pads
    u_out = J6_U + 1.27
    group = []
    for num, name in header_nets(5).items():
        if name not in RING:
            continue
        u, v = uv(J6_THETA, j6_pad(num))
        if u > J6_U:
            group.append((v, name, [j6_pad(num)]))
        else:
            group.append((v - 1.27, name, [j6_pad(num), frame(J6_THETA, J6_U, v - 1.27)]))
    corner(J6_THETA, u_out, group)
    # the XIAO's bus pins through the corner at XIAO_PSI
    group = []
    for pin, name in XIAO_NETS.items():
        if name in BUS_PIN:
            u, v = uv(XIAO_PSI, xiao_pad(pin))
            group.append((v, name, [xiao_pad(pin)]))
    corner(XIAO_PSI, uv(XIAO_PSI, xiao_pad("D0"))[0], group)
    # the XIAO's 3V3: straight out, away from the bus, to the 3V3 ring
    v3 = xiao_pad("3V3")
    to_ring("+3V3", [v3], e(XIAO_PSI + 180))
    # A0..A2 straight to U1's pins 1..3
    for k, a in enumerate(("D10", "D9", "D8")):
        lines.append((XIAO_NETS[a], [xiao_pad(a), u1_pad(1 + k)], TRACK_W))
    # 3V3 past C2 and C3, then up into pin 16, round the pin 1 end; E3 (pin 6) from pin 16 under the body
    c1 = [cap_pad("C2", 1), cap_pad("C3", 1)]
    lines.append(("+3V3", [v3, c1[0], c1[1], add(c1[1], mul(uv(XIAO_PSI, u1_pad(16))[0] - uv(XIAO_PSI, c1[1])[0], e(XIAO_PSI))), u1_pad(16)], POWER_W))
    lines.append(("+3V3", [u1_pad(16), u1_local(0.9, -3.6), u1_local(0.9, 1.6), u1_local(-1.6, 1.905), u1_pad(6)], POWER_W))
    # GND: U1's pins 4, 5 and 8 to vias under its body; the capacitors' pad 2 to vias beyond
    a, b = GND_VIAS_U1
    lines.append(("GND", [u1_pad(4), u1_local(*a), u1_pad(5)], POWER_W))
    vias.append(("GND", u1_local(*a)))
    lines.append(("GND", [u1_pad(8), u1_local(*b)], POWER_W))
    vias.append(("GND", u1_local(*b)))
    for ref in ("C2", "C3"):
        p1, p2 = cap_pad(ref, 1), cap_pad(ref, 2)
        dd = (p2[0] - p1[0], p2[1] - p1[1])
        n = math.hypot(*dd)
        v = add(p2, mul(1.05 / n, dd))
        lines.append(("GND", [p2, v], POWER_W))
        vias.append(("GND", v))
    return lines, vias


def cap_pad(ref, num):
    x, y, rot = PARTS[ref][5]
    half = 0.95 if ref == "C2" else 0.775
    return add((x, y), mul(-half if num == 1 else half, e(rot)))


def plan_chip_selects():
    """Which U1 output goes to which display, each side row's lane via, and the B.Cu paths."""
    from shapely.geometry import LineString, Point
    from router import Router
    lines, vias = fixed_wiring()
    shapes = [(LineString(pts).buffer(w / 2, 4), n) for n, pts, w in lines] + [(Point(p).buffer(VIA_D / 2, 8), n) for n, p in vias]
    pads = [(row_pad(d, k), 0.85, header_nets(d)[k]) for d in range(5) for k in range(1, 9)]
    pads += [(j6_pad(k), 0.85, header_nets(5)[k]) for k in range(1, 9)]
    # the sockets' pads: 1.7 mm, pin 1 square (its corners reach 0.85 x sqrt 2)
    square = {place_socket(pcbnew.BOARD(), load_fp(SOCKET_FP), ref)[1] for ref in ("J7", "J8")}
    pads += [(xiao_pad(n), 0.85 * (math.sqrt(2) if n in square else 1.0), XIAO_NETS.get(n, n)) for n in XIAO_COL]
    shapes += [(Point(c).buffer(r, 8), n) for c, r, n in pads]
    y_via = {p: u1_local(Y_VIA_X, 4.445 - 1.27 * (p - 9)) for p in range(9, 16)}

    def lanes(d):
        target = row_pad(d, 5)
        a0 = math.degrees(math.atan2(target[1], target[0]))
        mine = f"LCD_CS{d}"
        out = []
        for r in LANE_R:
            for delta in LANE_DELTA:
                v = mul(r, e(a0 + delta))
                line = LineString([v, target]).buffer(TRACK_W / 2, 4)
                vc = Point(v).buffer(VIA_D / 2, 8)
                if all(n == mine or (line.distance(sh) >= CLEAR and vc.distance(sh) >= CLEAR) for sh, n in shapes):
                    out.append((abs(delta) + 0.3 * (r - LANE_R[0]), v))
        return [v for _, v in sorted(out)][:10]

    # B.Cu obstacles: the through-hole pads and every via inside the rings
    keep = TRACK_W / 2 + CLEAR
    obstacles = [(c, r + keep) for c, r, _ in pads if math.hypot(*c) < BCU_LIMIT + 2]
    obstacles += [(p, VIA_D / 2 + keep) for _, p in vias if math.hypot(*p) < BCU_LIMIT + 1]
    waypoints = []
    for sx in (7.62, -7.62):
        for k in range(6):
            waypoints.append(xf(sx + XIAO_X, -6.35 + 2.54 * k + XIAO_Y))
    # the target pad (J6 pin 5) is not an obstacle for its own path
    j6_cs = j6_pad(5)
    obstacles = [o for o in obstacles if math.dist(o[0], j6_cs) > 1e-6]
    router = Router(obstacles, waypoints, BCU_LIMIT, TRACK_W, CLEAR)
    cands = {d: lanes(d) for d in range(5)}
    cands[5] = [j6_cs]
    print("lane candidates:", {d: len(c) for d, c in cands.items()}, flush=True)
    # The outputs in the order the lines leave round the chip (seen from above, counter-clockwise
    # in the XIAO's frame from the -y end of the output side): plate 3 and plate 2 round the -y end
    # (the USB-C end), plate 1, plate 5, the base, plate 4 round the +y end; so no two cross. The
    # lines that leave straight go first.
    order = [0, 4, 5, 1, 3, 2]
    chosen = {}

    def rec(i, used_pins):
        if i == len(order):
            return True
        d = order[i]
        for pin in (CS_OUTPUT[d],):
            for lane in cands[d]:
                others = [(y_via[q], VIA_D / 2 + keep) for q in range(9, 16) if q != pin]
                others += [(c["lane"], VIA_D / 2 + keep) for c in chosen.values() if c["lane"] != j6_cs]
                if d != 5:
                    others.append((j6_cs, 0.85 + keep))
                if any(math.dist(lane, c["lane"]) < VIA_D + CLEAR for c in chosen.values()):
                    continue
                path = router.route(y_via[pin], lane, [c["path"] for c in chosen.values()], others)
                if path is None:
                    continue
                chosen[d] = {"pin": pin, "lane": lane, "path": path}
                if rec(i + 1, used_pins | {pin}):
                    return True
                del chosen[d]
        return False

    if not rec(0, set()):
        raise SystemExit("no plan for the chip selects")
    for d in sorted(chosen):
        print(f"  display {d}: U1 pin {chosen[d]['pin']} (Y{15 - chosen[d]['pin']}), {len(chosen[d]['path'])} points on B.Cu")
    return {"output": {d: c["pin"] for d, c in chosen.items()}, "lane": {d: c["lane"] for d, c in chosen.items()},
            "path": {d: c["path"] for d, c in chosen.items()}, "y_via": y_via}


def route(board, net, plan):
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

    lines, vias = fixed_wiring()
    for name, pts, w in lines:
        track(name, pts, width=w)
    for name, p in vias:
        via(name, p)
    on_ring = {name: [math.degrees(math.atan2(p[1], p[0])) % 360 for n, p in vias if n == name and abs(math.hypot(*p) - RING[name]) < 1e-6]
               for name in RING}
    # the chip selects: U1's output pad -> its via; B.Cu -> the lane via; F.Cu -> the row's pin 5
    for d, pin in plan["output"].items():
        name = f"LCD_CS{d}"
        yv = plan["y_via"][pin]
        track(name, [u1_pad(pin), yv])
        via(name, yv)
        track(name, plan["path"][d], layer=pcbnew.B_Cu)
        if d < 5:
            via(name, plan["lane"][d])
            track(name, [plan["lane"][d], row_pad(d, 5)])
    # the rings: closed circles through every via on them, in steps of RING_STEP_DEG
    for name, radius in RING.items():
        stops = sorted(set(on_ring[name]) | {round(a * RING_STEP_DEG, 6) for a in range(int(360 / RING_STEP_DEG))})
        pts = [mul(radius, e(a)) for a in stops]
        track(name, pts + pts[:1], layer=pcbnew.B_Cu, width=RING_W.get(name, TRACK_W))


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
        for lib in ("Capacitor_SMD", "Connector_PinSocket_2.54mm", "Package_SO"):
            f.write(f'  (lib (name "{lib}") (type "KiCad") (uri "${{KICAD10_FOOTPRINT_DIR}}/{lib}.pretty") (options "") (descr ""))\n')
        f.write(")\n")


def main():
    symbols = project_symbols()
    libs = all_libs(symbols)
    write_symbol_lib(symbols)
    write_footprints()
    write_project()
    nets_of = {ref: dict(p[4]) if p[4] is not None else socket_nets(ref) for ref, p in PARTS.items()}
    plan = plan_chip_selects()
    for d, pin in plan["output"].items():
        nets_of["U1"][pin] = f"LCD_CS{d}"
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    write_schematic(libs, nets_of)
    write_board(libs, nets_of, plan)
    print(f"wrote {NAME}.kicad_sch, {NAME}.kicad_pcb")


if __name__ == "__main__":
    main()
