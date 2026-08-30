# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Body-local occurrence and support contracts for FaceLevel."""

import pytest
from build123d import Align, Axis, Box, Compound, Pos, export_step, import_step

from b123d_recognisers import (
    FramedRecognitionResult,
    build_framed_recognition_result,
    build_recognition_result,
    step_level_records,
)
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers.result import _take_inventory

_MINIMUM_Z = (Align.CENTER, Align.CENTER, Align.MIN)


def _stepped(dx: float):
    base = Box(80, 50, 10, align=_MINIMUM_Z)
    upper = Pos(20, 0, 10) * Box(40, 50, 10, align=_MINIMUM_Z)
    return Pos(dx, 0, 0) * (base + upper)


def test_equal_levels_on_separate_bodies_retain_two_body_local_supports() -> None:
    left = _stepped(-70)
    right = _stepped(70)
    part = Compound(children=[left, right])

    levels = list(build_recognition_result(part).step_levels)

    assert levels == step_level_records(part)
    assert [(level.z, level.x_span, level.y_span) for level in levels] == [
        (10.0, (-110.0, -70.0), (-25.0, 25.0)),
        (10.0, (30.0, 70.0), (-25.0, 25.0)),
    ]


def test_aggregate_occurrences_retain_distinct_defining_solid_authority() -> None:
    part = Compound(children=[_stepped(-70), _stepped(70)])
    product = _take_inventory(part)
    candidates = product.physical.candidate_set(FamilyId.STEP_LEVELS).candidates

    assert len(candidates) == 2
    defining = [product.evidence.defining_of(candidate) for candidate in candidates]
    assert all(nodes for nodes in defining)
    solids = [product.context.graph.common_valid_solid(nodes) for nodes in defining]
    assert all(solid is not None for solid in solids)
    assert solids[0] != solids[1]


def test_child_order_does_not_change_body_local_level_order() -> None:
    left = _stepped(-70)
    right = _stepped(70)

    forward = step_level_records(Compound(children=[left, right]))
    reverse = step_level_records(Compound(children=[right, left]))

    assert reverse == forward


def test_framed_rigid_motion_preserves_body_local_level_occurrences() -> None:
    part = Compound(children=[_stepped(-70), _stepped(70)])
    baseline = build_framed_recognition_result(part)
    moved = build_framed_recognition_result(Pos(13, -7, 5) * part.rotate(Axis.X, 30))

    assert isinstance(baseline, FramedRecognitionResult)
    assert isinstance(moved, FramedRecognitionResult)
    assert len(moved.result.step_levels) == len(baseline.result.step_levels)
    for actual, expected in zip(
        moved.result.step_levels, baseline.result.step_levels, strict=True
    ):
        assert actual.z == pytest.approx(expected.z, abs=1e-9)
        assert actual.x_span == pytest.approx(expected.x_span, abs=1e-9)
        assert actual.y_span == pytest.approx(expected.y_span, abs=1e-9)


def test_connected_faces_at_one_level_still_coalesce_within_their_body() -> None:
    part = _stepped(0) + Pos(-20, 0, 10) * Box(40, 50, 10, align=_MINIMUM_Z)

    assert step_level_records(part) == []


def test_nested_compounds_retain_the_flat_body_occurrence_roster() -> None:
    left = _stepped(-70)
    right = _stepped(70)
    nested = Compound(children=[Compound(children=[left]), Compound(children=[right])])

    assert step_level_records(nested) == step_level_records(
        Compound(children=[left, right])
    )


def test_large_foreign_body_does_not_raise_a_small_bodys_area_threshold() -> None:
    small = _stepped(-70)
    large = Pos(500, 0, 0) * Box(1000, 1000, 20, align=_MINIMUM_Z)

    assert step_level_records(Compound(children=[small, large])) == step_level_records(small)


def test_step_round_trip_preserves_body_local_occurrences(tmp_path) -> None:
    part = Compound(children=[_stepped(-70), _stepped(70)])
    path = tmp_path / "separate-stepped-bodies.step"
    export_step(part, path)

    imported = import_step(path)

    assert step_level_records(imported) == step_level_records(part)
