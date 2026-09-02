# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""One concave circular Blend path at a blind cylindrical floor."""

from build123d import Box, Cylinder, GeomType, Pos, fillet

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_blends.py")


def build_fixture():
    pocket = Box(60, 60, 20) - Pos(0, 0, 8) * Cylinder(5, 12)
    bottom = min(pocket.edges().filter_by(GeomType.CIRCLE), key=lambda edge: edge.center().Z)
    return fillet(bottom, 1.0)
