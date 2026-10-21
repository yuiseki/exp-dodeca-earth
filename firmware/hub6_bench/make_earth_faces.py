"""Cut a whole-Earth image into the six round displays of one cup: each display shows the part of
the globe behind it, seen from the centre of the dodecahedron (a gnomonic projection onto the
plane of the screen), as through a window. Writes earth_faces.h (RGB565, 240 x 240 per display,
in the sketch's NAME order: P1..P5, BASE) and a preview PNG.

    ../../.venv/bin/python make_earth_faces.py blue_marble_2002.jpg [--cup upper|lower] [--face P2 --lon 139.77] [--preview out.png]

The input is an equirectangular image (longitude -180..180 left to right, latitude 90..-90 top to
bottom), for example NASA's Blue Marble (public domain), as exp-cubic-earth uses.

Geometry (simulate/dodecahedron.py, simulate/cables.py): M maps each display's plate frame to the
dodecahedron, centre at the origin, the cup's axis on z (the lower cup opens up, its base at
z = -33.4). The plate's +z points inward. The screen's "up" (with the sketch's 180 degree turn)
points away from the display's header, plate -y: the side displays read upright with the base
above them when the cup stands on its rim. Its "right" is up x outward, seen from outside.

--cup upper (the default) draws the cup as the upper half of the globe: the upper cup is the lower
one turned 180 degrees about x, so a point (x, y, z) of the cup is (x, -y, -z) on the globe, and the
base is the north pole. --cup lower draws it as the southern half, the base at the south pole.
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../simulate"))
import dodecahedron as dd  # noqa: E402

N = 240
ACTIVE_D = 32.4      # the round LCD's active area, mm (240 px)
SCREEN_OUT = 4.0     # the screen's surface is this far outside the plate's outer face (approximate)
NAMES = ["P1", "P2", "P3", "P4", "P5", "BASE"]


def plates():
    """name -> 4x4 plate-to-dodecahedron transform, for the lower cup (as cables.py)."""
    placed = dd.two_cups(dd.dodecahedron_faces())
    roles = [r for r, *_ in placed]
    M = [dd.plate_to_face(c, n, v) for _, c, n, v, _ in placed]
    centres = [c for _, c, *_ in placed]
    lower = sorted((i for i, r in enumerate(roles) if r == "lower"), key=lambda i: math.atan2(centres[i][1], centres[i][0]))
    out = {f"P{k}": M[i] for k, i in enumerate(lower, 1)}
    out["BASE"] = M[next(i for i, r in enumerate(roles) if r == "base")]
    return out


def face_directions(m, cup):
    """Unit directions from the centre through every pixel of one display, on the globe: (N, N, 3)."""
    r = m[:3, :3]
    outward = -r @ np.array([0, 0, 1.0])
    up = r @ np.array([0, -1.0, 0])
    right = np.cross(up, outward)
    centre = (m @ np.array([0, 0, 0, 1.0]))[:3] + SCREEN_OUT * outward
    pitch = ACTIVE_D / N
    s = (np.arange(N) - (N - 1) / 2) * pitch
    xs, ys = np.meshgrid(s, s)  # ys grows downward on the screen
    p = centre + xs[..., None] * right + (-ys)[..., None] * up
    p /= np.linalg.norm(p, axis=-1, keepdims=True)
    if cup == "upper":
        p = p * np.array([1.0, -1.0, -1.0])
    return p


def sample(img, d, lon0):
    lat = np.degrees(np.arcsin(np.clip(d[..., 2], -1, 1)))
    lon = (np.degrees(np.arctan2(d[..., 1], d[..., 0])) + lon0 + 180) % 360 - 180
    h, w, _ = img.shape
    fx = (lon + 180) / 360 * w - 0.5
    fy = (90 - lat) / 180 * h - 0.5
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    tx, ty = (fx - x0)[..., None], (fy - y0)[..., None]
    def at(x, y):
        return img[np.clip(y, 0, h - 1), x % w].astype(float)
    top = at(x0, y0) * (1 - tx) + at(x0 + 1, y0) * tx
    bot = at(x0, y0 + 1) * (1 - tx) + at(x0 + 1, y0 + 1) * tx
    return np.clip(np.rint(top * (1 - ty) + bot * ty), 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--cup", choices=("upper", "lower"), default="upper")
    ap.add_argument("--face", choices=NAMES[:5], default="P2", help="the side display whose centre gets --lon")
    ap.add_argument("--lon", type=float, default=139.77, help="longitude at the centre of --face (Tokyo)")
    ap.add_argument("--preview", help="also write the six faces side by side to this PNG")
    args = ap.parse_args()
    img = np.asarray(Image.open(args.src).convert("RGB"))
    ms = plates()
    # turn the globe about its axis so that the centre of --face lands on --lon
    c1 = face_directions(ms[args.face], args.cup)[N // 2, N // 2]
    lon0 = args.lon - math.degrees(math.atan2(c1[1], c1[0]))
    yy, xx = np.mgrid[0:N, 0:N]
    inside = (xx - (N - 1) / 2) ** 2 + (yy - (N - 1) / 2) ** 2 <= (N / 2) ** 2
    faces = {}
    for name in NAMES:
        d = face_directions(ms[name], args.cup)
        rgb = sample(img, d, lon0)
        rgb[~inside] = 0
        faces[name] = rgb
        c = d[N // 2, N // 2]
        lat = math.degrees(math.asin(c[2]))
        lon = (math.degrees(math.atan2(c[1], c[0])) + lon0 + 180) % 360 - 180
        print(f"{name:4s} centre at {lat:6.1f} N {lon:7.1f} E")
    with open(os.path.join(HERE, "earth_faces.h"), "w") as f:
        f.write(f"// Generated by make_earth_faces.py from {os.path.basename(args.src)} (--cup {args.cup} --face {args.face} --lon {args.lon}). Do not edit.\n")
        f.write("#pragma once\n#include <stdint.h>\n")
        f.write(f"const uint16_t EARTH_FACES[{len(NAMES)}][{N * N}] PROGMEM = {{\n")
        for name in NAMES:
            rgb = faces[name].astype(np.uint16)
            v = ((rgb[..., 0] & 0xF8) << 8) | ((rgb[..., 1] & 0xFC) << 3) | (rgb[..., 2] >> 3)
            f.write(f"  {{ // {name}\n")
            flat = v.ravel()
            for i in range(0, flat.size, 16):
                f.write("    " + ",".join(f"0x{x:04x}" for x in flat[i:i + 16]) + ",\n")
            f.write("  },\n")
        f.write("};\n")
    if args.preview:
        preview = Image.new("RGB", (N * len(NAMES), N))
        for k, name in enumerate(NAMES):
            preview.paste(Image.fromarray(faces[name]), (k * N, 0))
        preview.save(args.preview)
    print("wrote earth_faces.h")


if __name__ == "__main__":
    main()
