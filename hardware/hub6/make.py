"""Generate the hub6 KiCad project: the board that drives the six 1.28 inch
round LCDs (GC9A01, PH2.0 8-pin) of one cup of the dodecahedron.

    /usr/bin/python3 make.py      # needs KiCad 10's pcbnew module

One XIAO ESP32-S3 (in pin sockets) drives the six displays over one SPI bus:
DIN, CLK, DC, RST, BL and the 3.3V supply are shared, and each display has its
own chip select straight from a XIAO pin (all 11 pins are used). Six PH2.0
8-pin headers sit on the six edges of a regular hexagon, in the order the
cables come out of the cup (README.md), the XIAO in the middle. Everything
JLCPCB places is on the top side (Economic PCBA is single sided, and takes 4
layers).

Writes the schematic, the board with every part placed and every connection
drawn (there is no autorouter step: see preroute), the project's symbol and
footprint libraries, and the library tables. check.sh runs ERC, DRC and the
schematic parity check, test_hub6.py the netlist and the geometry.

The parts and nets below are the single source for both the schematic and
the board. assign.py found which XIAO pin carries which signal.
"""
import json
import math
import os
import re
import uuid

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "hub6"
LIB = "dodecahedron-earth"
KICAD = "/usr/share/kicad"
A_IN = 22.5  # hexagon: centre to the middle of an edge, mm
R_CIRC = A_IN / math.cos(math.radians(30))
ORIGIN = (100.0 + R_CIRC, 100.0 + R_CIRC)  # the board's centre on the PCB sheet

# --- nets -------------------------------------------------------------------

# XIAO ESP32-S3 pin -> net (pin 1 = D0 ... 7 = D6, 8 = D7 ... 11 = D10, 12 3V3, 13 GND, 14 5V).
# Which pin carries which signal was found by assign.py: with this table every line is a
# short straight run that crosses nothing. SPI is on the GPIO matrix, so any pins do.
# D2 (GPIO3) is a strapping pin and D6/D7 (GPIO43/44) are UART0; none is driven at boot here.
XIAO = {
    1: "LCD_CS4",  # D0
    2: "LCD_CS3",  # D1
    3: "LCD_DIN",  # D2 (SPI MOSI)
    4: "LCD_CS1",  # D3
    5: "LCD_CS5",  # D4
    6: "LCD_CLK",  # D5 (SPI SCK)
    7: "LCD_CS0",  # D6
    8: "LCD_DC",  # D7
    9: "LCD_RST",  # D8
    10: "LCD_CS2",  # D9
    11: "LCD_BL",  # D10
    12: "+3V3",
    13: "GND",
    14: None,  # 5V: not used; the displays run on 3V3 (see header_nets)
}
XIAO_PINS = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "3V3", "GND", "5V"]

# The six displays, by plate number counting counter-clockwise from above in
# the cup standing on its base (simulate/v0.0.5/magnets.csv), then the base.
# Display d's cable goes to header J(d+1) and its chip select is net LCD_CS(d).
DISPLAYS = ["plate 1", "plate 2", "plate 3", "plate 4", "plate 5", "base"]

# The display's PH2.0 pins, 1 to 8 (Waveshare 1.28inch LCD Module; the cable is 1:1).
# VCC must be 3.3V: the module's TXB0108 level shifter takes its header-side logic
# levels from VCC, and at 5V it wants 0.65 x 5V = 3.25V for a high, which a 3.3V
# XIAO pin does not guarantee (ESP32-S3 VOH min 2.64V); at 3.3V it wants 2.15V.
PH_PINS = ["VCC", "GND", "DIN", "CLK", "CS", "DC", "RST", "BL"]


def header_nets(d):
    return {1: "+3V3", 2: "GND", 3: "LCD_DIN", 4: "LCD_CLK", 5: f"LCD_CS{d}", 6: "LCD_DC", 7: "LCD_RST", 8: "LCD_BL"}


