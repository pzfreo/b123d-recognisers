# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import copy
from dataclasses import dataclass

import pytest
from build123d import Axis, Box, Cylinder, Plane, Pos, export_step, fillet, import_step

from b123d_recognisers._adjacency import (
    EdgeOccurrenceRef,
    EdgeOwnershipFact,
    FaceGraph,
    FaceNode,
    GraphRunToken,
    SharedEdgeOccurrenceRef,
    SolidRef,
)
from b123d_recognisers._analytic_surfaces import SurfaceKind
from b123d_recognisers._blend_view import (
    BlendChain,
    BlendCollapseIndex,
    RefusedBlendComponent,
)
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveSurfaceIndex,
    OrientationCapability,
    RefusedSurfaceFact,
    SurfaceProvenance,
    SurfaceRefusalReason,
)


def _external():
    return fillet(Box(40, 20, 10).edges().filter_by(Axis.Z), radius=3)


def _internal():
    cutter = fillet(Box(12, 12, 20).edges().filter_by(Axis.Z), radius=2)
    return Box(30, 30, 10) - Pos(0, 0, -5) * cutter


def _index(part):
    graph = FaceGraph(part)
    return graph, BlendCollapseIndex(graph, EffectiveSurfaceIndex(graph))


def _base_occurrence_count(graph: FaceGraph) -> int:
    return sum(
        len(graph.shared_occurrences(left, right))
        for at, left in enumerate(graph.nodes)
        for right in graph.nodes[at + 1 :]
    )


@dataclass
class _SyntheticGraph:
    nodes: tuple[FaceNode, ...]
    faces: tuple
    adjacency: dict[tuple[int, int], SharedEdgeOccurrenceRef]
    arcs: dict[tuple[int, int], str]
    sides: dict[tuple[int, int], str]
    run_token: GraphRunToken
    solid: SolidRef

    def owns(self, node):
        return any(node is issued for issued in self.nodes)

    def face(self, node):
        assert self.owns(node)
        return self.faces[node.index]

    def neighbours(self, node):
        return tuple(
            self.nodes[right if left == node.index else left]
            for left, right in self.adjacency
            if node.index in (left, right)
        )

    def arc(self, a, b):
        return self.arcs.get(tuple(sorted((a.index, b.index))))

    def smooth_side(self, a, b):
        return self.sides.get(tuple(sorted((a.index, b.index))))

    def shared_occurrences(self, a, b):
        found = self.adjacency.get(tuple(sorted((a.index, b.index))))
        return () if found is None else (found,)

    def edge_occurrences(self, node):
        return tuple(
            half
            for occurrence in self.adjacency.values()
            for half in occurrence.halves
            if half.owner is node
        )

    def ownership(self, occurrence):
        return EdgeOwnershipFact(self.solid, occurrence)


@dataclass
class _SyntheticSurfaces:
    run_token: GraphRunToken
    facts: dict[FaceNode, AnalyticSurfaceFact | RefusedSurfaceFact]

    def fact(self, node):
        return self.facts[node]


