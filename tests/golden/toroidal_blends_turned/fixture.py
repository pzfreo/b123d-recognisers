# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Several complete circular Blend paths on one oblique stepped shaft."""

from build123d import Axis, Cylinder, GeomType, Pos, fillet

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_blends.py")


def build_fixture():
    shaft = Pos(0, 0, 20) * Cylinder(15, 40) + Pos(0, 0, 55) * Cylinder(8, 30)
    circular_edges = [edge for edge in shaft.edges() if edge.geom_type == GeomType.CIRCLE]
    # Oblique placement keeps the golden focused on free-axis circular Blend paths rather than
    # also pinning platform-sensitive principal-axis TurnedProfile bounding-box metadata.
    return fillet(circular_edges, 0.2).rotate(Axis.Y, 23)
