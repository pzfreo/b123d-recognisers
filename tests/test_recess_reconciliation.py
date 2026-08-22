# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""A complete recess boundary beats fragments assembled from selected wall pairs."""

from __future__ import annotations

from build123d import Box, BuildPart, BuildSketch, Cylinder, Plane, Polygon, Pos, Rot, extrude

import b123d_recognisers as r


def _u_void(*, blind: bool):
    """An eight-wall concave section with several opposed, axis-aligned wall pairs."""

    with BuildPart() as tool:
        with BuildSketch(Plane.XY):
            Polygon(
                (-15, -15),
                (15, -15),
                (15, 15),
                (9, 15),
                (9, -9),
                (-9, -9),
                (-9, 15),
                (-15, 15),
            )
        extrude(amount=14 if blind else 40, both=not blind)
    return Box(60, 60, 20) - (Pos(0, 0, -4) * tool.part if blind else tool.part)


def test_a_non_rectangular_passage_beats_slots_assembled_from_its_wall_pairs():
    """The two rectangular arms are still one eight-wall passage in the final inventory."""

    part = _u_void(blind=False)
    slots = r.recognise_slots(part)
    assert [(slot.width, slot.length, slot.w_center) for slot in slots] == [
        (6.0, 24.0, -12.0),
        (6.0, 24.0, 12.0),
    ]
    assert [passage.sides for passage in r.recognise_passages(part)] == [8]

    result = r.build_recognition_result(part)
    assert result.slots == ()
    assert [passage.sides for passage in result.passages] == [8]


def test_a_non_rectangular_prismatic_pocket_beats_paired_wall_fragments():
    """The floor and complete ring describe one U pocket; three rectangles do not."""

    part = _u_void(blind=True)
    assert len(r.recognise_pockets(part)) == 3, "the pair recogniser proposes fragments"
    assert [pocket.sides for pocket in r.recognise_prismatic_pockets(part)] == [8]

    result = r.build_recognition_result(part)
    assert result.pockets == ()
    assert [pocket.sides for pocket in result.prismatic_pockets] == [8]


def test_coaxial_posts_at_slot_ends_do_not_defeat_the_planar_boundary():
    """Convex added material interrupts an end; it does not make the slot walls unrelated."""

    plain = Box(60, 30, 10) - Box(30, 8, 20)
    for posts in (
        Pos(15, 0, 0) * Cylinder(4, 10),
        Pos(15, 0, 0) * Cylinder(4, 10) + Pos(-15, 0, 0) * Cylinder(4, 10),
    ):
        part = plain + posts
        (slot,) = r.recognise_slots(part)

        assert (slot.width_axis, slot.long_axis) == ("y", "x")
        assert (slot.width, slot.length) == (8.0, 30.0)
        assert (slot.w_center, slot.lo, slot.hi) == (0.0, -15.0, 15.0)
        assert (slot.d_lo, slot.d_hi) == (-5.0, 5.0)
        assert r.build_recognition_result(part).slots == (slot,)


def _parallel_recesses(*, blind: bool = False):
    """Two real recesses separated by a solid rib, the counterexample from issue #142."""

    stock = Box(60, 30, 10)
    cutter = Pos(0, 0, 3) * Box(30, 6, 6) if blind else Box(30, 6, 20)
    return stock - Pos(0, 8, 0) * cutter - Pos(0, -8, 0) * cutter


def test_parallel_slots_do_not_manufacture_a_third_slot_across_the_solid_rib():
    """Arc parity at the stock faces cannot prove that the space between walls is void."""

    part = _parallel_recesses()

    slots = r.recognise_slots(part)
    assert [(slot.width, slot.w_center) for slot in slots] == [(6.0, -8.0), (6.0, 8.0)]
    assert r.build_recognition_result(part).slots == tuple(slots)


def test_parallel_pockets_do_not_manufacture_a_third_pocket_across_intact_material():
    """The blind counterpart must not report one removal spanning both real pockets."""

    part = _parallel_recesses(blind=True)

    pockets = r.recognise_pockets(part)
    assert [(pocket.width, pocket.w_center) for pocket in pockets] == [(6.0, -8.0), (6.0, 8.0)]
    assert r.build_recognition_result(part).pockets == tuple(pockets)


def test_a_narrow_connector_does_not_turn_two_slots_into_one_wide_rectangular_slot():
    """Void connectedness alone cannot distinguish an H section from one rectangular cut."""

    part = _parallel_recesses() - Box(1, 10, 20)

    slots = r.recognise_slots(part)
    assert [(slot.width, slot.w_center) for slot in slots] == [
        (1.0, 0.0),  # the connector is itself a real narrow rectangular cut
        (6.0, -8.0),
        (6.0, 8.0),
    ]
    assert all(slot.width != 22.0 for slot in slots)


