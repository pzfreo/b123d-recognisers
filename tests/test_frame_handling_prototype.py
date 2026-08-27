# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Decision tests for the part-relative frame-handling prototype."""

from __future__ import annotations

import pytest
from build123d import Axis, Box, Sphere

from tools.frame_handling_prototype import evaluate_goldens, infer_frame


def test_frame_inference_tracks_a_rigidly_rotated_prism() -> None:
    frame = infer_frame(Box(10, 20, 30).rotate(Axis.X, 30))

    assert frame.support_areas[0] >= frame.support_areas[1] > 0.0
    assert all(
        abs(sum(left * right for left, right in zip(frame.axes[i], frame.axes[j], strict=True)))
        < 1e-12
        for i, j in ((0, 1), (0, 2), (1, 2))
    )


def test_frame_inference_refuses_geometry_with_no_direction_evidence() -> None:
    with pytest.raises(ValueError, match="two independent analytic direction classes"):
        infer_frame(Sphere(10))


def test_normalization_makes_the_complete_golden_inventory_rotation_invariant() -> None:
    report = evaluate_goldens()

    assert report["refused"] == {}
    assert report["totals"] == {
        name: {
            "baseline_records": 75,
            "same_family": 75,
            "reclassified": 0,
            "absent": 0,
            "introduced": 0,
        }
        for name in ("Z30", "X30", "X90")
    }
