# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import math
from dataclasses import replace

import pytest
from build123d import Align, Box, Cylinder, Pos, Rot, export_step, import_step

from b123d_recognisers import (
    build_recognition_result,
    recognise_oriented_slot_patterns,
    recognise_oriented_slots,
    recognise_section_passages,
)
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._dispositions import Outcome, ReasonCode
from b123d_recognisers.result import _take_inventory


def _rectangular_through_slot(angle: float = 30.0):
    tool = Rot(0, 0, angle) * Box(
        30,
        8,
        20,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    )
    return Box(100, 70, 10) - tool


@pytest.mark.parametrize("angle", [17.0, 30.0, 45.0])
def test_free_axis_rectangle_is_an_oriented_slot(angle: float) -> None:
    part = _rectangular_through_slot(angle)

    (record,) = recognise_oriented_slots(part)

    assert record.width == pytest.approx(8.0, abs=0.002)
    assert record.length == pytest.approx(30.0, abs=0.002)
    assert record.depth == pytest.approx(10.0)
    assert record.center == (0.0, 0.0, 0.0)
    # Public section vertices are serialized to 0.001 model units before this projection.
    assert (
        abs(
            sum(
                a * b
                for a, b in zip(
                    record.width_direction, record.long_direction, strict=True
                )
            )
        )
        < 2e-5
    )
    assert record.source == recognise_section_passages(part)[0]


def test_aggregate_reconciles_the_generic_source_passage() -> None:
    part = _rectangular_through_slot()
    product = _take_inventory(part)

    assert product.result.oriented_slots == tuple(recognise_oriented_slots(part))
    assert product.result.section_passages == ()
    (decision,) = tuple(
        item
        for item in product.reconciliation.for_family(FamilyId.PASSAGES)
        if item.reason is ReasonCode.PASSAGE_SUPERSEDED_BY_ORIENTED_SLOT
    )
    assert decision.outcome is Outcome.REJECTED
    assert decision.related[0].family is FamilyId.ORIENTED_SLOTS
    assert product.evidence.defining_of(decision.candidate) == product.evidence.defining_of(
        decision.related[0]
    )


def test_principal_rectangle_stays_in_legacy_slot_family() -> None:
    result = build_recognition_result(_rectangular_through_slot(0.0), rotational=False)

    assert len(result.slots) == 1
    assert result.oriented_slots == ()
    assert result.section_passages == ()


def test_square_and_curved_passages_are_not_oriented_slots() -> None:
    square = Box(100, 70, 10) - Rot(0, 0, 30) * Box(
        12,
        12,
        20,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    )
    round_hole = Box(100, 70, 10) - Cylinder(5, 20)

    assert recognise_oriented_slots(square) == []
    assert recognise_oriented_slots(round_hole) == []


def test_record_directions_follow_a_rotated_whole_part() -> None:
    base = recognise_oriented_slots(_rectangular_through_slot(30.0))[0]
    rotated = recognise_oriented_slots(Rot(90, 0, 0) * _rectangular_through_slot(30.0))[0]

    assert rotated.width == base.width
    assert rotated.length == base.length
    assert rotated.depth == base.depth
    assert math.isclose(abs(rotated.width_direction[0]), abs(base.width_direction[0]), abs_tol=2e-6)
    assert math.isclose(abs(rotated.width_direction[2]), abs(base.width_direction[1]), abs_tol=2e-6)
    assert abs(rotated.width_direction[1]) < 2e-6


def test_step_round_trip_preserves_oriented_slot(tmp_path) -> None:
    source = _rectangular_through_slot(37.0)
    path = tmp_path / "oriented-slot.step"
    export_step(source, path)

    before = recognise_oriented_slots(source)
    after = recognise_oriented_slots(import_step(path))

    assert after == before


@pytest.mark.parametrize("scale", [0.1, 1.0, 10.0])
def test_scale_preserves_one_oriented_slot(scale: float) -> None:
    tool = Rot(0, 0, 23) * Box(
        30 * scale,
        8 * scale,
        20 * scale,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    )
    part = Box(100 * scale, 70 * scale, 10 * scale) - tool

    (record,) = recognise_oriented_slots(part)

    assert record.width == pytest.approx(8 * scale, abs=0.002)
    assert record.length == pytest.approx(30 * scale, abs=0.002)


def test_translation_changes_only_public_location_values() -> None:
    base = recognise_oriented_slots(_rectangular_through_slot())[0]
    moved = recognise_oriented_slots(Pos(12, -7, 4) * _rectangular_through_slot())[0]

    assert moved.center == (12.0, -7.0, 4.0)
    assert moved.width == base.width
    assert moved.length == base.length
    assert moved.width_direction == base.width_direction
    assert moved.long_direction == base.long_direction


def test_blind_and_edge_open_rectangles_are_not_oriented_through_slots() -> None:
    blind = Box(100, 70, 10) - Pos(0, 0, 4) * Rot(0, 0, 30) * Box(
        30,
        8,
        6,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    )
    edge_open = Box(100, 70, 10) - Pos(45, 0, 0) * Rot(0, 0, 30) * Box(
        30,
        8,
        20,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    )

    assert recognise_oriented_slots(blind) == []
    assert recognise_oriented_slots(edge_open) == []


def test_patterns_require_matching_geometry_plane_orientation_and_body() -> None:
    source = recognise_oriented_slots(_rectangular_through_slot())[0]
    members = [replace(source, center=(float(x), 0.0, 0.0)) for x in (-20, 0, 20)]

    (pattern,) = recognise_oriented_slot_patterns(members)

    assert pattern.slots == tuple(members)
    assert pattern.pitch == pytest.approx(20.0)
    assert recognise_oriented_slot_patterns(
        [members[0], members[1], replace(members[2], width=9.0)]
    ) == []
    assert recognise_oriented_slot_patterns(
        [members[0], members[1], replace(members[2], body_key=None)]
    ) == []
