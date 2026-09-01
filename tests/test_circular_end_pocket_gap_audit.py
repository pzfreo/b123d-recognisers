# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Authored controls for the circular-end-pocket gap audit."""

from __future__ import annotations

from build123d import Box, Compound, Cylinder, Pos, Rot

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._recess_core import _pocket_proposals_one
from b123d_recognisers._recess_faces import _cylinder_faces
from tools.audit_mfcadpp_circular_end_pocket_gaps import (
    _probe_component,
    _selection_hash,
    _source_selection_hash,
)


def _obround(length: float = 6, width: float = 10, depth: float = 8):
    end = Cylinder(width / 2, depth)
    return Box(length, width, depth) + Pos(-length / 2, 0, 0) * end + Pos(length / 2, 0, 0) * end


def _blind_pocket(*, angle: float = 0):
    tool = Rot(0, 0, angle) * _obround()
    return Box(60, 40, 12) - Pos(0, 0, 4) * tool


def _component(part, graph: FaceGraph):
    nodes = {cap[5] for cap in _cylinder_faces(part, graph) if cap[4]}
    for node in tuple(nodes):
        nodes.update(
            neighbour
            for neighbour in graph.neighbours(node)
            if graph.is_planar(neighbour) and graph.face(neighbour).area < 500
        )
    return frozenset(nodes)


def _proposal_groups(part, graph: FaceGraph):
    return tuple(
        proposal.planar
        | proposal.floors
        | frozenset(node for group in proposal.caps for node in group)
        for solid in (list(part.solids()) or [part])
        for proposal in _pocket_proposals_one(solid, graph=graph)
    )


def test_semicircular_blind_pocket_reaches_current_proposal() -> None:
    part = _blind_pocket()
    graph = FaceGraph(part)

    probe = _probe_component(part, graph, _component(part, graph), _proposal_groups(part, graph))

    assert probe.first_failed_gate == "current_proposal"
    assert probe.cylinder_faces == probe.individually_supported_ends == 2
    assert probe.principal_side_walls == 2
    assert sorted(probe.floor_counts or ()) == [0, 1]


def test_internally_oblique_pocket_is_not_called_a_ratio_failure() -> None:
    part = _blind_pocket(angle=10)
    graph = FaceGraph(part)

    probe = _probe_component(part, graph, _component(part, graph), _proposal_groups(part, graph))

    assert probe.first_failed_gate == "non_principal_side_walls"
    assert probe.cylinder_faces == 2
    assert probe.principal_side_walls == 0


def test_fragmented_component_stops_before_pairing() -> None:
    part = _blind_pocket()
    graph = FaceGraph(part)
    component = _component(part, graph)
    fragment = frozenset(sorted(component, key=lambda node: node.index)[:2])

    probe = _probe_component(part, graph, fragment, _proposal_groups(part, graph))

    assert probe.first_failed_gate == "fragmented_anatomy"


def test_equal_pockets_on_separate_bodies_retain_owners() -> None:
    first = _blind_pocket()
    second = Pos(100, 0, 0) * first
    compound = Compound(children=[first, second])
    graph = FaceGraph(compound)
    proposals = [
        proposal
        for solid in compound.solids()
        for proposal in _pocket_proposals_one(solid, graph=graph)
    ]

    assert len(proposals) == 2
    owners = [
        graph.common_valid_solid(
            proposal.planar
            | proposal.floors
            | frozenset(node for group in proposal.caps for node in group)
        )
        for proposal in proposals
    ]
    assert None not in owners
    assert owners[0] != owners[1]


def test_selection_hashes_pin_order_and_source_content() -> None:
    assert _selection_hash(["100", "200"]) != _selection_hash(["200", "100"])
    assert _source_selection_hash([("100", "aaa")]) != _source_selection_hash([("100", "changed")])
