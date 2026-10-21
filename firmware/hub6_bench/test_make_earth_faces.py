"""Check the directions make_earth_faces.py samples the globe along, for the two --fit modes.

    ../../.venv/bin/python -m pytest -q test_make_earth_faces.py
"""
import math

import numpy as np
import pytest

import make_earth_faces as mef

N = mef.N
SIDES = mef.NAMES[:5]
MS = mef.plates()


def angle(a, b):
    return math.degrees(math.acos(np.clip(np.dot(a, b), -1, 1)))


def normal(name, cup="upper"):
    """The face's outward normal, on the globe."""
    n = -MS[name][:3, :3] @ np.array([0, 0, 1.0])
    return n * np.array([1.0, -1.0, -1.0]) if cup == "upper" else n


def rim(d):
    """The directions on the screen circle's rim (a ring of pixels just inside it)."""
    yy, xx = np.mgrid[0:N, 0:N]
    r = np.hypot(xx - (N - 1) / 2, yy - (N - 1) / 2)
    return d[(r > N / 2 - 1.5) & (r <= N / 2)]


@pytest.mark.parametrize("fit", ["window", "edge"])
def test_north_up_east_right_not_mirrored(fit):
    north = np.array([0, 0, 1.0])
    for name in SIDES:
        d = mef.face_directions(MS[name], "upper", fit)
        c = d[N // 2, N // 2]
        right = d[N // 2, -1] - d[N // 2, 0]
        up = d[0, N // 2] - d[-1, N // 2]
        east = np.cross(north, c)
        assert np.dot(right, east) > 0.99 * np.linalg.norm(right) * np.linalg.norm(east)
        assert np.dot(np.cross(right, up), c) > 0  # seen from outside, as on the screen


def test_window_is_the_view_through_the_screen():
    # the 32.4 mm active area, about 4 mm outside a plate whose face is at the dodecahedron's inradius
    d = mef.face_directions(MS["P2"], "upper", "window")
    assert 22 < max(angle(d[N // 2, N // 2], p) for p in rim(d)) < 25


def test_edge_fit_centres_on_the_face_and_reaches_its_edges():
    for name in mef.NAMES:
        d = mef.face_directions(MS[name], "upper", "edge")
        n = normal(name)
        assert angle(d[N // 2, N // 2], n) < 0.5
        r = [angle(n, p) for p in rim(d)]
        # the ring is up to 1.5 px inside the circle, about 0.4 degrees here
        assert min(r) == pytest.approx(mef.EDGE_ANGLE, abs=0.5)
        assert max(r) == pytest.approx(mef.EDGE_ANGLE, abs=0.5)


def test_edge_fit_neighbours_meet_at_the_edge():
    # The rim point of a display nearest its neighbour's face lies on their shared edge (halfway
    # between the two normals), and the neighbour's rim reaches the same point.
    pairs = [("P1", "P2"), ("P2", "P3"), ("P3", "P4"), ("P4", "P5"), ("P5", "P1")]
    pairs += [(s, "BASE") for s in SIDES]
    for a, b in pairs:
        na, nb = normal(a), normal(b)
        ra = rim(mef.face_directions(MS[a], "upper", "edge"))
        rb = rim(mef.face_directions(MS[b], "upper", "edge"))
        pa = ra[np.argmax(ra @ nb)]
        pb = rb[np.argmax(rb @ na)]
        assert angle(pa, na) == pytest.approx(angle(pa, nb), abs=1.0)
        assert angle(pa, pb) < 1.5


def test_dihedral_geometry():
    # face centre to edge midpoint, seen from the dodecahedron's centre: atan(apothem / inradius)
    assert mef.EDGE_ANGLE == pytest.approx(31.72, abs=0.01)
    assert angle(normal("P1"), normal("P2")) == pytest.approx(2 * mef.EDGE_ANGLE, abs=0.1)
