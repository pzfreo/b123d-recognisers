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

from attribution_audit import attributed_run
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    extrude,
    mirror,
)

import b123d_recognisers as r
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._reconcile import prismatic_pockets_that_are_not_pockets


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


def test_the_section_is_what_separates_a_triangle_from_a_hexagon():
    """`sides` alone would not, and neither would depth.

    A record that could not tell those apart would collapse two distinct machined shapes into
    one — the same reason `Passage` carries a section, and the reason this is not folded into
    `Pocket`, whose width-and-length cannot describe either.
    """

    triangle = _triangular()
    hexagon = Box(120, 80, 20) - Pos(0, 0, 2) * _prism(
        (-12, -7), (-6, -12), (6, -12), (12, -7), (6, -2), (-6, -2)
    )

    (tri,) = r.recognise_prismatic_pockets(triangle)
    (hexa,) = r.recognise_prismatic_pockets(hexagon)

    assert (tri.sides, hexa.sides) == (3, 6)
    assert tri.section != hexa.section
    assert len(tri.section) == 3 and len(hexa.section) == 6


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
    ledger = ClaimLedger(FaceGraph(part))
    pockets = r.recognise_pockets(part, ledger=ledger)
    prismatic = r.recognise_prismatic_pockets(part, ledger=ledger)

    assert len(pockets) == 1 and len(prismatic) == 1, "both families see this recess"
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
