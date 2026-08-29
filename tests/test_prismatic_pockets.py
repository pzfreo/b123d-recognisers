# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""A recess of any planar cross-section, found by walking its ring instead of pairing its walls.

The point of this family is a blind spot in the other one, and it is a blind spot in the *search*
rather than in a gate. `recognise_pockets` sorts walls into buckets by the axis their normal
aligns with and pairs walls within a bucket. A triangular recess has no two walls sharing an
axis, so no pair forms and no gate ever runs — measured over 600 MFCAD++ models, 94% of
triangular-pocket faces never reach a test at all.

So these tests are mostly about *reach*: geometry the pairing family cannot see, and geometry
this one cannot see either, because neither family is going away. The overlap where both see the
same recess is a reconciliation question and is tested as one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from attribution_audit import assert_ring_role, attributed_run
from build123d import (
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    export_step,
    extrude,
    import_step,
    mirror,
)

import b123d_recognisers as r
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._reconcile import prismatic_pockets_that_are_not_pockets
from b123d_recognisers.frames import (
    FramedRecognitionResult,
    build_framed_recognition_result,
)


def _prism(*corners, height=14):
    with BuildPart() as built:
        with BuildSketch(Plane.XY):
            Polygon(*corners)
        extrude(amount=height)
    return built.part


def _triangular():
    """A blind triangular recess: three walls, no two sharing a normal axis."""

    return Box(120, 80, 20) - Pos(0, 0, 2) * _prism((-12, -9), (12, -9), (0, 12))


def _rectangular():
    """The shape both families reach, so the overlap has something to be about."""

    return Box(120, 80, 20) - Pos(0, 0, 8) * Box(20, 12, 14)


def _hexagonal():
    return Box(120, 80, 20) - Pos(0, 0, 2) * _prism(
        (-12, -7), (-6, -12), (6, -12), (12, -7), (6, -2), (-6, -2)
    )


def _through():
    """The same triangular void cut clean through: a passage, not a pocket."""

    return Box(120, 80, 20) - Pos(0, 0, -20) * _prism(
        (-12, -9), (12, -9), (0, 12), height=60
    )


def _claimed(part):
    return attributed_run(
        part,
        FamilyId.PRISMATIC_POCKETS,
        r.recognise_prismatic_pockets,
    )


def test_a_triangular_recess_is_recognised_where_wall_pairing_cannot_see_it():
    """The reason this family exists, stated as the contrast rather than as a lone assertion.

    Both halves matter. `recognise_pockets` returning nothing is not this family succeeding
    where the other was merely stricter — the other never formed a candidate, because pairing
    walls that share a normal axis has nothing to pair when no two walls do.
    """

    part = _triangular()
    (pocket,) = r.recognise_prismatic_pockets(part)

    assert pocket.sides == 3
    assert pocket.depth == 8.0
    assert len(pocket.section) == 3
    assert r.recognise_pockets(part) == [], "the pairing family must be blind to this"


def test_both_cap_orientations_issue_complete_wall_evidence() -> None:
    low_ledger, (low,) = _claimed(_triangular())
    high_ledger, (high,) = _claimed(mirror(_triangular(), about=Plane.XY))

    assert (low.open_sign, high.open_sign) == (1, -1)
    for ledger, pocket in ((low_ledger, low), (high_ledger, high)):
        (candidate,) = ledger.candidate_set(FamilyId.PRISMATIC_POCKETS).candidates
        assert len(ledger.defining_of(candidate)) == pocket.sides


def test_multiple_pockets_keep_sorted_occurrence_identity() -> None:
    cutter = _prism((-8, -6), (8, -6), (0, 8))
    part = Box(120, 80, 20) - Pos(-25, 0, 2) * cutter - Pos(25, 0, 2) * cutter
    ledger, pockets = _claimed(part)

    assert len(pockets) == 2
    candidates = ledger.candidate_set(FamilyId.PRISMATIC_POCKETS).candidates
    assert all(
        candidate.record is pocket
        for candidate, pocket in zip(candidates, pockets, strict=True)
    )
    assert len({frozenset(ledger.defining_of(candidate)) for candidate in candidates}) == 2


def test_the_section_is_what_separates_a_triangle_from_a_hexagon():
    """`sides` alone would not, and neither would depth.

    A record that could not tell those apart would collapse two distinct machined shapes into
    one — the same reason `Passage` carries a section, and the reason this is not folded into
    `Pocket`, whose width-and-length cannot describe either.
    """

    triangle = _triangular()
    hexagon = _hexagonal()

    tri_ledger, (tri,) = _claimed(triangle)
    hex_ledger, (hexa,) = _claimed(hexagon)

    assert (tri.sides, hexa.sides) == (3, 6)
    assert tri.section != hexa.section
    assert len(tri.section) == 3 and len(hexa.section) == 6
    for ledger, pocket in ((tri_ledger, tri), (hex_ledger, hexa)):
        (candidate,) = ledger.candidate_set(FamilyId.PRISMATIC_POCKETS).candidates
        defining = ledger.defining_of(candidate)
        assert len(defining) == pocket.sides
        assert all(abs(ledger.graph.normal(node)[2]) < 1e-6 for node in defining)


