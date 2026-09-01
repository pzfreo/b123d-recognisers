# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Synthetic round-bottom blind-slot golden fixture."""

from build123d import (
    Box,
    BuildLine,
    BuildSketch,
    Line,
    Pos,
    RadiusArc,
    Vector,
    extrude,
    make_face,
)

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_round_bottom_slots.py")


def build_fixture():
    with BuildLine() as boundary:
        Line((-5, 0), (5, 0))
        RadiusArc((5, 0), (2, -3), 3)
        Line((2, -3), (-2, -3))
        RadiusArc((-2, -3), (-5, 0), 3)
    with BuildSketch() as sketch:
        make_face(boundary.line)
    stock = Pos(0, -5, 0) * Box(30, 10, 40)
    return stock - extrude(sketch.sketch, amount=20, dir=Vector(0, 0, 1))
