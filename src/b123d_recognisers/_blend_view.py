# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Private immutable support-bridge view over original graph provenance."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from OCP.BRep import BRep_Tool

from b123d_recognisers._adjacency import (
    ArcKind,
    FaceGraphQuery,
    FaceNode,
    GraphRunToken,
    SharedEdgeOccurrenceRef,
    SmoothSide,
    SolidRef,
)
from b123d_recognisers._analytic_surfaces import SurfaceKind, equivalent_parameters
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveSurfaceQuery,
    OrientationCapability,
    SurfaceProvenance,
)


class BlendRefusalReason(Enum):
    UNSUPPORTED_SURFACE = "unsupported-surface"
    INCOMPLETE_BOUNDARY = "incomplete-boundary"
    BRANCHING_OR_CYCLE = "branching-or-cycle"
    MIXED_RADIUS_OR_SIDE = "mixed-radius-or-side"
    AMBIGUOUS_SUPPORT = "ambiguous-support"
    OWNERSHIP_UNPROVEN = "ownership-unproven"
    INVALID_LOCAL_SCALE = "invalid-local-scale"
    OVERLAPPING_COMPONENT = "overlapping-component"


@dataclass(frozen=True, eq=False, slots=True)
class OriginalArcRef:
    endpoints: tuple[FaceNode, FaceNode]
    occurrence: SharedEdgeOccurrenceRef


@dataclass(frozen=True, slots=True)
class FrozenProvenance:
    nodes: frozenset[FaceNode]
    arcs: tuple[OriginalArcRef, ...]


@dataclass(frozen=True, eq=False, slots=True)
class BlendChain:
    blend_nodes: frozenset[FaceNode]
    supports: tuple[frozenset[FaceNode], frozenset[FaceNode]]
    spring_arcs: tuple[OriginalArcRef, ...]
    internal_arcs: tuple[OriginalArcRef, ...]
    terminal_arcs: tuple[OriginalArcRef, ...]
    side: SmoothSide
    radius: float
    solid: SolidRef


@dataclass(frozen=True, slots=True)
class RefusedBlendComponent:
    nodes: frozenset[FaceNode]
    reason: BlendRefusalReason


BlendDiscoveryResult = BlendChain | RefusedBlendComponent


@dataclass(frozen=True, eq=False, slots=True)
class LogicalNode:
    sources: frozenset[FaceNode]


@dataclass(frozen=True, eq=False, slots=True)
class LogicalArc:
    endpoints: tuple[LogicalNode, LogicalNode]
    kind: ArcKind
    synthetic: bool


def _physical_length(occurrences: tuple[OriginalArcRef, ...]) -> float:
    seen: list = []
    lengths: list[float] = []
    for arc in occurrences:
        edge = arc.occurrence.edge
        if BRep_Tool.Degenerated_s(edge.wrapped):
            continue
        if any(edge.wrapped.IsSame(other.wrapped) for other in seen):
            continue
        seen.append(edge)
        lengths.append(float(edge.length))
    return math.fsum(lengths)