def _split_strip_capabilities():
    # B0--B1 is a split cylindrical strip. Each patch has one spring to both supports and one
    # terminal at its path end. This isolates the exact multi-patch grammar from kernel meshing.
    nodes = tuple(FaceNode(at) for at in range(6))
    b0, b1, support_a, support_b, terminal_a, terminal_b = nodes
    pairs = (
        (b0, b1, "smooth", "neutral"),
        (b0, support_a, "smooth", "convex"),
        (b0, support_b, "smooth", "convex"),
        (b1, support_a, "smooth", "convex"),
        (b1, support_b, "smooth", "convex"),
        (b0, terminal_a, "convex", None),
        (b1, terminal_b, "convex", None),
    )
    edges = Box(10, 10, 10).edges()
    adjacency = {}
    arcs = {}
    sides = {}
    for ordinal, (left, right, kind, side) in enumerate(pairs):
        edge = edges[ordinal]
        left_half = EdgeOccurrenceRef(left, 0, ordinal, False, edge)
        right_half = EdgeOccurrenceRef(right, 0, ordinal, True, edge)
        key = tuple(sorted((left.index, right.index)))
        adjacency[key] = SharedEdgeOccurrenceRef(
            (nodes[key[0]], nodes[key[1]]), (left_half, right_half), edge
        )
        arcs[key] = kind
        if side is not None:
            sides[key] = side
    token, solid = GraphRunToken(), SolidRef(0)
    faces = tuple(Box(2, 2, 2).faces()[at % 6] for at in range(6))
    graph = _SyntheticGraph(nodes, faces, adjacency, arcs, sides, token, solid)
    cylinder = (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 2.0)
    plane_a = (1.0, 0.0, 0.0, 1.0)
    plane_b = (0.0, 1.0, 0.0, 1.0)
    facts = {}
    for node, kind, parameters in (
        (b0, SurfaceKind.CYLINDER, cylinder),
        (b1, SurfaceKind.CYLINDER, cylinder),
        (support_a, SurfaceKind.PLANE, plane_a),
        (support_b, SurfaceKind.PLANE, plane_b),
    ):
        facts[node] = AnalyticSurfaceFact(
            node,
            kind,
            SurfaceProvenance.NATIVE,
            OrientationCapability.NATIVE_ORIENTED,
            parameters,
            0.0,
            0.0,
            None,
        )
    for node in (terminal_a, terminal_b):
        facts[node] = RefusedSurfaceFact(node, SurfaceRefusalReason.UNSUPPORTED_KIND)
    return graph, _SyntheticSurfaces(token, facts)


def test_graph_issues_one_paired_oriented_occurrence_per_box_adjacency():
    graph = FaceGraph(Box(2, 3, 4))
    occurrences = [
        occurrence
        for at, left in enumerate(graph.nodes)
        for right in graph.nodes[at + 1 :]
        for occurrence in graph.shared_occurrences(left, right)
    ]
    assert len(occurrences) == 12
    for occurrence in occurrences:
        assert occurrence.endpoints == tuple(half.owner for half in occurrence.halves)
        assert len({half.ordinal for half in occurrence.halves}) >= 1
        assert graph.ownership(occurrence).occurrence is occurrence


def test_half_edge_identity_keeps_inner_and_outer_wire_ordinals():
    graph = FaceGraph(Box(20, 20, 5) - Cylinder(3, 5))
    top = max(graph.nodes, key=lambda node: graph.face(node).center().Z)
    occurrences = graph._face_edge_occurrences(top)
    assert {occurrence.wire_ordinal for occurrence in occurrences} == {0, 1}
    assert len(
        {(occurrence.wire_ordinal, occurrence.ordinal) for occurrence in occurrences}
    ) == len(occurrences)


def test_graph_occurrences_reject_foreign_copies_and_mutation():
    graph = FaceGraph(Box(2, 3, 4))
    left = graph.nodes[0]
    right = graph.neighbours(left)[0]
    (occurrence,) = graph.shared_occurrences(left, right)
    with pytest.raises(ValueError, match="not issued"):
        graph.ownership(copy.copy(occurrence))
    object.__setattr__(occurrence.halves[0], "ordinal", 999)
    with pytest.raises(ValueError, match="changed"):
        graph.ownership(occurrence)


@pytest.mark.parametrize(
    ("part", "side", "count"),
    [(_external(), "convex", 4), (_internal(), "concave", 4)],
)
def test_single_cylindrical_blend_patches_form_closed_chains(part, side, count):
    _, index = _index(part)
    chains = index.chains()
    assert len(chains) == count
    assert {chain.side for chain in chains} == {side}
    for chain in chains:
        assert len(chain.blend_nodes) == 1
        assert len(chain.supports) == 2
        assert len(chain.spring_arcs) == 2
        assert len(chain.internal_arcs) == 0
        assert len(chain.terminal_arcs) == 2


def test_split_cylindrical_strip_is_one_complete_multi_patch_chain():
    graph, surfaces = _split_strip_capabilities()
    (chain,) = BlendCollapseIndex(graph, surfaces).chains()
    assert len(chain.blend_nodes) == 2
    assert len(chain.internal_arcs) == 1
    assert len(chain.spring_arcs) == 4
    assert len(chain.terminal_arcs) == 2
    assert chain.side == "convex"


