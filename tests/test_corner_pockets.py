# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Exact AAG evidence for the edge-anchored rectangular Pocket subset."""

from __future__ import annotations

import pytest
from build123d import Axis, Box, Face, Pos, Rot, Shell, Solid, Vector, Wire, chamfer

from b123d_recognisers import recognise_pockets
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._claims import ClaimLedger


def _corner_notch():
    return Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8)


def _anchored(part):
    return [pocket for pocket in recognise_pockets(part) if pocket.edge_anchored]


def _split_wall(part) -> Solid:
    wall = next(
        face
        for face in part.faces()
        if abs(face.center().X - 15) < 1e-8 and abs(face.center().Z - 3) < 1e-8
    )
    low = sorted(tuple(vertex) for vertex in wall.vertices() if vertex.Z < 3)
    high = sorted(tuple(vertex) for vertex in wall.vertices() if vertex.Z > 3)
    middle = [(point[0], point[1], 3) for point in low]

    def oriented(*points):
        wire = Wire.make_polygon([Vector(*point) for point in points], close=True)
        face = Face(wire)
        if face.normal_at().dot(wall.normal_at()) < 0:
            face = Face(
                Wire.make_polygon(
                    [Vector(*point) for point in points[::-1]], close=True
                )
            )
        return face

    patches = (
        oriented(low[0], low[1], middle[1], middle[0]),
        oriented(middle[0], middle[1], high[1], high[0]),
    )
    solid = Solid(
        Shell([*(face for face in part.faces() if not face.is_same(wall)), *patches])
    )
    assert solid.is_valid
    return solid


def test_corner_pocket_is_in_plane_rotation_and_scale_invariant():
    baseline = _anchored(_corner_notch())
    assert len(baseline) == 1
    assert (baseline[0].width, baseline[0].length, baseline[0].depth) == (15.0, 15.0, 6.0)

    for rotation in (Rot(0, 0, 90), Rot(0, 0, 180), Rot(0, 0, 270)):
        (pocket,) = _anchored(rotation * _corner_notch())
        assert (pocket.width, pocket.length, pocket.depth) == (15.0, 15.0, 6.0)

    for factor in (0.001, 1000):
        (pocket,) = _anchored(_corner_notch().scale(factor))
        assert sorted((pocket.width, pocket.length, pocket.depth)) == pytest.approx(
            sorted((15 * factor, 15 * factor, 6 * factor)), abs=max(0.01, factor * 1e-6)
        )


def test_a_bounded_notch_may_span_more_than_ninety_percent_of_stock():
    """Topology and envelope context decide; part-relative feature fractions do not."""

    stock = Box(100, 100, 20)
    part = stock - Pos(4.5, 40, 5) * Box(91, 20, 10)

    (pocket,) = _anchored(part)
    assert (pocket.width, pocket.length, pocket.depth) == (20.0, 91.0, 10.0)


def test_a_coplanar_wall_split_preserves_the_record_and_claims_every_patch():
    part = _split_wall(_corner_notch())
    graph = FaceGraph(part)
    ledger = ClaimLedger(graph)

    records = recognise_pockets(part, ledger=ledger)
    anchored = [pocket for pocket in records if pocket.edge_anchored]

    assert anchored == _anchored(_corner_notch())
    claim = next(claim for claim in ledger.claims if claim.claimant is anchored[0])
    assert len(claim.defining) == 4


def test_an_inner_wire_or_open_boundary_notch_is_not_a_simple_corner_pocket():
    base = _corner_notch()
    # These cuts remove more material through a defining support. An empty-volume test alone
    # cannot reject extra void, so the actual sewn, hole-free rectangular boundary is essential.
    inner_wire = base - Pos(15, 12, 0) * Box(2, 2, 2)
    open_notch = base - Pos(15, 17, 1) * Box(2, 8, 2)

    assert _anchored(inner_wire) == []
    assert _anchored(open_notch) == []


def test_a_material_bridge_inside_the_nominal_cuboid_fails_closed():
    stock = Box(60, 40, 12)
    cutter = Pos(25, 15, 4) * Box(20, 20, 8)
    # Withhold a thin strip from the cutter so the resulting recess contains a same-solid bridge.
    cutter -= Pos(20, 15, 3) * Box(1, 20, 2)
    part = stock - cutter

    assert _anchored(part) == []


def test_three_unconnected_support_planes_cannot_be_joined_by_bounds():
    """Two adjacent recesses supply plausible stations but no complete concave trihedron."""

    stock = Box(60, 40, 12)
    first = Pos(25, 15, 4) * Box(20, 8, 8)
    second = Pos(25, 4, 4) * Box(8, 10, 8)
    part = stock - first - second

    assert _anchored(part) == []


def test_a_chamfered_stock_corner_is_not_promoted_to_a_rectangular_pocket():
    stock = Box(60, 40, 12)
    corner = max(
        stock.edges().filter_by(Axis.Z),
        key=lambda edge: edge.center().X + edge.center().Y,
    )
    stock = chamfer(corner, 2)
    part = stock - Pos(25, 15, 4) * Box(20, 20, 8)

    assert _anchored(part) == []