@pytest.mark.parametrize(
    ("rotation_axis", "degrees", "expected_axis", "expected_open_sign"),
    [
        (Axis.X, 0, "z", 1),
        (Axis.Y, 180, "z", -1),
        (Axis.X, -90, "y", 1),
        (Axis.X, 90, "y", -1),
        (Axis.Y, 90, "x", 1),
        (Axis.Y, -90, "x", -1),
    ],
)
@pytest.mark.parametrize(("fixture", "sides"), [(_triangular, 3), (_hexagonal, 6)])
def test_polygonal_pockets_are_covariant_across_signed_principal_axes(
    fixture,
    sides: int,
    rotation_axis: Axis,
    degrees: float,
    expected_axis: str,
    expected_open_sign: int,
) -> None:
    part = Pos(17, -11, 9) * fixture().rotate(rotation_axis, degrees)

    (direct,) = r.recognise_prismatic_pockets(part)
    result = r.build_recognition_result(part)

    assert (direct.axis, direct.sides, direct.depth, direct.open_sign) == (
        expected_axis,
        sides,
        8.0,
        expected_open_sign,
    )
    assert result.prismatic_pockets == (direct,)


@pytest.mark.parametrize(
    ("rotation_axis", "degrees", "expected_axis", "expected_open_sign"),
    [
        (Axis.X, 0, "z", 1),
        (Axis.Y, 180, "z", -1),
        (Axis.X, -90, "y", 1),
        (Axis.X, 90, "y", -1),
        (Axis.Y, 90, "x", 1),
        (Axis.Y, -90, "x", -1),
    ],
)
def test_rectangular_ring_covariance_preserves_aggregate_pocket_precedence(
    rotation_axis: Axis,
    degrees: float,
    expected_axis: str,
    expected_open_sign: int,
) -> None:
    part = Pos(17, -11, 9) * _rectangular().rotate(rotation_axis, degrees)

    (ring,) = r.recognise_prismatic_pockets(part)
    result = r.build_recognition_result(part)

    assert (ring.axis, ring.sides, ring.depth, ring.open_sign) == (
        expected_axis,
        4,
        9.0,
        expected_open_sign,
    )
    assert result.prismatic_pockets == ()
    assert len(result.pockets) == 1


@pytest.mark.parametrize(("fixture", "sides"), [(_triangular, 3), (_hexagonal, 6)])
def test_principal_y_polygonal_pocket_survives_step_round_trip(
    fixture,
    sides: int,
    tmp_path: Path,
) -> None:
    part = Pos(17, -11, 9) * fixture().rotate(Axis.X, -90)
    path = tmp_path / f"principal-y-{sides}-sided-pocket.step"

    assert export_step(part, path)
    imported = import_step(path)

    (pocket,) = r.recognise_prismatic_pockets(imported)
    assert (pocket.axis, pocket.sides, pocket.depth, pocket.open_sign) == (
        "y",
        sides,
        8.0,
        1,
    )


def test_principal_y_rectangular_ring_round_trip_keeps_pocket_precedence(
    tmp_path: Path,
) -> None:
    part = Pos(17, -11, 9) * _rectangular().rotate(Axis.X, -90)
    path = tmp_path / "principal-y-rectangular-pocket.step"

    assert export_step(part, path)
    imported = import_step(path)
    result = r.build_recognition_result(imported)

    (ring,) = r.recognise_prismatic_pockets(imported)
    assert (ring.axis, ring.sides, ring.depth, ring.open_sign) == ("y", 4, 9.0, 1)
    assert result.prismatic_pockets == ()
    assert len(result.pockets) == 1


@pytest.mark.parametrize(
    ("fixture", "sides", "rectangular"),
    [(_triangular, 3, False), (_hexagonal, 6, False), (_rectangular, 4, True)],
)
def test_principal_ring_contract_survives_arbitrary_rigid_presentation_in_framed_aggregate(
    fixture,
    sides: int,
    rectangular: bool,
) -> None:
    presented = Pos(-31, 17, 23) * fixture().rotate(
        Axis((0, 0, 0), (1, 1, 0)), 37
    )

    framed = build_framed_recognition_result(presented)

    assert isinstance(framed, FramedRecognitionResult)
    if rectangular:
        assert framed.result.prismatic_pockets == ()
        assert len(framed.result.pockets) == 1
    else:
        (pocket,) = framed.result.prismatic_pockets
        assert (pocket.sides, pocket.depth) == (sides, 8.0)