def test_split_strip_refuses_partial_support_and_mixed_side_mutations():
    graph, surfaces = _split_strip_capabilities()
    # B0 loses its spring to support A; a complete component may not be salvaged as a subset.
    removed = (0, 2)
    graph.adjacency.pop(removed)
    graph.arcs.pop(removed)
    graph.sides.pop(removed)
    results = BlendCollapseIndex(graph, surfaces).results()
    assert not any(isinstance(result, BlendChain) for result in results)

    graph, surfaces = _split_strip_capabilities()
    graph.sides[(1, 3)] = "concave"
    results = BlendCollapseIndex(graph, surfaces).results()
    assert not any(isinstance(result, BlendChain) for result in results)
    assert any(
        isinstance(result, RefusedBlendComponent) and result.reason.value == "mixed-radius-or-side"
        for result in results
    )


def test_maximal_cylindrical_cycle_refuses_instead_of_selecting_a_path_subset():
    graph, surfaces = _split_strip_capabilities()
    third = FaceNode(6)
    graph.nodes = (*graph.nodes, third)
    graph.faces = (*graph.faces, Box(2, 2, 2).faces()[0])
    template = surfaces.facts[graph.nodes[0]]
    assert isinstance(template, AnalyticSurfaceFact)
    surfaces.facts[third] = AnalyticSurfaceFact(
        third,
        template.kind,
        template.provenance,
        template.orientation,
        template.parameters,
        0.0,
        0.0,
        None,
    )
    support_a, support_b = graph.nodes[2], graph.nodes[3]
    for ordinal, (other, side) in enumerate(
        (
            (graph.nodes[0], "neutral"),
            (graph.nodes[1], "neutral"),
            (support_a, "convex"),
            (support_b, "convex"),
        ),
        start=20,
    ):
        edge = Box(3, 3, 3).edges()[ordinal % 12]
        key = tuple(sorted((third.index, other.index)))
        left, right = graph.nodes[key[0]], graph.nodes[key[1]]
        graph.adjacency[key] = SharedEdgeOccurrenceRef(
            (left, right),
            (
                EdgeOccurrenceRef(left, 0, ordinal, False, edge),
                EdgeOccurrenceRef(right, 0, ordinal, True, edge),
            ),
            edge,
        )
        graph.arcs[key] = "smooth"
        graph.sides[key] = side
    results = BlendCollapseIndex(graph, surfaces).results()
    assert not any(isinstance(result, BlendChain) for result in results)
    assert any(
        isinstance(result, RefusedBlendComponent) and result.reason.value == "branching-or-cycle"
        for result in results
    )


def test_split_strip_refuses_unproved_ownership_and_invalid_local_radius(monkeypatch):
    graph, surfaces = _split_strip_capabilities()
    monkeypatch.setattr(graph, "ownership", lambda occurrence: None)
    results = BlendCollapseIndex(graph, surfaces).results()
    assert any(
        isinstance(result, RefusedBlendComponent) and result.reason.value == "ownership-unproven"
        for result in results
    )

    graph, surfaces = _split_strip_capabilities()
    first = graph.nodes[0]
    fact = surfaces.facts[first]
    assert isinstance(fact, AnalyticSurfaceFact)
    surfaces.facts[first] = AnalyticSurfaceFact(
        fact.node,
        fact.kind,
        fact.provenance,
        fact.orientation,
        (*fact.parameters[:-1], 0.0),
        fact.requested_tolerance,
        fact.kernel_reported_gap,
        fact.certificate,
    )
    results = BlendCollapseIndex(graph, surfaces).results()
    assert not any(isinstance(result, BlendChain) for result in results)


def test_ordinary_cylinder_is_a_closed_refusal_not_a_bridge():
    _, index = _index(Cylinder(5, 10))
    assert index.chains() == ()
    assert any(isinstance(result, RefusedBlendComponent) for result in index.results())


def test_empty_view_is_exact_singleton_base_projection():
    graph, index = _index(_external())
    view = index.view(())
    assert tuple(view.expand_node(node) for node in view.logical_nodes()) == tuple(
        frozenset((node,)) for node in graph.nodes
    )
    assert sum(
        len(view.arcs_between(left, right))
        for at, left in enumerate(view.logical_nodes())
        for right in view.logical_nodes()[at + 1 :]
    ) == _base_occurrence_count(graph)