class BlendCollapseIndex:
    """Discover frozen neutral blend-chain occurrences once for one original graph."""

    def __init__(self, graph: FaceGraphQuery, surfaces: EffectiveSurfaceQuery) -> None:
        if graph.run_token is not surfaces.run_token:
            raise ValueError("blend graph and surface query belong to different runs")
        self._graph = graph
        self._surfaces = surfaces
        self._run_token: GraphRunToken = graph.run_token
        self._results: tuple[BlendDiscoveryResult, ...] | None = None
        self._issued_chains: dict[BlendChain, tuple] = {}
        self._issued_original_arcs: dict[OriginalArcRef, tuple] = {}
        self._issued_refusals: dict[RefusedBlendComponent, tuple] = {}

    @property
    def run_token(self) -> GraphRunToken:
        return self._run_token

    def results(self) -> tuple[BlendDiscoveryResult, ...]:
        if self._results is None:
            self._results = self._discover()
        for result in self._results:
            if isinstance(result, BlendChain):
                self._validate_chain(result)
            else:
                self._validate_refusal(result)
        return self._results

    def chains(self) -> tuple[BlendChain, ...]:
        return tuple(result for result in self.results() if isinstance(result, BlendChain))

    def view(self, selected: Iterable[BlendChain] = ()) -> CollapsedGraphView:
        selected = tuple(selected)
        seen_blends: set[FaceNode] = set()
        seen_arcs: set[SharedEdgeOccurrenceRef] = set()
        for chain in selected:
            self._validate_chain(chain)
            if seen_blends.intersection(chain.blend_nodes):
                raise ValueError("selected blend chains overlap")
            occurrences = {
                arc.occurrence
                for arc in (*chain.spring_arcs, *chain.internal_arcs, *chain.terminal_arcs)
            }
            if seen_arcs.intersection(occurrences):
                raise ValueError("selected blend chains share original arcs")
            seen_blends.update(chain.blend_nodes)
            seen_arcs.update(occurrences)
        return CollapsedGraphView(self, selected)

    def _fact(self, node: FaceNode) -> AnalyticSurfaceFact | None:
        fact = self._surfaces.fact(node)
        if not self._graph.owns(node):
            raise ValueError("surface query was asked with a foreign graph node")
        if not isinstance(fact, AnalyticSurfaceFact) or fact.node is not node:
            return None
        if (
            fact.provenance is not SurfaceProvenance.NATIVE
            or fact.orientation is not OrientationCapability.NATIVE_ORIENTED
        ):
            return None
        return fact

    def _cylinder(self, node: FaceNode) -> AnalyticSurfaceFact | None:
        fact = self._fact(node)
        return fact if fact is not None and fact.kind is SurfaceKind.CYLINDER else None

    def _pair_local(self, a: FaceNode, b: FaceNode) -> float | None:
        occurrences = self._graph.shared_occurrences(a, b)
        lengths = [float(item.edge.length) for item in occurrences]
        values = [
            math.sqrt(float(self._graph.face(a).area)),
            math.sqrt(float(self._graph.face(b).area)),
            *lengths,
        ]
        if not values or not all(math.isfinite(value) and value > 0.0 for value in values):
            return None
        return min(values)

    def _native_neutral(self, a: FaceNode, b: FaceNode) -> bool:
        legacy_smooth = self._graph.arc(a, b) == "smooth"
        neutral_side = self._graph.smooth_side(a, b) == "neutral"
        if not (legacy_smooth and neutral_side):
            return False
        left, right = self._fact(a), self._fact(b)
        if left is None or right is None or left.kind is not right.kind:
            return False
        local = self._pair_local(a, b)
        return local is not None and equivalent_parameters(
            left.kind, left.parameters, right.parameters, local=local
        )

    def _cylinder_components(self) -> tuple[frozenset[FaceNode], ...]:
        pending = {node for node in self._graph.nodes if self._cylinder(node) is not None}
        components: list[frozenset[FaceNode]] = []
        while pending:
            first = next(iter(pending))
            pending.remove(first)
            found = {first}
            queue = deque((first,))
            while queue:
                current = queue.popleft()
                for neighbour in self._graph.neighbours(current):
                    if neighbour in pending and self._native_neutral(current, neighbour):
                        pending.remove(neighbour)
                        found.add(neighbour)
                        queue.append(neighbour)
            components.append(frozenset(found))
        return tuple(components)

    def _support_region(
        self, first: FaceNode, *, excluded: frozenset[FaceNode]
    ) -> frozenset[FaceNode]:
        found = {first}
        queue = deque((first,))
        while queue:
            current = queue.popleft()
            for neighbour in self._graph.neighbours(current):
                if neighbour in found or neighbour in excluded:
                    continue
                if self._native_neutral(current, neighbour):
                    found.add(neighbour)
                    queue.append(neighbour)
        return frozenset(found)

    def _arc_refs(self, a: FaceNode, b: FaceNode) -> tuple[OriginalArcRef, ...]:
        found = tuple(
            OriginalArcRef(item.endpoints, item) for item in self._graph.shared_occurrences(a, b)
        )
        for arc in found:
            self._issued_original_arcs[arc] = (arc.endpoints, arc.occurrence)
        return found

    def _validate_original_arc(self, arc: OriginalArcRef) -> None:
        snapshot = self._issued_original_arcs.get(arc)
        if snapshot is None:
            raise ValueError("original arc was not issued by this blend index")
        endpoints, issued_occurrence = snapshot
        occurrence = arc.occurrence
        # ``ownership`` first revalidates the graph-issued occurrence even when ownership is
        # unavailable, which is the only read boundary this neutral value needs.
        self._graph.ownership(occurrence)
        if (
            occurrence is not issued_occurrence
            or any(
                actual is not expected
                for actual, expected in zip(arc.endpoints, endpoints, strict=True)
            )
            or any(
                actual is not expected
                for actual, expected in zip(arc.endpoints, occurrence.endpoints, strict=True)
            )
        ):
            raise ValueError("original arc endpoints changed after issuance")

    def _refuse(
        self, component: frozenset[FaceNode], reason: BlendRefusalReason
    ) -> RefusedBlendComponent:
        refusal = RefusedBlendComponent(component, reason)
        self._issued_refusals[refusal] = (component, reason)
        return refusal

    def _validate_refusal(self, refusal: RefusedBlendComponent) -> None:
        snapshot = self._issued_refusals.get(refusal)
        if snapshot is None or refusal.nodes != snapshot[0] or refusal.reason is not snapshot[1]:
            raise ValueError("blend refusal changed after issuance")
        if not all(self._graph.owns(node) for node in refusal.nodes):
            raise ValueError("blend refusal contains a changed graph node")

    def _classify(self, component: frozenset[FaceNode]) -> BlendDiscoveryResult:
        internal: list[OriginalArcRef] = []
        spring_by_patch: dict[FaceNode, dict[frozenset[FaceNode], list[OriginalArcRef]]] = {
            node: {} for node in component
        }
        terminal_by_face: dict[FaceNode, list[OriginalArcRef]] = {}
        sides: set[SmoothSide] = set()
        solid = None
        internal_degree = {node: 0 for node in component}
        accounted_halves: set = set()
        for node in component:
            for neighbour in self._graph.neighbours(node):
                if neighbour in component and node.index > neighbour.index:
                    continue
                refs = self._arc_refs(node, neighbour)
                if not refs:
                    return self._refuse(component, BlendRefusalReason.INCOMPLETE_BOUNDARY)
                for ref in refs:
                    accounted_halves.update(ref.occurrence.halves)
                    ownership = self._graph.ownership(ref.occurrence)
                    if ownership is None:
                        return self._refuse(component, BlendRefusalReason.OWNERSHIP_UNPROVEN)
                    if solid is None:
                        solid = ownership.solid
                    elif ownership.solid is not solid:
                        return self._refuse(component, BlendRefusalReason.OWNERSHIP_UNPROVEN)
                if neighbour in component:
                    if not self._native_neutral(node, neighbour):
                        return self._refuse(component, BlendRefusalReason.MIXED_RADIUS_OR_SIDE)
                    internal.extend(refs)
                    internal_degree[node] += 1
                    internal_degree[neighbour] += 1
                    continue
                side = self._graph.smooth_side(node, neighbour)
                if self._graph.arc(node, neighbour) == "smooth" and side in ("convex", "concave"):
                    region = self._support_region(neighbour, excluded=component)
                    spring_by_patch[node].setdefault(region, []).extend(refs)
                    sides.add(side)
                    continue
                if self._graph.arc(node, neighbour) == "smooth":
                    return self._refuse(component, BlendRefusalReason.INCOMPLETE_BOUNDARY)
                terminal_by_face.setdefault(neighbour, []).extend(refs)

        for node in component:
            face = self._graph.face(node)
            for occurrence in self._graph.edge_occurrences(node):
                if occurrence in accounted_halves:
                    continue
                edge = occurrence.edge
                if BRep_Tool.IsClosed_s(edge.wrapped, face.wrapped) or BRep_Tool.Degenerated_s(
                    edge.wrapped
                ):
                    continue
                return self._refuse(component, BlendRefusalReason.INCOMPLETE_BOUNDARY)

        if len(component) == 1:
            if next(iter(internal_degree.values())) != 0:
                return self._refuse(component, BlendRefusalReason.BRANCHING_OR_CYCLE)
        else:
            degrees = tuple(internal_degree.values())
            if degrees.count(1) != 2 or any(value not in (1, 2) for value in degrees):
                return self._refuse(component, BlendRefusalReason.BRANCHING_OR_CYCLE)
        if len(sides) != 1:
            return self._refuse(component, BlendRefusalReason.MIXED_RADIUS_OR_SIDE)
        support_sets = {region for groups in spring_by_patch.values() for region in groups}
        if len(support_sets) != 2 or any(
            set(groups) != support_sets for groups in spring_by_patch.values()
        ):
            return self._refuse(component, BlendRefusalReason.AMBIGUOUS_SUPPORT)

        terminal_groups: list[set[FaceNode]] = []
        pending = set(terminal_by_face)
        while pending:
            first = pending.pop()
            group = {first}
            queue = deque((first,))
            while queue:
                current = queue.popleft()
                for neighbour in self._graph.neighbours(current):
                    if neighbour in pending:
                        pending.remove(neighbour)
                        group.add(neighbour)
                        queue.append(neighbour)
            terminal_groups.append(group)
        if len(terminal_groups) != 2:
            return self._refuse(component, BlendRefusalReason.INCOMPLETE_BOUNDARY)

        supports = tuple(
            sorted(support_sets, key=lambda region: min(node.index for node in region))
        )
        spring_groups = tuple(
            tuple(arc for node in component for arc in spring_by_patch[node][support])
            for support in supports
        )
        terminal_groups_arcs = tuple(
            tuple(arc for face in group for arc in terminal_by_face[face])
            for group in terminal_groups
        )
        first_fact = self._cylinder(next(iter(component)))
        assert first_fact is not None
        radius = first_fact.parameters[-1]
        local_values = [
            radius,
            *(_physical_length(group) for group in (*spring_groups, *terminal_groups_arcs)),
            math.sqrt(math.fsum(float(self._graph.face(node).area) for node in component)),
            *(
                math.sqrt(math.fsum(float(self._graph.face(node).area) for node in support))
                for support in supports
            ),
        ]
        if not all(math.isfinite(value) and value > 0.0 for value in local_values):
            return self._refuse(component, BlendRefusalReason.INVALID_LOCAL_SCALE)
        local = min(local_values)
        if any(
            (fact := self._cylinder(node)) is None
            or not equivalent_parameters(
                SurfaceKind.CYLINDER, first_fact.parameters, fact.parameters, local=local
            )
            for node in component
        ):
            return self._refuse(component, BlendRefusalReason.MIXED_RADIUS_OR_SIDE)

        side = sides.pop()
        assert side in ("convex", "concave")
        assert solid is not None
        chain = BlendChain(
            blend_nodes=component,
            supports=(supports[0], supports[1]),
            spring_arcs=tuple(arc for group in spring_groups for arc in group),
            internal_arcs=tuple(internal),
            terminal_arcs=tuple(arc for group in terminal_groups_arcs for arc in group),
            side=side,
            radius=radius,
            solid=solid,
        )
        self._issued_chains[chain] = (
            chain.blend_nodes,
            chain.supports,
            chain.spring_arcs,
            chain.internal_arcs,
            chain.terminal_arcs,
            chain.side,
            chain.radius,
            chain.solid,
        )
        return chain

    def _discover(self) -> tuple[BlendDiscoveryResult, ...]:
        results = [self._classify(component) for component in self._cylinder_components()]
        chains = [result for result in results if isinstance(result, BlendChain)]
        conflicted: set[BlendChain] = set()
        for at, left in enumerate(chains):
            for right in chains[at + 1 :]:
                if left.blend_nodes.intersection(right.blend_nodes):
                    conflicted.update((left, right))
                    continue
                for left_support in left.supports:
                    for right_support in right.supports:
                        if left_support != right_support and left_support.intersection(
                            right_support
                        ):
                            conflicted.update((left, right))
        if not conflicted:
            return tuple(results)
        final: list[BlendDiscoveryResult] = []
        for result in results:
            if isinstance(result, BlendChain) and result in conflicted:
                self._issued_chains.pop(result, None)
                final.append(
                    self._refuse(result.blend_nodes, BlendRefusalReason.OVERLAPPING_COMPONENT)
                )
            else:
                final.append(result)
        return tuple(final)

    def _validate_chain(self, chain: BlendChain) -> None:
        snapshot = self._issued_chains.get(chain)
        if snapshot is None:
            raise ValueError("blend chain was not issued by this index")
        actual = (
            chain.blend_nodes,
            chain.supports,
            chain.spring_arcs,
            chain.internal_arcs,
            chain.terminal_arcs,
            chain.side,
            chain.radius,
            chain.solid,
        )
        if (
            any(
                value != expected
                for value, expected in zip(actual[:-1], snapshot[:-1], strict=True)
            )
            or actual[-1] is not snapshot[-1]
        ):
            raise ValueError("blend chain changed after issuance")
        if not all(
            self._graph.owns(node)
            for node in (*chain.blend_nodes, *chain.supports[0], *chain.supports[1])
        ):
            raise ValueError("blend chain contains a changed graph node")
        owned_solids: set[SolidRef] = set()
        for arc in (*chain.spring_arcs, *chain.internal_arcs, *chain.terminal_arcs):
            self._validate_original_arc(arc)
            ownership = self._graph.ownership(arc.occurrence)
            if ownership is None:
                raise ValueError("blend chain ownership changed after issuance")
            owned_solids.add(ownership.solid)
        if owned_solids != {chain.solid}:
            raise ValueError("blend chain solid changed after issuance")


