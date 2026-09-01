# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Authored controls for the section-passage gap audits."""

from __future__ import annotations

import pytest
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Compound,
    Plane,
    Pos,
    RegularPolygon,
    Rot,
    extrude,
)

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._section_passages import section_ring_proposals
from tools.audit_mfcadpp_section_passage_gaps import (
    _probe_component,
    _selection_hash,
    _source_selection_hash,
)


def _polygonal_tool(sides: int, *, depth: float = 60.0):
    with BuildPart() as tool:
        with BuildSketch(Plane.XY):
            RegularPolygon(7, sides)
        extrude(amount=depth, both=depth == 60.0)
    return tool.part


def _polygonal_passage(sides: int = 6):
    return Box(60, 40, 20) - _polygonal_tool(sides)


def _vertical_inner_walls(graph: FaceGraph):
    return frozenset(
        node
        for node in graph.nodes
        if graph.is_planar(node)
        and (normal := graph.normal(node)) is not None
        and abs(normal[2]) < 1e-8
        and graph.face(node).area < 200.0
    )


@pytest.mark.parametrize("sides", (3, 4, 6))
def test_intact_polygonal_passage_reaches_exact_production_proposal(sides: int) -> None:
    part = _polygonal_passage(sides)
    graph = FaceGraph(part)
    (proposal,) = section_ring_proposals(part, graph)
    component = frozenset(proposal.nodes)

    probe = _probe_component(graph, component)

    assert probe.first_failed_gate == "recognisable"
    assert probe.planar_walls == probe.collinear_pairs == probe.interval_pairs == sides
    assert probe.cycle_faces == sides
    assert component == frozenset(proposal.nodes)


@pytest.mark.parametrize("sides", (3, 4, 6))
def test_capped_polygonal_void_reaches_only_material_or_capped_gate(sides: int) -> None:
    part = Box(60, 40, 20) - _polygonal_tool(sides, depth=10.0)
    graph = FaceGraph(part)
    component = _vertical_inner_walls(graph)

    probe = _probe_component(graph, component)

    assert len(component) == sides
    assert probe.first_failed_gate == "material_or_capped"
    assert section_ring_proposals(part, graph) == ()


def test_probe_is_axis_covariant() -> None:
    first_part = _polygonal_passage()
    second_part = Rot(90, 0, 0) * first_part
    first_graph = FaceGraph(first_part)
    second_graph = FaceGraph(second_part)
    (first,) = section_ring_proposals(first_part, first_graph)
    (second,) = section_ring_proposals(second_part, second_graph)

    first_probe = _probe_component(first_graph, frozenset(first.nodes))
    second_probe = _probe_component(second_graph, frozenset(second.nodes))

    assert first_probe.first_failed_gate == second_probe.first_failed_gate == "recognisable"
    assert first_probe.run != second_probe.run
    assert first_probe.planar_walls == second_probe.planar_walls == 6


def test_equal_rectangular_passages_on_separate_bodies_remain_distinct() -> None:
    first = _polygonal_passage(4)
    second = Pos(100, 0, 0) * first
    compound = Compound(children=[first, second])
    graph = FaceGraph(compound)
    proposals = section_ring_proposals(compound, graph)

    assert len(proposals) == 2
    components = [frozenset(proposal.nodes) for proposal in proposals]
    assert all(
        _probe_component(graph, component).first_failed_gate == "recognisable"
        for component in components
    )
    owners = [graph.common_valid_solid(component) for component in components]
    assert None not in owners
    assert owners[0] != owners[1]


def test_selection_hashes_pin_order_and_source_content() -> None:
    assert _selection_hash(["100", "200"]) == _selection_hash(["100", "200"])
    assert _selection_hash(["100", "200"]) != _selection_hash(["200", "100"])
    assert _source_selection_hash([("100", "aaa")]) != _source_selection_hash([("100", "changed")])
