# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Experimental read-only geometry facade for the F7 consumer spike.

This module is deliberately absent from :mod:`b123d_recognisers`' root exports and
capability manifest.  It exists to test a small graph-bound surface/blend contract
with two real consumers before any supported API is frozen.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import cast

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.Standard import Standard_Failure

from b123d_recognisers._adjacency import ArcKind, FaceGraph, FaceNode, SmoothSide
from b123d_recognisers._blend_view import BlendChain, BlendCollapseIndex
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveSurfaceIndex,
    RefusedSurfaceFact,
)
from b123d_recognisers._typing import FaceLike, Part


class SurfaceKind(Enum):
    PLANE = "plane"
    CYLINDER = "cylinder"
    CONE = "cone"
    SPHERE = "sphere"


class SurfaceProvenance(Enum):
    NATIVE = "native"
    RECOVERED = "recovered"


class OrientationCapability(Enum):
    NATIVE_ORIENTED = "native-oriented"
    RECOVERED_UNORIENTED = "recovered-unoriented"


class SurfaceRefusalReason(Enum):
    UNSUPPORTED_KIND = "unsupported-kind"
    UNSUPPORTED_TORUS_RECOVERY = "unsupported-torus-recovery"
    FIT_UNAVAILABLE = "fit-unavailable"
    INVALID_INPUT = "invalid-input"
    INVALID_RESULT = "invalid-result"
    RESIDUAL_EXCEEDED = "residual-exceeded"
    AMBIGUOUS_PRIMITIVE = "ambiguous-primitive"
    UNSUPPORTED_OCCT_CONTRACT = "unsupported-occt-contract"


class FaceRef:
    """Opaque identity for one face during one :class:`GeometryGraph` run."""

    __slots__ = ("_authority", "_node")

    def __init__(self, authority: object, node: object) -> None:
        self._authority = authority
        self._node = node


class BoundaryRef:
    """Opaque identity for one original shared-edge occurrence."""

    __slots__ = ("_authority", "_occurrence")

    def __init__(self, authority: object, occurrence: object) -> None:
        self._authority = authority
        self._occurrence = occurrence


class BlendRef:
    """Opaque identity for one blend chain issued by a graph."""

    __slots__ = ("_authority", "_chain")

    def __init__(self, authority: object, chain: object) -> None:
        self._authority = authority
        self._chain = chain


@dataclass(frozen=True, slots=True)
class AnalyticSurface:
    kind: SurfaceKind
    provenance: SurfaceProvenance
    orientation: OrientationCapability
    parameters: tuple[float, ...]
    requested_tolerance: float
    kernel_reported_gap: float


@dataclass(frozen=True, slots=True)
class RefusedSurface:
    reason: SurfaceRefusalReason


SurfaceFact = AnalyticSurface | RefusedSurface


@dataclass(frozen=True, slots=True)
class BlendFact:
    ref: BlendRef
    blend_faces: frozenset[FaceRef]
    supports: tuple[frozenset[FaceRef], frozenset[FaceRef]]
    side: SmoothSide
    radius: float
    boundary: tuple[BoundaryRef, ...]


@dataclass(frozen=True, slots=True)
class GeometryProvenance:
    faces: frozenset[FaceRef]
    boundary: tuple[BoundaryRef, ...]


@dataclass(frozen=True, slots=True)
class CollapsedBridge:
    supports: tuple[FaceRef, FaceRef]
    kind: ArcKind
    provenance: GeometryProvenance


