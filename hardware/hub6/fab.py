"""Write the JLCPCB files to build/fab/: Gerbers and drill (zipped), and the
BOM and placement (CPL) for the parts with an LCSC number; then copy the three
files to upload into fab6/.

    /usr/bin/python3 fab.py

Every part with an LCSC number is on the top side (Economic PCBA places one
side only). The display cables are soldered into bare holes (J1-J6), which
have no part; J7, the header to board B, is soldered by hand.
"""
import csv
import os
import shutil
import subprocess

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "build", "fab")
PCB = os.path.join(HERE, "hub6.kicad_pcb")
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
# JLCPCB's zero rotation differs from KiCad's for some footprints. Seen in
# JLCPCB's placement preview for the cubic-earth hub3 (2026-10-19): the
# SOIC-16 at KiCad's 90 showed up standing on end, pin 1 at the lower right;
# at 0 it lies like the pads, pin 1 at the lower left. The 1x7 socket at
# KiCad's 0 and 180 (standing, as on that board) showed up lying across; it
# has no polarity, so +90. Not yet checked for this board.
JLC_ROTATION_OFFSET = {"SOIC-16_3.9x9.9mm_P1.27mm": -90, "PinSocket_1x07_P2.54mm_Vertical": 90}
# JLCPCB places a part by its centre. KiCad's pin sockets have their origin
# on pin 1, so give the centre of their pads instead.
JLC_CENTRE_FROM_PADS = {"PinSocket_1x07_P2.54mm_Vertical"}


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    gerbers = os.path.join(OUT, "gerbers")
    os.makedirs(gerbers)
    subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "--use-drill-file-origin", "-o", gerbers + "/", PCB], check=True)
    subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--drill-origin", "plot", "-o", gerbers + "/", PCB], check=True)
    shutil.make_archive(os.path.join(OUT, "hub6-gerbers"), "zip", gerbers)

    board = pcbnew.LoadBoard(PCB)
    origin = board.GetDesignSettings().GetAuxOrigin()
    rows = {}
    with open(os.path.join(OUT, "hub6-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
            lcsc = fp.GetFieldText("LCSC") if fp.HasField("LCSC") else ""
            if not lcsc:
                continue
            footprint = fp.GetFPID().GetLibItemName().wx_str()
            pos = fp.GetPosition()
            if footprint in JLC_CENTRE_FROM_PADS:
                xs = [p.GetPosition().x for p in fp.Pads()]
                ys = [p.GetPosition().y for p in fp.Pads()]
                pos = pcbnew.VECTOR2I((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)
            x = pcbnew.ToMM(pos.x - origin.x)
            y = -pcbnew.ToMM(pos.y - origin.y)  # JLCPCB: y up
            rotation = (fp.GetOrientationDegrees() + JLC_ROTATION_OFFSET.get(footprint, 0)) % 360
            w.writerow([fp.GetReference(), f"{x:.3f}mm", f"{y:.3f}mm", "Top", f"{rotation:.0f}"])
            # One row per LCSC part. JLCPCB merges rows with the same part
            # number itself and then repeats the designators (J1-J3 given
            # as three rows came back as nine), so never split a part.
            row = rows.setdefault(lcsc, {"values": set(), "footprint": footprint, "refs": []})
            row["values"].add(fp.GetValue())
            row["refs"].append(fp.GetReference())
    with open(os.path.join(OUT, "hub6-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for lcsc, row in sorted(rows.items(), key=lambda kv: kv[1]["refs"][0]):
            values = sorted(row["values"])
            comment = values[0] if len(values) == 1 else row["footprint"]  # no commas in a CSV cell
            w.writerow([comment, ",".join(row["refs"]), row["footprint"], lcsc])
    upload = os.path.join(HERE, "fab6")
    os.makedirs(upload, exist_ok=True)
    for name in ("hub6-gerbers.zip", "hub6-bom.csv", "hub6-cpl.csv"):
        shutil.copy(os.path.join(OUT, name), upload)
    for name in sorted(os.listdir(OUT)):
        print(os.path.join(OUT, name))
    print(f"copied the gerbers, BOM and CPL to {upload}")


if __name__ == "__main__":
    main()