def test_selected_chain_hides_only_blend_and_adds_provenance_complete_bridge():
    graph, index = _index(_external())
    chain = index.chains()[0]
    view = index.view((chain,))
    assert len(view.logical_nodes()) == len(graph.nodes) - len(chain.blend_nodes)
    support_nodes = tuple(
        node for node in view.logical_nodes() if view.expand_node(node) in chain.supports
    )
    assert len(support_nodes) == 2
    bridges = tuple(arc for arc in view.arcs_between(*support_nodes) if arc.synthetic)
    assert len(bridges) == 1
    provenance = view.expand_arc(bridges[0])
    assert provenance.nodes == frozenset(
        (*chain.blend_nodes, *chain.supports[0], *chain.supports[1])
    )
    assert provenance.arcs == (
        *chain.spring_arcs,
        *chain.internal_arcs,
        *chain.terminal_arcs,
    )


def test_foreign_surface_capability_fails_at_construction_even_for_empty_graph():
    graph = FaceGraph(Box(1, 1, 1))
    foreign = FaceGraph(Box(1, 1, 1))
    with pytest.raises(ValueError, match="different runs"):
        BlendCollapseIndex(graph, EffectiveSurfaceIndex(foreign))


def test_chain_and_logical_handles_revalidate_issuer_snapshots():
    _, index = _index(_external())
    chain = index.chains()[0]
    with pytest.raises(ValueError, match="not issued"):
        index.view((copy.copy(chain),))
    view = index.view((chain,))
    node = view.logical_nodes()[0]
    object.__setattr__(node, "sources", frozenset())
    with pytest.raises(ValueError, match="changed"):
        view.expand_node(node)


def test_nested_arc_solid_and_refusal_mutation_fail_on_warm_reads():
    graph, index = _index(_external())
    chain = index.chains()[0]
    original = chain.spring_arcs[0]
    object.__setattr__(original, "endpoints", tuple(reversed(original.endpoints)))
    with pytest.raises(ValueError, match="endpoints changed"):
        index.chains()

    _, solid_index = _index(_external())
    solid_chain = solid_index.chains()[0]
    object.__setattr__(solid_chain.solid, "ordinal", 99)
    with pytest.raises(ValueError, match="solid reference changed"):
        solid_index.chains()

    _, refused_index = _index(Cylinder(5, 10))
    refusal = next(
        result for result in refused_index.results() if isinstance(result, RefusedBlendComponent)
    )
    object.__setattr__(refusal, "reason", None)
    with pytest.raises(ValueError, match="refusal changed"):
        refused_index.results()


@pytest.mark.parametrize(
    "part",
    [
        _external().mirror(Plane.YZ),
        _external().rotate(Axis((0, 0, 0), (1, 1, 0)), 37),
        _external().scale(10),
    ],
)
def test_rigid_mirror_and_scale_keep_four_provenance_complete_chains(part):
    _, index = _index(part)
    signatures = sorted(
        (
            chain.side,
            len(chain.blend_nodes),
            len(chain.spring_arcs),
            len(chain.terminal_arcs),
        )
        for chain in index.chains()
    )
    assert signatures == [("convex", 1, 2, 2)] * 4


def test_step_round_trip_preserves_chain_incidence(tmp_path):
    target = tmp_path / "filleted.step"
    export_step(_external(), target)
    _, index = _index(import_step(target))
    assert (
        sorted(
            (chain.side, len(chain.spring_arcs), len(chain.terminal_arcs))
            for chain in index.chains()
        )
        == [("convex", 2, 2)] * 4
    )


def test_all_disjoint_box_chains_can_be_selected_atomically():
    _, index = _index(_external())
    chains = index.chains()
    view = index.view(chains)
    assert sum(
        arc.synthetic
        for at, left in enumerate(view.logical_nodes())
        for right in view.logical_nodes()[at + 1 :]
        for arc in view.arcs_between(left, right)
    ) == len(chains)