class GeometryGraph:
    """Small read-only facade over one run-owned face graph.

    Handles are identity values, valid only for this object.  ``face()`` is the
    single borrowed-build123d escape hatch; mutating the part or borrowed wrapper
    invalidates the facade and is unsupported during a run.
    """

    def __init__(self, part: Part | None, *, _graph: FaceGraph | None = None) -> None:
        if _graph is None and part is None:
            raise TypeError("GeometryGraph requires a part")
        self.__graph = FaceGraph(part) if _graph is None else _graph
        self.__authority = object()
        self.__refs = tuple(FaceRef(self.__authority, node) for node in self.__graph.nodes)
        self.__by_node = dict(zip(self.__graph.nodes, self.__refs, strict=True))
        self.__surfaces = EffectiveSurfaceIndex(self.__graph)
        self.__blends: BlendCollapseIndex | None = None
        self.__blend_refs: dict[BlendChain, BlendRef] = {}
        self.__boundary_refs: dict[object, BoundaryRef] = {}

    @classmethod
    def _from_graph(cls, graph: FaceGraph) -> GeometryGraph:
        """Package-private adapter for an existing aggregate recognition run."""

        return cls(None, _graph=graph)

    @property
    def faces(self) -> tuple[FaceRef, ...]:
        return self.__refs

    def __len__(self) -> int:
        return len(self.__refs)

    def _node(self, ref: FaceRef) -> FaceNode:
        if type(ref) is not FaceRef or ref._authority is not self.__authority:
            raise ValueError("face reference is foreign to this geometry graph")
        node = cast(FaceNode, ref._node)
        if self.__by_node.get(node) is not ref or not self.__graph.owns(node):
            raise ValueError("face reference is copied, changed, or stale")
        return node

    def ref(self, face: FaceLike) -> FaceRef:
        return self.__by_node[self.__graph.require_node(face)]

    def face(self, ref: FaceRef) -> FaceLike:
        return self.__graph.face(self._node(ref))

    def neighbours(self, ref: FaceRef) -> tuple[FaceRef, ...]:
        return tuple(self.__by_node[node] for node in self.__graph.neighbours(self._node(ref)))

    def arc(self, left: FaceRef, right: FaceRef) -> ArcKind | None:
        return self.__graph.arc(self._node(left), self._node(right))

    def smooth_side(self, left: FaceRef, right: FaceRef) -> SmoothSide | None:
        return self.__graph.smooth_side(self._node(left), self._node(right))

    def smooth_region(self, ref: FaceRef) -> frozenset[FaceRef]:
        return frozenset(
            self.__by_node[node] for node in self.__graph.smooth_region(self._node(ref))
        )

    def bounds(self, ref: FaceRef):
        return self.__graph.bounds(self._node(ref))

    def normal(self, ref: FaceRef) -> tuple[float, float, float] | None:
        return self.__graph.normal(self._node(ref))

    def surface_fact(self, ref: FaceRef) -> SurfaceFact:
        fact = self.__surfaces.fact(self._node(ref))
        if isinstance(fact, RefusedSurfaceFact):
            return RefusedSurface(SurfaceRefusalReason(fact.reason.value))
        assert isinstance(fact, AnalyticSurfaceFact)
        return AnalyticSurface(
            SurfaceKind(fact.kind.value),
            SurfaceProvenance(fact.provenance.value),
            OrientationCapability(fact.orientation.value),
            fact.parameters,
            fact.requested_tolerance,
            fact.kernel_reported_gap,
        )

    def surface_anchor(self, ref: FaceRef) -> tuple[float, float, float]:
        """Return the midpoint of the trimmed surface parameter domain.

        This is a leader/inspection anchor, not a topological identity.  Keeping
        it here prevents consumers from reopening the raw OCCT surface merely to
        locate a point on the same face whose analytic fact they just queried.
        """

        face = self.face(ref)
        try:
            surface = BRepAdaptor_Surface(face.wrapped)
            u = 0.5 * (surface.FirstUParameter() + surface.LastUParameter())
            v = 0.5 * (surface.FirstVParameter() + surface.LastVParameter())
            point = surface.Value(u, v)
            values = (float(point.X()), float(point.Y()), float(point.Z()))
        except (AttributeError, Standard_Failure, RuntimeError, ValueError) as error:
            raise ValueError("surface anchor is unavailable") from error
        return values

    def blend_facts(self) -> tuple[BlendFact, ...]:
        if self.__blends is None:
            index = BlendCollapseIndex(self.__graph, self.__surfaces)
            self.__blends = index
        facts: list[BlendFact] = []
        for chain in self.__blends.chains():
            ref = self.__blend_refs.setdefault(chain, BlendRef(self.__authority, chain))
            arcs = (*chain.spring_arcs, *chain.internal_arcs, *chain.terminal_arcs)
            left_support, right_support = chain.supports
            boundary = tuple(
                self.__boundary_refs.setdefault(
                    arc.occurrence, BoundaryRef(self.__authority, arc.occurrence)
                )
                for arc in arcs
            )
            facts.append(
                BlendFact(
                    ref,
                    frozenset(self.__by_node[node] for node in chain.blend_nodes),
                    (
                        frozenset(self.__by_node[node] for node in left_support),
                        frozenset(self.__by_node[node] for node in right_support),
                    ),
                    chain.side,
                    chain.radius,
                    boundary,
                )
            )
        return tuple(facts)

    def collapsed_bridges(self, selected: tuple[BlendRef, ...]) -> tuple[CollapsedBridge, ...]:
        if self.__blends is None:
            self.blend_facts()
        assert self.__blends is not None
        chains: list[BlendChain] = []
        for ref in selected:
            if type(ref) is not BlendRef or ref._authority is not self.__authority:
                raise ValueError("blend reference is foreign to this geometry graph")
            chain = cast(BlendChain, ref._chain)
            if self.__blend_refs.get(chain) is not ref:
                raise ValueError("blend reference is copied, changed, or stale")
            chains.append(chain)
        index = self.__blends
        view = index.view(chains)
        logical_by_source = {
            next(iter(sources)): logical
            for logical in view.logical_nodes()
            if len(sources := view.expand_node(logical)) == 1
        }
        result: list[CollapsedBridge] = []
        for chain in chains:
            left = next(iter(chain.supports[0]))
            right = next(iter(chain.supports[1]))
            for arc in view.arcs_between(logical_by_source[left], logical_by_source[right]):
                if not arc.synthetic:
                    continue
                provenance = view.expand_arc(arc)
                result.append(
                    CollapsedBridge(
                        (self.__by_node[left], self.__by_node[right]),
                        arc.kind,
                        GeometryProvenance(
                            frozenset(self.__by_node[node] for node in provenance.nodes),
                            tuple(
                                self.__boundary_refs.setdefault(
                                    item.occurrence,
                                    BoundaryRef(self.__authority, item.occurrence),
                                )
                                for item in provenance.arcs
                            ),
                        ),
                    )
                )
        return tuple(result)


__all__ = [
    "AnalyticSurface",
    "BlendFact",
    "BlendRef",
    "BoundaryRef",
    "CollapsedBridge",
    "FaceRef",
    "GeometryGraph",
    "GeometryProvenance",
    "OrientationCapability",
    "RefusedSurface",
    "SurfaceFact",
    "SurfaceKind",
    "SurfaceProvenance",
    "SurfaceRefusalReason",
]
