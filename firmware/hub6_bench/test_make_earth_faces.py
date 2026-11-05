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


def test_hub6_one_placement_is_the_mirror_seen_on_the_bench():
    # hub6_one with the XIAO toward the cup's opening (2026-11-05): seen from outside the base,
    # P1..P5 run counter-clockwise, the model's plates clockwise, and the base display's "up"
    # points at P2 (photos). Each display sits on one model plate, every plate used once.
    place = mef.PLACEMENT["hub6_one"]
    assert sorted(place.values()) == sorted(mef.NAMES)
    assert place["BASE"] == "BASE"
    up = MS["BASE"][:3, :3] @ np.array([0, -1.0, 0])
    p2 = (MS[place["P2"]] @ np.array([0, 0, 0, 1.0]))[:3]
    base = (MS["BASE"] @ np.array([0, 0, 0, 1.0]))[:3]
    side = p2 - base
    side -= np.dot(side, -MS["BASE"][:3, :3] @ [0, 0, 1.0]) * (-MS["BASE"][:3, :3] @ [0, 0, 1.0])
    assert angle(up, side / np.linalg.norm(side)) < 1
    # going P1 -> P2 -> ... the plates' azimuths about the cup's axis turn the other way from the model's
    az = [math.atan2(*(MS[place[n]][:3, 3][[1, 0]])) for n in SIDES]
    steps = [((b - a + math.pi) % (2 * math.pi)) - math.pi for a, b in zip(az, az[1:] + az[:1])]
    model = [math.atan2(*(MS[n][:3, 3][[1, 0]])) for n in SIDES]
    msteps = [((b - a + math.pi) % (2 * math.pi)) - math.pi for a, b in zip(model, model[1:] + model[:1])]
    assert all(s * t < 0 for s, t in zip(steps, msteps))


def test_model_placement_is_the_identity():
    assert mef.PLACEMENT["model"] == {n: n for n in mef.NAMES}


def test_hub6_one_neighbours_still_meet_at_the_edge():
    place = mef.PLACEMENT["hub6_one"]
    ring = [("P1", "P2"), ("P2", "P3"), ("P3", "P4"), ("P4", "P5"), ("P5", "P1")]
    for a, b in ring:
        assert angle(normal(place[a]), normal(place[b])) == pytest.approx(2 * mef.EDGE_ANGLE, abs=0.1)
