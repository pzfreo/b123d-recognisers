# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""A passage, and the two things it is not.

Every test here is built around one block with one void through it, varied in exactly one way
at a time: capped at an end (a pocket), filled instead of hollow (a boss), or left open (a
passage). The pairing is the point -- a fixture that differed in several ways at once could
pass for reasons unrelated to the gate it names.
"""

from __future__ import annotations

from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Locations,
    Plane,
    Polygon,
    Pos,
    RegularPolygon,
    chamfer,
    extrude,
    fillet,
)

from b123d_recognisers import Passage, recognise_passages, recognise_slots
from b123d_recognisers._adjacency import FaceEdges


def _block() -> Box:
    return Box(60, 40, 20)


def _hexagonal_passage():
    """A six-walled void running the full depth in Z, open at both ends."""

    with BuildPart() as bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(9, 6)
        extrude(amount=40, both=True)
    return _block() - bore.part


def test_a_void_open_at_both_ends_is_a_passage():
    passages = recognise_passages(_hexagonal_passage())

    assert len(passages) == 1
    passage = passages[0]
    assert passage.axis == "z"
    assert passage.sides == 6
    assert passage.length == 20.0


def test_a_void_a_slot_already_reports_is_not_reported_twice():
    """The reconciliation, and it asks the slot recogniser rather than guessing.

    A through slot *is* a closed uncapped ring, so this family sees it too, and two pinned
    goldens caught the double count. An earlier fix declined every four-walled ring on the
    reasoning that a rectangular through void is simply what this package calls a slot.
    Measured, that was false -- of fifteen such rings across 120 MFCAD++ models, seven are in
    models where `recognise_slots` reports nothing at all -- so it dropped coverage rather than
    reconciling. What it claimed is now what is asked.
    """

    slotted = Box(130, 150, 16) - Box(30, 8, 60)
    assert recognise_slots(slotted), "the fixture must be a recognisable slot"
    assert recognise_passages(slotted) == []

    # A four-walled void no slot claims is still a passage: the side count was never the point.
    square = Box(60, 40, 20) - Box(10, 10, 60)
    assert recognise_slots(square) == []
    assert [p.sides for p in recognise_passages(square)] == [4]


def test_the_slot_inventory_can_be_injected():
    """`slots=` is the `cyls=` idiom: the census pays for one slot scan, not two."""

    slotted = Box(130, 150, 16) - Box(30, 8, 60)

    assert recognise_passages(slotted, slots=recognise_slots(slotted)) == []
    assert recognise_passages(slotted, slots=[]), "an empty inventory claims nothing"


def test_the_same_void_with_a_floor_is_a_pocket_and_not_a_passage():
    """The control, differing in one way: the void stops inside the block.

    A pocket's ring is capped by a face perpendicular to the run axis that fills the ring's
    cross-section. That the cap must *fill* it is the whole subtlety -- at a passage mouth the
    block's own end face is perpendicular and edge-adjacent too, and a test that only looked
    for a perpendicular neighbour rejected every passage there is.
    """

    with BuildPart() as bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(9, 6)
        extrude(amount=14)
    blind = _block() - Pos(0, 0, -4) * bore.part

    assert recognise_passages(blind) == []


def test_a_column_of_material_is_not_a_passage():
    """The same ring of walls, with the material inside it rather than outside.

    A hexagonal column joining two plates is bounded by an identical closed uncapped ring, and
    only the solid-classifier probe separates it from a void. The fixture matters: a boss
    standing *on* a plate is rejected by the cap test instead, so a test written around one
    passes with the probe deleted and proves nothing about it. This one does not -- without the
    probe it reports a passage.
    """

    with BuildPart() as column:
        with BuildSketch(Plane.XY):
            RegularPolygon(10, 6)
        extrude(amount=30)
    joined = _block() + Pos(0, 0, 26) * _block() + Pos(0, 0, -4) * column.part

    assert recognise_passages(joined) == []


def test_the_side_count_is_the_polygon_and_not_a_class():
    """MFCAD++ names triangular, rectangular and six-sided passages separately; the geometry
    does not, so one recogniser reports the count and the caller reads it."""

    with BuildPart() as tri:
        with BuildSketch(Plane.XZ):
            Polygon((-8, -6), (8, -6), (0, 8))
        extrude(amount=60, both=True)
    triangular = _block() - tri.part

    found = recognise_passages(triangular)
    assert len(found) == 1
    assert found[0].sides == 3
    assert found[0].axis == "y"


def test_two_passages_on_one_part_are_reported_separately_and_in_order():
    with BuildPart() as bores:
        with BuildSketch(Plane.XY):
            RegularPolygon(7, 6)
            with Locations((22, 0)):
                RegularPolygon(6, 6)
        extrude(amount=40, both=True)
    part = _block() - bores.part
    found = recognise_passages(part)

    assert len(found) == 2
    assert found == sorted(found, key=lambda p: (p.axis, p.at))
    assert all(isinstance(p, Passage) for p in found)
    assert recognise_passages(part) == found


def test_a_passage_is_a_passage_at_any_scale():
    """No gate mentions the part, so scaling the model changes nothing but the numbers."""

    small = recognise_passages(_hexagonal_passage())
    with BuildPart() as big_bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(180, 6)
        extrude(amount=800, both=True)
    big = recognise_passages(Box(1200, 800, 400) - big_bore.part)

    assert len(small) == len(big) == 1
    assert small[0].axis == big[0].axis and small[0].sides == big[0].sides
    assert round(big[0].length / 20, 3) == small[0].length


def test_a_part_with_no_void_has_no_passages():
    assert recognise_passages(_block()) == []


def test_a_shared_face_edge_memo_does_not_change_the_result():
    """``face_edges=`` is an optimisation, never a behaviour switch."""

    part = _hexagonal_passage()
    plain = recognise_passages(part)

    assert plain, "the fixture must reach the scan for this comparison to mean anything"
    assert plain == recognise_passages(part, face_edges=FaceEdges())


def test_a_blind_void_stays_a_pocket_when_its_floor_edge_is_blended():
    """A fillet or chamfer at the bottom of a pocket does not open it into a passage.

    The cap test originally looked only at planar axis-aligned neighbours, so breaking the
    floor edge removed the only candidate and an ordinary blind pocket came back as a through
    passage. `docs/capabilities.md` publishes capped voids as an exclusion; this is what makes
    that true for manufactured geometry rather than only for sharp corners.
    """

    with BuildPart() as bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(9, 6)
        extrude(amount=14)
    blind = _block() - Pos(0, 0, -4) * bore.part
    floor_edges = [e for e in blind.edges() if abs(e.center().Z - (-4)) < 1e-6]
    assert floor_edges, "the fixture must have a floor edge to blend"

    assert recognise_passages(blind) == []
    assert recognise_passages(fillet(floor_edges, 2.0)) == []
    assert recognise_passages(chamfer(floor_edges, 1.5)) == []
