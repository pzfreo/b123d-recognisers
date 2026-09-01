# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Authored controls for the class-15 PrismaticPocket gap audit."""

from __future__ import annotations

import pytest
from build123d import Box, BuildPart, BuildSketch, Plane, RegularPolygon, Rot, extrude

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._rings import rings
from tools.audit_mfcadpp_prismatic_pocket_gaps import (
    _probe_component,
    _selection_hash,
    _source_selection_hash,
)


def _hexagonal_tool(*, depth: float, both: bool = False, z: float = 0.0):
    with BuildPart() as tool:
        with BuildSketch(Plane.XY.offset(z)):
            RegularPolygon(7, 6)
        extrude(amount=depth, both=both)
    return tool.part


def _only_ring(part):
    graph = FaceGraph(part)
    (ring,) = rings(part, graph)
    component = frozenset((*ring.nodes, *ring.cap_nodes[0], *ring.cap_nodes[1]))
    return graph, component


def test_blind_hexagonal_pocket_reaches_recognisable_gate() -> None:
    part = Box(60, 40, 20) - _hexagonal_tool(depth=10)
    graph, component = _only_ring(part)

    probe = _probe_component(part, graph, component)

    assert probe.first_failed_gate == "recognisable"
    assert probe.span_members == 6
    assert sorted(probe.cap_counts or ()) == [0, 1]


@pytest.mark.parametrize(
    ("part", "caps"),
    [
        (Box(60, 40, 20) - _hexagonal_tool(depth=30, both=True), (0, 0)),
        (Box(60, 40, 20) - _hexagonal_tool(depth=10, z=-5), (1, 1)),
    ],
)
def test_through_and_enclosed_hexagonal_voids_fail_single_cap(part, caps) -> None:
    graph, component = _only_ring(part)

    probe = _probe_component(part, graph, component)

    assert probe.first_failed_gate == "not_single_cap"
    assert probe.cap_counts == caps


def test_probe_is_axis_covariant() -> None:
    first = Box(60, 40, 20) - _hexagonal_tool(depth=10)
    second = Rot(90, 0, 0) * first
    first_graph, first_component = _only_ring(first)
    second_graph, second_component = _only_ring(second)

    first_probe = _probe_component(first, first_graph, first_component)
    second_probe = _probe_component(second, second_graph, second_component)

    assert first_probe.first_failed_gate == second_probe.first_failed_gate == "recognisable"
    assert first_probe.axis != second_probe.axis
    assert first_probe.span_members == second_probe.span_members == 6


def test_selection_hashes_pin_order_and_source_content() -> None:
    assert _selection_hash(["100", "200"]) != _selection_hash(["200", "100"])
    assert _source_selection_hash([("100", "aaa")]) != _source_selection_hash(
        [("100", "changed")]
    )
