# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Synthetic semicircular-bottom blind-slot golden fixture."""

from build123d import Align, Box, BuildSketch, Pos, Rectangle, Vector, extrude, fillet

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_semicircular_bottom_slots.py")


def build_fixture():
    with BuildSketch() as sketch:
        Rectangle(6, 7, align=(Align.CENTER, Align.MAX))
        bottom = [vertex for vertex in sketch.vertices() if abs(vertex.Y + 7) < 1e-8]
        fillet(bottom, radius=3)
    stock = Pos(0, -6, 0) * Box(30, 12, 40)
    return stock - extrude(sketch.sketch, amount=20, dir=Vector(0, 0, 1))