def test_a_void_open_at_both_ends_is_a_passage_and_not_reported_here():
    """The cap count is the whole discriminator, so it is tested at both ends of its range."""

    part = _through()
    from attribution_audit import unattributed_run

    unattributed_run(part, FamilyId.PRISMATIC_POCKETS, r.recognise_prismatic_pockets)
    assert r.recognise_passages(part), "the same void must still be a passage"


def test_the_pocket_claims_its_walls_and_not_the_floor_that_makes_it_blind():
    """The floor is consulted, not consumed — the line every recess family here draws.

    `depth` is the walls' own span along the run axis, not a measurement taken off the floor, so
    the floor is what makes the recess blind rather than what it is measured by. Claiming it
    would have every pocket contest whatever else owns that face.
    """

    ledger, found = _claimed(_triangular())
    (pocket,) = found
    (claim,) = ledger.claims

    assert len(claim.defining) == pocket.sides == 3
    for node in claim.defining:
        normal = ledger.graph.normal(node)
        assert normal is not None
        assert abs(normal[2]) < 0.01, "a claimed face is a wall, not the floor"


def test_a_rectangular_recess_is_reported_by_both_families_and_reconciled_to_one():
    """The overlap, and the direction it resolves.

    Both records are true of the geometry. The `Pocket` wins because `width` and `length` on
    named axes are the numbers a drawing calls out, where a four-corner section says the same
    thing less directly — and for every shape `Pocket` cannot express, this rule does not fire
    and the prismatic record is the only one there is.
    """

    part = _rectangular()
    rect_ledger, rect_records = _claimed(part)
    assert len(rect_records) == 1
    (rect_candidate,) = rect_ledger.candidate_set(
        FamilyId.PRISMATIC_POCKETS
    ).candidates
    assert_ring_role(rect_ledger, rect_candidate, rect_records[0])

    ledger = ClaimLedger(FaceGraph(part))
    pockets = r.recognise_pockets(part, ledger=ledger)
    prismatic = r.recognise_prismatic_pockets(part, ledger=ledger)

    assert len(pockets) == 1 and len(prismatic) == 1, "both families see this recess"
    (candidate,) = ledger.candidate_set(FamilyId.PRISMATIC_POCKETS).candidates
    assert candidate.record is prismatic[0]
    assert len(ledger.defining_of(candidate)) == prismatic[0].sides == 4
    assert_ring_role(ledger, candidate, prismatic[0])
    assert (
        prismatic_pockets_that_are_not_pockets(
            prismatic, pockets, ledger.snapshot_index()
        )
        == []
    )

    # And the rule is not simply "drop everything": a shape `Pocket` cannot express survives it.
    # One part, built once -- a second `_triangular()` is a different solid, and the ledger
    # would refuse its faces rather than quietly answering about the wrong one.
    triangle = _triangular()
    tri_ledger = ClaimLedger(FaceGraph(triangle))
    tri_pockets = r.recognise_pockets(triangle, ledger=tri_ledger)
    tri = r.recognise_prismatic_pockets(triangle, ledger=tri_ledger)
    assert (
        len(
            prismatic_pockets_that_are_not_pockets(
                tri, tri_pockets, tri_ledger.snapshot_index()
            )
        )
        == 1
    )


def test_an_obround_recess_is_the_other_family_s_to_find():
    """Neither family subsumes the other, and this is the half that runs the other way.

    An obround pocket's ends are cylindrical, so its walls form no closed *planar* ring and this
    family sees nothing. Measured over 250 MFCAD++ models: zero rings on the whole *Circular end
    pocket* class. That is why the pairing family stays rather than being replaced.
    """

    end = Cylinder(6, 14)
    stub = Box(8, 12, 14) + Pos(-4, 0, 0) * end + Pos(4, 0, 0) * end
    part = Box(120, 80, 20) - Pos(0, 0, 8) * stub

    assert r.recognise_prismatic_pockets(part) == []
    assert r.recognise_pockets(part), "the pairing family must still find it"


def test_a_ledger_built_from_another_part_is_refused_rather_than_left_empty():
    """A graph from a different part resolves nothing, and empty reads as "claims nothing"."""

    part, twin = _triangular(), _triangular()
    assert r.recognise_prismatic_pockets(twin) == r.recognise_prismatic_pockets(part)

    foreign = ClaimLedger(FaceGraph(twin))
    try:
        r.recognise_prismatic_pockets(part, ledger=foreign)
    except ValueError as refusal:
        assert "built from a different part" in str(refusal)
    else:
        raise AssertionError("recognise_prismatic_pockets accepted another part's graph")