class CollapsedGraphView:
    """Explicit selected support bridges with complete original provenance."""

    def __init__(self, index: BlendCollapseIndex, selected: tuple[BlendChain, ...]) -> None:
        self._index = index
        self._graph = index._graph
        self._selected = selected
        hidden = frozenset(node for chain in selected for node in chain.blend_nodes)
        support_sets: list[frozenset[FaceNode]] = []
        for chain in selected:
            for support in chain.supports:
                if support not in support_sets:
                    support_sets.append(support)
        covered = frozenset(node for support in support_sets for node in support)
        sources = support_sets + [
            frozenset((node,))
            for node in self._graph.nodes
            if node not in hidden and node not in covered
        ]
        self._nodes = tuple(LogicalNode(source) for source in sources)
        self._issued_nodes = {node: node.sources for node in self._nodes}
        self._by_source = {source: node for node in self._nodes for source in node.sources}
        arcs: list[LogicalArc] = []
        provenance: dict[LogicalArc, FrozenProvenance] = {}
        for at, left in enumerate(self._graph.nodes):
            if left in hidden:
                continue
            for right in self._graph.nodes[at + 1 :]:
                if right in hidden:
                    continue
                mapped_left, mapped_right = self._by_source[left], self._by_source[right]
                refs = self._index._arc_refs(left, right)
                if mapped_left is mapped_right:
                    continue
                kind = self._graph.arc(left, right)
                if kind is None:
                    continue
                for ref in refs:
                    arc = LogicalArc((mapped_left, mapped_right), kind, False)
                    arcs.append(arc)
                    provenance[arc] = FrozenProvenance(frozenset((left, right)), (ref,))
        for chain in selected:
            logical_left, logical_right = (
                self._by_source[next(iter(source))] for source in chain.supports
            )
            bridge_kind: ArcKind = "convex" if chain.side == "convex" else "concave"
            arc = LogicalArc((logical_left, logical_right), bridge_kind, True)
            arcs.append(arc)
            provenance[arc] = FrozenProvenance(
                frozenset((*chain.blend_nodes, *chain.supports[0], *chain.supports[1])),
                (*chain.spring_arcs, *chain.internal_arcs, *chain.terminal_arcs),
            )
        self._arcs = tuple(arcs)
        self._issued_arcs = {
            arc: (arc.endpoints, arc.kind, arc.synthetic, provenance[arc]) for arc in arcs
        }

    def logical_nodes(self) -> tuple[LogicalNode, ...]:
        for node in self._nodes:
            self._validate_node(node)
        return self._nodes

    def _validate_node(self, node: LogicalNode) -> None:
        snapshot = self._issued_nodes.get(node)
        if (
            snapshot is None
            or node.sources != snapshot
            or not all(self._graph.owns(source) for source in node.sources)
        ):
            raise ValueError("logical node is foreign or changed")

    def _validate_arc(self, arc: LogicalArc) -> FrozenProvenance:
        snapshot = self._issued_arcs.get(arc)
        if snapshot is None:
            raise ValueError("logical arc was not issued by this view")
        endpoints, kind, synthetic, provenance = snapshot
        if (
            any(
                actual is not expected
                for actual, expected in zip(arc.endpoints, endpoints, strict=True)
            )
            or arc.kind != kind
            or arc.synthetic is not synthetic
        ):
            raise ValueError("logical arc changed after issuance")
        for endpoint in endpoints:
            self._validate_node(endpoint)
        for original in provenance.arcs:
            self._index._validate_original_arc(original)
        if not all(self._graph.owns(node) for node in provenance.nodes):
            raise ValueError("logical arc provenance contains a changed graph node")
        return provenance

    def neighbours(self, node: LogicalNode) -> tuple[LogicalNode, ...]:
        self._validate_node(node)
        found: list[LogicalNode] = []
        for arc in self._arcs:
            self._validate_arc(arc)
            if arc.endpoints[0] is node and arc.endpoints[1] not in found:
                found.append(arc.endpoints[1])
            elif arc.endpoints[1] is node and arc.endpoints[0] not in found:
                found.append(arc.endpoints[0])
        return tuple(found)

    def arcs_between(self, a: LogicalNode, b: LogicalNode) -> tuple[LogicalArc, ...]:
        self._validate_node(a)
        self._validate_node(b)
        result = tuple(
            arc
            for arc in self._arcs
            if (arc.endpoints[0] is a and arc.endpoints[1] is b)
            or (arc.endpoints[0] is b and arc.endpoints[1] is a)
        )
        for arc in result:
            self._validate_arc(arc)
        return result

    def expand_node(self, node: LogicalNode) -> frozenset[FaceNode]:
        self._validate_node(node)
        return self._issued_nodes[node]

    def expand_arc(self, arc: LogicalArc) -> FrozenProvenance:
        return self._validate_arc(arc)