# --- geometry -----------------------------------------------------------------
# Board coordinates: x right, y down, as KiCad draws the top side; (0, 0) is the
# hexagon's centre. A direction "theta" counts counter-clockwise on the screen,
# which is counter-clockwise seen from above: the same as the cup's azimuth.
# Headers sit at -18 + 60 k degrees (k = 0..5), the least turn from the cables'
# azimuths in the cup (plate 3 342, plate 4 54, plate 5 126, base 162, plate 1
# 198, plate 2 270). The hexagon's edges face them, its corners are 30 away.
HEADER_THETA = {d: -18 + 60 * ((d + 4) % 6) for d in range(6)}  # d = 0 is plate 1
HEADER_R = A_IN - 3.3  # pin row; the 18.0 x 4.6 body reaches 2.9 either way (the model's side is not certain), 0.35 to the edge
USB_THETA = 72  # the XIAO's USB-C points at a corner
XIAO_PSI = USB_THETA + 90  # footprint turn that takes local +y (USB-C) to USB_THETA


def polar(r, theta):
    t = math.radians(theta)
    return (r * math.cos(t), -r * math.sin(t))


def xiao_frame(lx, ly):
    """XIAO-local (USB-C toward +y) to board coordinates."""
    c, s = math.cos(math.radians(XIAO_PSI)), math.sin(math.radians(XIAO_PSI))
    return (lx * c + ly * s, -lx * s + ly * c)


def hex_corners():
    return [polar(R_CIRC, 12 + 60 * k) for k in range(6)]


# --- parts ------------------------------------------------------------------
# ref: (symbol, value, footprint, LCSC part, pin -> net, (x, y, rotation) on the board relative to its centre)
HEADER_FP = f"{LIB}:PH2.0_8P_Vertical_THT_C157974"
SOCKET_FP = "Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical"


def xiao_part(lx, ly, rot):
    x, y = xiao_frame(lx, ly)
    return (x, y, (rot + XIAO_PSI) % 360)


PARTS = {}
for _d in range(6):
    _x, _y = polar(HEADER_R, HEADER_THETA[_d])
    PARTS[f"J{_d + 1}"] = (f"{LIB}:PH2.0_8P", DISPLAYS[_d], HEADER_FP, "C157974", header_nets(_d),
                           (_x, _y, (HEADER_THETA[_d] + 90) % 360))
