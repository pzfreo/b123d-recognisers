# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Several complete circular Blend paths on one stepped turned body."""

from build123d import Cylinder, GeomType, Pos, fillet

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_blends.py")


def build_fixture():
    shaft = Pos(0, 0, 20) * Cylinder(15, 40) + Pos(0, 0, 55) * Cylinder(8, 30)
    circular_edges = [edge for edge in shaft.edges() if edge.geom_type == GeomType.CIRCLE]
    return fillet(circular_edges, 0.2)