def test_an_end_connector_does_not_turn_a_u_section_into_one_wide_slot():
    """One shared concave end joins the arms, but does not complete their outer rectangle."""

    part = _parallel_recesses() - Pos(14, 0, 0) * Box(2, 10, 20)

    slots = r.recognise_slots(part)
    assert [(slot.width, slot.w_center, slot.length) for slot in slots] == [
        (2.0, 14.0, 10.0),
        (6.0, -8.0, 28.0),
        (6.0, 8.0, 28.0),
    ]
    assert all(slot.width != 22.0 for slot in slots)


def test_a_blind_u_does_not_turn_one_end_and_a_floor_into_a_wide_pocket():
    """A floor and one common end do not clear the solid rib at the opposite end."""

    part = _parallel_recesses(blind=True) - Pos(14, 0, 3) * Box(2, 10, 6)

    pockets = r.recognise_pockets(part)
    assert all(pocket.width != 22.0 for pocket in pockets)


def test_two_end_connectors_leave_a_separate_body_not_material_in_the_slot_body():
    """Compound bodies remain independent even when one spatially occupies another's void."""

    part = (
        _parallel_recesses()
        - Pos(-14, 0, 0) * Box(2, 10, 20)
        - Pos(14, 0, 0) * Box(2, 10, 20)
    )

    assert len(part.solids()) == 2
    (slot,) = r.recognise_slots(part)
    assert (slot.width, slot.length) == (22.0, 30.0)
    assert slot.body_key is not None


def test_even_a_thin_continuous_rib_keeps_two_slots_distinct():
    """Candidate existence is topological; it has no material-volume allowance."""

    stock = Box(60, 30, 10)
    for rib in (0.01, 0.05, 0.1):
        centre = 3 + rib / 2
        part = stock - Pos(0, centre, 0) * Box(30, 6, 20) - Pos(0, -centre, 0) * Box(30, 6, 20)

        slots = r.recognise_slots(part)
        assert [slot.width for slot in slots] == [6.0, 6.0]
        assert all(slot.width != round(12 + rib, 2) for slot in slots)


def test_parallel_channels_do_not_manufacture_one_channel_across_the_rib():
    """The same wall-pair admission rule applies to an open, floored recess."""

    stock = Box(60, 30, 10)
    cutter = Pos(0, 0, 3) * Box(80, 6, 6)
    part = stock - Pos(0, 8, 0) * cutter - Pos(0, -8, 0) * cutter

    channels = r.recognise_channels(part)
    assert [(channel.width, channel.w_center) for channel in channels] == [
        (6.0, -8.0),
        (6.0, 8.0),
    ]


def test_connected_non_rectangular_channel_systems_do_not_become_one_wide_channel():
    """Neither a central H connector nor a one-ended U is a simple full-span channel."""

    stock = Box(60, 30, 10)
    cutter = Pos(0, 0, 3) * Box(80, 6, 6)
    parallel = stock - Pos(0, 8, 0) * cutter - Pos(0, -8, 0) * cutter
    parts = (
        parallel - Pos(0, 0, 3) * Box(1, 10, 6),
        parallel - Pos(29, 0, 3) * Box(2, 10, 6),
    )

    for part in parts:
        assert r.recognise_channels(part) == []
        assert r.build_recognition_result(part).channels == ()


def test_a_near_boundary_membrane_is_not_lost_to_the_boolean_inset():
    """Material thicker than the documented coordinate floor still blocks admission."""

    membrane = 1e-5
    connector = Pos(membrane / 2, 0, 0) * Box(30 - membrane, 10, 20)
    part = _parallel_recesses() - connector

    assert len(part.solids()) == 1
    assert all(slot.width != 22.0 for slot in r.recognise_slots(part))


def test_a_slot_record_does_not_hide_an_interior_material_bridge():
    """A simple rectangular record cannot represent connected added material in its prism."""

    plain = Box(60, 30, 10) - Box(30, 8, 20)
    part = plain + Pos(0, -2, 0) * Box(4, 4, 10)

    assert len(part.solids()) == 1
    slots = r.recognise_slots(part)
    assert [(slot.width, slot.length, slot.lo, slot.hi) for slot in slots] == [
        (8.0, 13.0, -15.0, -2.0),
        (8.0, 13.0, 2.0, 15.0),
    ]


def test_concave_boundary_evidence_is_axis_and_scale_independent():
    """The rejection is topological, not a dimension or preferred-axis threshold."""

    for blind, recognise in ((False, r.recognise_slots), (True, r.recognise_pockets)):
        for scale in (0.05, 100.0):
            part = _parallel_recesses(blind=blind).scale(scale)
            rotated = Rot(0, 0, 90) * part

            for candidate in (part, rotated):
                records = recognise(candidate)
                assert sorted(round(record.width / scale, 6) for record in records) == [6.0, 6.0]
                assert sorted(round(record.w_center / scale, 6) for record in records) == [
                    -8.0,
                    8.0,
                ]
