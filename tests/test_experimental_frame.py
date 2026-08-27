# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Contract tests for the opt-in part-relative recognition frame spike."""

from __future__ import annotations

from pathlib import Path

import pytest
from build123d import Axis, Box, Cylinder, Pos, Sphere, Vector

from b123d_recognisers._experimental_frame import (
    FramedRecognitionResult,
    FrameGauge,
    FrameRefusalReason,
    PartFrame,
    RefusedPartFrame,
    build_framed_recognition_result,
    infer_part_frame,
)
from b123d_recognisers.result import build_recognition_result
from tests.golden._common import load_fixture


def test_frame_point_transforms_are_inverse() -> None:
    frame = PartFrame(
        (10.0, 20.0, 30.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
        FrameGauge.FULL,
    )

    assert frame.to_local((14.0, 25.0, 36.0)) == (5.0, 6.0, 4.0)
    assert frame.to_world((5.0, 6.0, 4.0)) == (14.0, 25.0, 36.0)


def test_frame_origin_and_axes_follow_a_rigid_motion() -> None:
    source = Box(10, 20, 30)
    source_frame = infer_part_frame(source)
    assert isinstance(source_frame, PartFrame)
    part = Pos(13, -7, 5) * source.rotate(Axis.X, 30)
    frame = infer_part_frame(part)

    assert isinstance(frame, PartFrame)
    assert frame.gauge is FrameGauge.FULL
    expected = Vector(*source_frame.origin).rotate(Axis.X, 30) + Vector(13, -7, 5)
    assert frame.origin == pytest.approx(tuple(expected), abs=1e-9)


def test_surface_of_revolution_refuses_its_unobservable_roll_gauge() -> None:
    frame = infer_part_frame(Cylinder(10, 30).rotate(Axis.X, 37))

    assert frame == RefusedPartFrame(FrameRefusalReason.AMBIGUOUS_DIRECTION)


def test_frame_inference_refuses_material_without_an_analytic_direction() -> None:
    refusal = infer_part_frame(Sphere(10))

    assert refusal == RefusedPartFrame(FrameRefusalReason.NO_ANALYTIC_DIRECTION)


def test_framed_recognition_is_opt_in_and_does_not_mutate_legacy_behavior() -> None:
    fixture = load_fixture(Path("tests/golden/straight_and_obround_slots/fixture.py"))
    part = fixture.build_fixture()
    legacy_before = build_recognition_result(part)

    framed = build_framed_recognition_result(Pos(13, -7, 5) * part.rotate(Axis.X, 30))

    assert isinstance(framed, FramedRecognitionResult)
    assert len(framed.result.slots) == len(legacy_before.slots) == 5
    assert framed.result.section_passages == ()
    assert build_recognition_result(part) == legacy_before
