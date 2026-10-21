"""Fetch a whole-world zoom level of raster map tiles (Web Mercator, 256 px, {z}/{x}/{y}.png) and turn
it into an equirectangular image that make_earth_faces.py takes in place of Blue Marble.

    ../../.venv/bin/python make_tile_mosaic.py https://tile.yuiseki.net/styles/osm-liberty-no-text-no-icons \\
        --zoom 4 --cache ../../tmp/tiles --out ../../tmp/osm-liberty-equirect.png

Tiles are kept in --cache and not fetched again. Web Mercator stops at 85.05 degrees north and
south; nearer the poles the image repeats the last row (here the polar sea's colour), which fills
the middle of a display centred on a pole.
"""
import argparse
import concurrent.futures
import math
import os
import urllib.request

import numpy as np
from PIL import Image

MAX_LAT = math.degrees(math.atan(math.sinh(math.pi)))  # 85.0511


def fetch(base, cache, z, x, y):
    name = base.rstrip("/").split("/")[-1]
    path = os.path.join(cache, name, str(z), str(x), f"{y}.png")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Python's default User-Agent is refused (403) by the tile server's front end; curl's is not.
        req = urllib.request.Request(f"{base.rstrip('/')}/{z}/{x}/{y}.png", headers={"User-Agent": "exp-dodecahedron-earth/make_tile_mosaic"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    return x, y, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", help="tile URL without /{z}/{x}/{y}.png")
    ap.add_argument("--zoom", type=int, default=4)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    z, n = args.zoom, 2 ** args.zoom
    mosaic = Image.new("RGB", (256 * n, 256 * n))
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        jobs = [pool.submit(fetch, args.base, args.cache, z, x, y) for x in range(n) for y in range(n)]
        for job in concurrent.futures.as_completed(jobs):
            x, y, path = job.result()
            mosaic.paste(Image.open(path).convert("RGB"), (256 * x, 256 * y))
    merc = np.asarray(mosaic)
    size = merc.shape[0]
    # equirectangular: the same width, half as tall; each row's latitude to its Mercator row
    w, h = size, size // 2
    lat = 90 - (np.arange(h) + 0.5) * 180 / h
    lat = np.clip(lat, -MAX_LAT, MAX_LAT)
    yr = (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / math.pi) / 2 * size
    rows = np.clip(np.floor(yr).astype(int), 0, size - 1)
    Image.fromarray(merc[rows, :w]).save(args.out)
    print(f"wrote {args.out} ({w} x {h}) from {n * n} tiles at zoom {z}")


if __name__ == "__main__":
    main()
