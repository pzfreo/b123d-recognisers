# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Equal toroidal Blend paths retained as two body-local occurrences."""

from build123d import Box, Compound, Cylinder, GeomType, Pos, fillet

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_blends.py")


def _rounded_blind_bore():
    pocket = Box(60, 60, 20) - Pos(0, 0, 8) * Cylinder(5, 12)
    bottom = min(pocket.edges().filter_by(GeomType.CIRCLE), key=lambda edge: edge.center().Z)
    return fillet(bottom, 1.0)


def build_fixture():
    return Compound(
        children=[
            Pos(-70, 0, 0) * _rounded_blind_bore(),
            Pos(70, 0, 0) * _rounded_blind_bore(),
        ]
    )