PARTS.update({
    # The XIAO itself is plugged in by hand: on the schematic only. Its two
    # female sockets are assembled. With the USB-C down, J7 is the right row
    # (XIAO pins 1-7, D0 at the bottom) and J8 the left row (pins 8-14, 5V at
    # the bottom); the rows are 15.24 apart (Seeed's XIAO-ESP32-S3-DIP).
    "U2": (f"{LIB}:XIAO_ESP32S3", "XIAO ESP32S3", "", "", XIAO, None),
    "J7": (f"{LIB}:Socket_1x07", "XIAO D0-D6", SOCKET_FP, "C2832270", {k: XIAO[k] for k in range(1, 8)},
           xiao_part(7.62, 7.62, 180)),
    "J8": (f"{LIB}:Socket_1x07", "XIAO D7-5V", SOCKET_FP, "C2832270", {k: XIAO[k + 7] for k in range(1, 8)},
           xiao_part(-7.62, -7.62, 0)),
    "C2": ("Device:C", "10uF", "Capacitor_SMD:C_0805_2012Metric", "C15850", {1: "+3V3", 2: "GND"}, xiao_part(0, 0, 90)),  # bulk for the six displays (about 190mA), under the XIAO between the socket rows
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
    xiao_left = [(str(i), XIAO_PINS[i - 1], "bidirectional") for i in range(1, 8)]
    xiao_right = [("14", "5V", "power_out"), ("13", "GND", "power_out"), ("12", "3V3", "power_out")] + [
        (str(i), XIAO_PINS[i - 1], "bidirectional") for i in (11, 10, 9, 8)]
    return {
        "XIAO_ESP32S3": box_symbol("XIAO_ESP32S3", "U", xiao_left, xiao_right),
        "PH2.0_8P": box_symbol("PH2.0_8P", "J", [(str(i), PH_PINS[i - 1], "passive") for i in range(1, 9)], [], width=5.08),
        "Socket_1x07": box_symbol("Socket_1x07", "J", [(str(i), f"{i}", "passive") for i in range(1, 8)], [], width=5.08),
    }


def write_symbol_lib(symbols):
    body = "\n".join(symbols.values())
    with open(os.path.join(HERE, f"{LIB}.kicad_sym"), "w") as f:
        f.write(f"(kicad_symbol_lib (version 20231120) (generator \"make.py\")\n{body}\n)\n")


# --- project footprints -------------------------------------------------------


def write_footprints():
    os.makedirs(os.path.join(HERE, f"{LIB}.pretty"), exist_ok=True)
    # JST B8B-PH-K-S, vertical, through hole, 2.0mm pitch (LCSC C157974). Pads
    # and origin as in JLCPCB's own EasyEDA footprint for C157974 (read with
    # JLC2KiCadLib): 1.4mm pads with 0.9mm drills at 2.0 pitch on y = 0, pin 1
    # (square) at +x. The body is 18.0 x 4.6 (3D model: 2.9 and 1.7 from the pin
    # row, which side is not certain), so the courtyard takes 2.9 each way. The
    # surface-mount B8B-PH-SM4-TB (C265441, body 20.0) was tried first: six of
    # them 60 degrees apart overlap at their inner corners unless the board is
    # 56.6mm across the corners.
    name = "PH2.0_8P_Vertical_THT_C157974"
    lines = [f'(footprint "{name}" (version 20240108) (generator "make.py") (layer "F.Cu")',
             '(descr "JST B8B-PH-K-S: wire-to-board header, PH 2.0mm, 8 pins, vertical, through hole (LCSC C157974)")',
             '(attr through_hole)',
             '(property "Reference" "REF**" (at 0 -4.6 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
             '(property "Value" "PH2.0_8P" (at 0 4.6 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
             '(fp_rect (start -9.0 -2.9) (end 9.0 2.9) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
             '(fp_rect (start -9.1 -3.0) (end 9.1 3.0) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
             '(fp_text user "1" (at 7 -3.8 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))']
    for p in range(1, 9):
        shape = "rect" if p == 1 else "circle"
        lines.append(f'(pad "{p}" thru_hole {shape} (at {7 - 2 * (p - 1):.2f} 0) (size 1.4 1.4) (drill 0.9) (layers "*.Cu" "*.Mask"))')
    lines.append(")")
    with open(os.path.join(HERE, f"{LIB}.pretty", f"{name}.kicad_mod"), "w") as f:
        f.write("\n".join(lines) + "\n")

    # Where the XIAO ESP32-S3 sits on its sockets (J7, J8): its outline and
    # USB-C on F.Fab, which row is D0 and which 5V on the silkscreen. No pads;
    # placed as a board-only footprint over the sockets. USB-C toward +y.
    lines = ['(footprint "XIAO_ESP32S3_Outline" (version 20240108) (generator "make.py") (layer "F.Cu")',
             '(descr "Outline of a Seeed XIAO ESP32-S3 on two 1x7 sockets 15.24 apart, USB-C toward +y")',
             '(attr board_only exclude_from_pos_files exclude_from_bom)',
             '(property "Reference" "REF**" (at 0 -12 0) (layer "F.Fab") (hide yes) (effects (font (size 1 1) (thickness 0.15))))',
             '(property "Value" "XIAO" (at 0 0 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
             '(fp_rect (start -8.95 -10.47) (end 8.95 10.6) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
             '(fp_rect (start -4.5 10.6) (end 4.5 12.1) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
             '(fp_text user "XIAO" (at 0 -7.5 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
             '(fp_text user "USB" (at 0 8.5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
             '(fp_text user "D0" (at 10.2 7.62 90) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             '(fp_text user "5V" (at -10.2 7.62 90) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
             ")"]
    with open(os.path.join(HERE, f"{LIB}.pretty", "XIAO_ESP32S3_Outline.kicad_mod"), "w") as f:
        f.write("\n".join(lines) + "\n")


# --- schematic ----------------------------------------------------------------

# on the 2.54mm grid so every pin lands on the connection grid
SCH_POS = {ref: (round(x / 2.54) * 2.54, round(y / 2.54) * 2.54) for ref, (x, y) in
           {"U2": (60, 70), "C2": (130, 70), "J7": (30, 70), "J8": (95, 70),
            "J1": (30, 150), "J2": (75, 150), "J3": (120, 150), "J4": (165, 150), "J5": (210, 150), "J6": (255, 150)}.items()}


def all_libs(symbols):
    libs = {
        "Device:C": lib_symbol("Device", "C", f"{KICAD}/symbols/Device.kicad_sym"),
    }
    for name, block in symbols.items():
        libs[f"{LIB}:{name}"] = block.replace(f'(symbol "{name}"', f'(symbol "{LIB}:{name}"', 1)
    return libs


def write_schematic(libs):
    root = uid()
    out = [f'(kicad_sch (version 20231120) (generator "make.py") (generator_version "10.0") (uuid "{root}") (paper "A4")',
           f'(title_block (title "dodecahedron-earth {NAME}") (rev "A") (comment 1 "XIAO ESP32-S3 + 6 x PH2.0 8-pin to 1.28 inch round LCDs"))',
           "(lib_symbols", *libs.values(), ")"]
    for ref, (lib_id, value, fp, lcsc, nets, _) in PARTS.items():
        x, y = SCH_POS[ref]
        pins = pins_of(libs[lib_id])
        props = [("Reference", ref, 0, -1), ("Value", value, 0, 1), ("Footprint", fp, 0, 0), ("Datasheet", "", 0, 0)]
        if lcsc:
            props.append(("LCSC", lcsc, 0, 0))
        out.append(f'(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom {"yes" if fp else "no"}) (on_board {"yes" if fp else "no"}) (dnp no) (uuid "{uid()}")')
        top = min(-py for _, py in pins.values()) + y
        bottom = max(-py for _, py in pins.values()) + y
        for k, (pname, pval, _, where) in enumerate(props):
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


def pt(x, y):
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


def write_board(libs):
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.3)
    corners = hex_corners()
    # fabrication files are written from the lower left corner of the board's bounding box
    left = min(x for x, _ in corners)
    bottom = max(y for _, y in corners)
    ds.SetAuxOrigin(pt(left, bottom))
    ds.SetGridOrigin(pt(left, bottom))
    nets = {}

    def net(name):
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            nets[name] = n
        return nets[name]

    for ref, (_, value, fp_id, lcsc, pin_nets, place) in PARTS.items():
        if not fp_id:
            continue
        x, y, rot = place
        lib, name = fp_id.split(":")
        path = os.path.join(HERE, f"{LIB}.pretty") if lib == LIB else f"{KICAD}/footprints/{lib}.pretty"
        fp = pcbnew.FootprintLoad(path, name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(value)
        if lcsc:
            fp.SetField("LCSC", lcsc)
            field = fp.GetField("LCSC")
            field.SetVisible(False)
            field.SetLayer(pcbnew.F_Fab)
        if fp_id == SOCKET_FP:
            fp.Reference().SetVisible(False)  # the XIAO outline labels the rows
        if fp_id == HEADER_FP:
            fp.Reference().SetVisible(False)  # a label of our own, below
            fp.Value().SetVisible(False)
        if ref == "C2":
            fp.Reference().SetVisible(False)  # under the XIAO; see the schematic
        names = pin_names(libs[PARTS[ref][0]])
        board.Add(fp)
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num:
                # the schematic names an unconnected pin's net after the pin
                pad.SetNet(net(pin_nets.get(int(num)) or unconnected_net(ref, num, names.get(num))))
    fp = pcbnew.FootprintLoad(os.path.join(HERE, f"{LIB}.pretty"), "XIAO_ESP32S3_Outline")
    fp.SetFPID(pcbnew.LIB_ID(LIB, "XIAO_ESP32S3_Outline"))
    fp.SetReference("X1")
    fp.Reference().SetVisible(False)
    board.Add(fp)
    fp.SetPosition(pt(0, 0))
    fp.SetOrientationDegrees(XIAO_PSI % 360)

    for (x0, y0), (x1, y1) in zip(corners, corners[1:] + corners[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pt(x0, y0))
        seg.SetEnd(pt(x1, y1))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(mm(0.1))
        board.Add(seg)

    short = ["P1", "P2", "P3", "P4", "P5", "BASE"]
    labels = [(short[d], *polar(HEADER_R - 6.0, HEADER_THETA[d]), 0.8, pcbnew.F_SilkS) for d in range(6)]
    labels += [(f"J{d + 1} {DISPLAYS[d]}", *polar(HEADER_R - 6.0, HEADER_THETA[d]), 0.8, pcbnew.B_SilkS) for d in range(6)]
    labels += [("hub6 rev A", 0, 0, 0.8, pcbnew.B_SilkS)]
    for text, x, y, size, layer in labels:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(pt(x, y))
        t.SetLayer(layer)
        t.SetMirrored(layer == pcbnew.B_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(0.15))
        board.Add(t)

    # Planes: In1 GND, B.Cu +3V3 (every through-hole pad reaches them directly). F.Cu and
    # In2 carry the signals; In2 has the bus rings (preroute).
    for layer, name in ((pcbnew.In1_Cu, "GND"), (pcbnew.B_Cu, "+3V3")):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(net(name))
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in corners:
            p = pt(x, y)
            outline.Append(p.x, p.y)
        zone.SetLocalClearance(mm(0.3))
        zone.SetMinThickness(mm(0.2))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        board.Add(zone)

    preroute(board, net)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(os.path.join(HERE, f"{NAME}.kicad_pcb"))



# The wiring is drawn here, not autorouted (Freerouting stalled on the shared buses, and
# then on the 74HC138's select lines, however the rules were set). Shared bus nets, with the
# header pad that carries each and the radius of its ring on In2: a ring per net round the
# centre, a radial stub on F.Cu from each header pad and from the XIAO pad to a via on the
# ring. Each chip select runs on F.Cu from its XIAO pad to the start of its header's pad-5
# lane, then along the lane. Power is planes: In1 GND, B.Cu +3V3.
BUS = {"LCD_DIN": (3, 12.9), "LCD_CLK": (4, 13.7), "LCD_DC": (6, 14.5), "LCD_RST": (7, 15.3), "LCD_BL": (8, 16.1)}
LANE_START = 11.8  # chip select lines run along the radius from here out to the header
RING_STEP_DEG = 3.0
TRACK_W, VIA_D, VIA_DRILL = 0.2, 0.6, 0.3  # assign.py assumes these


def rel_mm(pos):
    return pcbnew.ToMM(pos.x) - ORIGIN[0], pcbnew.ToMM(pos.y) - ORIGIN[1]


def add_track(board, net, layer, a, b):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(*a) if isinstance(a, tuple) else a)
    t.SetEnd(pt(*b) if isinstance(b, tuple) else b)
    t.SetWidth(mm(TRACK_W))
    t.SetLayer(layer)
    t.SetNet(net)
    board.Add(t)


def add_via(board, net, xy):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(*xy))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(mm(VIA_D))
    v.SetDrill(mm(VIA_DRILL))
    v.SetNet(net)
    board.Add(v)


def preroute(board, net):
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    ring_angles = {name: [] for name in BUS}

    def to_ring(name, pad_xy, pad_pos):
        radius = BUS[name][1]
        r = math.hypot(*pad_xy)
        via = (pad_xy[0] / r * radius, pad_xy[1] / r * radius)
        add_track(board, net(name), pcbnew.F_Cu, pad_pos, via)
        add_via(board, net(name), via)
        ring_angles[name].append(math.degrees(math.atan2(via[1], via[0])) % 360)

    # headers: the five shared pads of each, to the rings
    for d in range(6):
        for pad in fps[f"J{d + 1}"].Pads():
            for name, (pad_no, _) in BUS.items():
                if pad.GetNumber() == str(pad_no):
                    to_ring(name, rel_mm(pad.GetPosition()), pad.GetPosition())
    # the XIAO's pads: a bus signal to its ring, a chip select to its header
    for ref, offset in (("J7", 0), ("J8", 7)):
        for pad in fps[ref].Pads():
            name = XIAO[int(pad.GetNumber()) + offset]
            if name in BUS:
                to_ring(name, rel_mm(pad.GetPosition()), pad.GetPosition())
            elif name and name.startswith("LCD_CS"):
                d = int(name[len("LCD_CS"):])
                target = next(p for p in fps[f"J{d + 1}"].Pads() if p.GetNumber() == "5")
                tx, ty = rel_mm(target.GetPosition())
                r = math.hypot(tx, ty)
                lane = (tx / r * LANE_START, ty / r * LANE_START)
                add_track(board, net(name), pcbnew.F_Cu, pad.GetPosition(), lane)
                add_track(board, net(name), pcbnew.F_Cu, lane, target.GetPosition())
    # the rings: closed circles through every via on them, in steps of RING_STEP_DEG
    for name, (_, radius) in BUS.items():
        stops = sorted(set(ring_angles[name]) | {round(a * RING_STEP_DEG, 6) for a in range(int(360 / RING_STEP_DEG))})
        pts = [(radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a))) for a in stops]
        for a, b in zip(pts, pts[1:] + pts[:1]):
            add_track(board, net(name), pcbnew.In2_Cu, a, b)
    # the bulk capacitor: each pad to a via, which reaches its plane
    c2 = fps["C2"]
    pads = list(c2.Pads())
    for pad in pads:
        other = next(p for p in pads if p is not pad)
        ox, oy = rel_mm(other.GetPosition())
        px, py = rel_mm(pad.GetPosition())
        d = math.hypot(px - ox, py - oy)
        via = (px + (px - ox) / d * 1.5, py + (py - oy) / d * 1.5)
        name = "+3V3" if pad.GetNumber() == "1" else "GND"
        add_track(board, net(name), pcbnew.F_Cu, pad.GetPosition(), via)
        add_via(board, net(name), via)


def write_project():
    pro = {
        "board": {"design_settings": {"rules": {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.6,
                                                "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.3}}},
        "net_settings": {
            "classes": [
                {"name": "Default", "clearance": 0.15, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3},
                {"name": "Power", "clearance": 0.2, "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4},
            ],
            # no wide power tracks: GND and +3V3 are planes (In1, B.Cu) that every through-hole pad reaches directly
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
        for lib in ("Capacitor_SMD", "Connector_PinSocket_2.54mm"):
            f.write(f'  (lib (name "{lib}") (type "KiCad") (uri "${{KICAD10_FOOTPRINT_DIR}}/{lib}.pretty") (options "") (descr ""))\n')
        f.write(")\n")


def main():
    symbols = project_symbols()
    libs = all_libs(symbols)
    write_symbol_lib(symbols)
    write_footprints()
    write_project()
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    write_schematic(libs)
    write_board(libs)
    print(f"wrote {NAME}.kicad_sch, {NAME}.kicad_pcb")


if __name__ == "__main__":
    main()
