# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Authored controls for the class-4 section-passage gap audit."""

from __future__ import annotations

from build123d import Box, BuildPart, BuildSketch, Plane, RegularPolygon, Rot, extrude

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._section_passages import section_ring_proposals
from tools.audit_mfcadpp_section_passage_gaps import (
    _probe_component,
    _selection_hash,
    _source_selection_hash,
)


def _hexagonal_tool(*, depth: float = 60.0):
    with BuildPart() as tool:
        with BuildSketch(Plane.XY):
            RegularPolygon(7, 6)
        extrude(amount=depth, both=depth == 60.0)
    return tool.part


def _hexagonal_passage():
    return Box(60, 40, 20) - _hexagonal_tool()


def _vertical_inner_walls(graph: FaceGraph):
    return frozenset(
        node
        for node in graph.nodes
        if graph.is_planar(node)
        and (normal := graph.normal(node)) is not None
        and abs(normal[2]) < 1e-8
        and graph.face(node).area < 200.0
    )


def test_intact_hexagonal_passage_reaches_exact_production_proposal() -> None:
    part = _hexagonal_passage()
    graph = FaceGraph(part)
    (proposal,) = section_ring_proposals(part, graph)
    component = frozenset(proposal.nodes)

    probe = _probe_component(graph, component)

    assert probe.first_failed_gate == "recognisable"
    assert probe.planar_walls == probe.collinear_pairs == probe.interval_pairs == 6
    assert probe.cycle_faces == 6
    assert component == frozenset(proposal.nodes)


def test_capped_hexagonal_void_reaches_only_material_or_capped_gate() -> None:
    part = Box(60, 40, 20) - _hexagonal_tool(depth=10.0)
    graph = FaceGraph(part)
    component = _vertical_inner_walls(graph)

    probe = _probe_component(graph, component)

    assert len(component) == 6
    assert probe.first_failed_gate == "material_or_capped"
    assert section_ring_proposals(part, graph) == ()


def test_probe_is_axis_covariant() -> None:
    first_part = _hexagonal_passage()
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


def test_selection_hashes_pin_order_and_source_content() -> None:
    assert _selection_hash(["100", "200"]) == _selection_hash(["100", "200"])
    assert _selection_hash(["100", "200"]) != _selection_hash(["200", "100"])
    assert _source_selection_hash([("100", "aaa")]) != _source_selection_hash(
        [("100", "changed")]
    )
