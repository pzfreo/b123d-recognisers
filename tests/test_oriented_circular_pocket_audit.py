from __future__ import annotations

import pytest
from build123d import Box, Compound, Cylinder, Pos, Rot

from b123d_recognisers._adjacency import FaceGraph
from tools.audit_mfcadpp_oriented_circular_pockets import _candidates


def _obround(*, straight: float = 12, width: float = 6, depth: float = 8):
    radius = width / 2
    return (
        Box(straight, width, depth)
        + Pos(-straight / 2, 0, 0) * Cylinder(radius, depth)
        + Pos(straight / 2, 0, 0) * Cylinder(radius, depth)
    )


def _blind_pocket(*, angle: float = 30, depth: float = 8):
    cutter = Rot(0, 0, angle) * _obround(depth=depth)
    return Box(60, 50, 12) - Pos(0, 0, 4) * cutter


def test_coordinate_free_proof_finds_an_oriented_closed_circular_pocket() -> None:
    (candidate,) = _candidates(FaceGraph(_blind_pocket()))

    assert candidate.oriented
    assert candidate.radius == 3
    assert candidate.run_interval == (0, 6)
    assert len(candidate.defining) == 4
    assert len(candidate.constituent) == 5


@pytest.mark.parametrize(
    "placement",
    [Rot(90, 0, 0), Rot(0, 90, 0), Rot(17, 31, 43) * Pos(11, -7, 5)],
)
def test_proof_is_covariant_under_rigid_presentation(placement) -> None:
    (candidate,) = _candidates(FaceGraph(placement * _blind_pocket()))

    assert candidate.oriented
    assert candidate.radius == 3
    assert len(candidate.constituent) == 5


def test_principal_pocket_is_measured_but_not_an_oriented_successor() -> None:
    (candidate,) = _candidates(FaceGraph(_blind_pocket(angle=0)))

    assert not candidate.oriented


def test_through_and_non_obround_cuts_do_not_satisfy_the_proof() -> None:
    through = Box(60, 50, 12) - Pos(0, 0, -1) * _obround(depth=14)
    round_blind = Box(60, 50, 12) - Pos(0, 0, 4) * Cylinder(3, 8)
    rectangular_blind = Box(60, 50, 12) - Pos(0, 0, 4) * Box(12, 6, 8)

    assert _candidates(FaceGraph(through)) == ()
    assert _candidates(FaceGraph(round_blind)) == ()
    assert _candidates(FaceGraph(rectangular_blind)) == ()


def test_interrupted_support_does_not_get_reconstructed() -> None:
    pocket = _blind_pocket()
    interruption = Pos(0, 3, 3) * Cylinder(1, 12)

    assert _candidates(FaceGraph(pocket - interruption)) == ()


def test_equal_pockets_on_separate_bodies_remain_separate() -> None:
    first = _blind_pocket()
    second = Pos(100, 0, 0) * _blind_pocket()

    candidates = _candidates(FaceGraph(Compound([first, second])))

    assert len(candidates) == 2
    assert all(candidate.oriented for candidate in candidates)
