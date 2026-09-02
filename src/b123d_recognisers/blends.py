# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Complete cylindrical rolling-ball blend-chain recognition.

A :class:`Blend` is one connected, same-solid chain of native cylindrical patches with one radius,
one proved material side and exactly two complete support regions. Convex chains describe external
rounds; concave chains describe internal rounds and may coexist with the Pocket, Slot or Step whose
interior contains them. The narrower :class:`~b123d_recognisers.fillets.Fillet` family remains the
dimension-worthy external edge treatment; aggregate reconciliation prefers that family when it
describes a complete convex chain.

The recogniser consumes the immutable :class:`._blend_view.BlendCollapseIndex`.  It never copies
Analysis Situs rules, consults a corpus label, or infers membership after recognition.  Every
original cylindrical patch in the chain is defining evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from b123d_recognisers._adjacency import FaceGraph, FaceNode
from b123d_recognisers._blend_view import BlendChain, BlendCollapseIndex
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import EvidenceWriter
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveSurfaceIndex,
    SurfaceKind,
)
from b123d_recognisers._geometry import SMOOTH_ARC_GAP, _canonical_axis_direction
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part


@dataclass(frozen=True)
class Blend(Record):
    """One complete cylindrical rolling-ball chain.

    ``side`` is the proved material-side relation, ``"convex"`` for an external round or
    ``"concave"`` for an internal round. ``axis`` names the dominant component of the canonical
    unit ``axis_direction``. ``at`` is a subdivision-invariant leader point on the chain's common
    analytic cylinder.
    """

    axis: str
    radius: float
    at: tuple[float, float, float]
    side: str
    axis_direction: tuple[float, float, float]

    def __post_init__(self) -> None:
        if self.side not in ("convex", "concave"):
            raise ValueError("public blend side must be convex or concave")
        object.__setattr__(
            self,
            "axis_direction",
            _canonical_axis_direction(self.axis, self.axis_direction),
        )


@dataclass(frozen=True, slots=True)
class _BlendProposal:
    record: Blend
    nodes: tuple[FaceNode, ...]


def _parallel_planar_supports(
    chain: BlendChain,
    surfaces: EffectiveSurfaceIndex,
) -> bool:
    """Whether both spring supports prove parallel planes rather than an intersecting edge.

    A circular end joining two parallel slot walls is a constant-radius tangent cylinder, but it
    is not a rolling-ball treatment of an edge: the two support surfaces have no edge to round.
    Refuse only when both complete support regions prove this exact case. Curved or unavailable
    support geometry cannot establish the exclusion and remains governed by the complete chain
    contract.
    """

    normals: list[tuple[float, float, float]] = []
    for support in chain.supports:
        spring_nodes = {
            node
            for arc in chain.spring_arcs
            for node in arc.endpoints
            if node in support
        }
        facts = [surfaces.fact(node) for node in spring_nodes]
        if not facts or any(
            not isinstance(fact, AnalyticSurfaceFact) or fact.kind is not SurfaceKind.PLANE
            for fact in facts
        ):
            return False
        support_normals = [
            fact.parameters[:3] for fact in facts if isinstance(fact, AnalyticSurfaceFact)
        ]
        first = (support_normals[0][0], support_normals[0][1], support_normals[0][2])
        if any(
            1.0 - abs(math.fsum(a * b for a, b in zip(first, other, strict=True)))
            > SMOOTH_ARC_GAP
            for other in support_normals[1:]
        ):
            return False
        normals.append(first)
    return (
        1.0 - abs(math.fsum(a * b for a, b in zip(normals[0], normals[1], strict=True)))
        <= SMOOTH_ARC_GAP
    )


def _chain_anchor(
    graph: FaceGraph,
    nodes: tuple[FaceNode, ...],
    parameters: tuple[float, ...],
) -> tuple[float, float, float] | None:
    """Area-centre projected to the common cylinder, invariant to face subdivision."""

    weighted: list[tuple[float, tuple[float, float, float]]] = []
    for node in nodes:
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(graph.face(node).wrapped, props)
        area = float(props.Mass())
        centre = props.CentreOfMass()
        point = (float(centre.X()), float(centre.Y()), float(centre.Z()))
        if not math.isfinite(area) or area <= 0.0 or not all(map(math.isfinite, point)):
            return None
        weighted.append((area, point))
    total = math.fsum(area for area, _point in weighted)
    if not math.isfinite(total) or total <= 0.0:
        return None
    centre = tuple(
        math.fsum(area * point[index] for area, point in weighted) / total
        for index in range(3)
    )
    origin = parameters[:3]
    direction = parameters[3:6]
    radius = parameters[6]
    relative = tuple(centre[index] - origin[index] for index in range(3))
    along = math.fsum(
        relative[index] * direction[index] for index in range(3)
    )
    radial = tuple(
        relative[index] - along * direction[index] for index in range(3)
    )
    radial_norm = math.hypot(*radial)
    if not math.isfinite(radial_norm) or radial_norm <= 0.0:
        return None
    return tuple(
        origin[index]
        + along * direction[index]
        + radius * radial[index] / radial_norm
        for index in range(3)
    )


def _proposal(
    chain: BlendChain,
    graph: FaceGraph,
    surfaces: EffectiveSurfaceIndex,
) -> _BlendProposal | None:
    if chain.side == "concave" and _parallel_planar_supports(chain, surfaces):
        return None
    nodes = tuple(sorted(chain.blend_nodes, key=lambda node: node.index))
    if not nodes:
        return None
    fact = surfaces.fact(nodes[0])
    if not isinstance(fact, AnalyticSurfaceFact) or len(fact.parameters) != 7:
        return None
    direction = fact.parameters[3:6]
    axis_at = max(range(3), key=lambda index: abs(direction[index]))
    axis = "xyz"[axis_at]
    canonical = _canonical_axis_direction(axis, direction)
    anchor = _chain_anchor(graph, nodes, fact.parameters)
    if anchor is None:
        return None
    record = Blend(
        axis=axis,
        radius=round(chain.radius, 3),
        at=(round(anchor[0], 3), round(anchor[1], 3), round(anchor[2], 3)),
        side=chain.side,
        axis_direction=canonical,
    )
    return _BlendProposal(record, nodes)


def recognise_blends(part: Part) -> list[Blend]:
    """Recognise complete native cylindrical blend chains in *part*."""

    return _discover_blends(part)


def _discover_blends(
    part: Part,
    *,
    graph: FaceGraph | None = None,
    surfaces: EffectiveSurfaceIndex | None = None,
    writer: EvidenceWriter | None = None,
) -> list[Blend]:
    """Shared writer-free/writer-enabled Blend discovery core."""

    if graph is None:
        graph = writer.graph if writer is not None else FaceGraph(part)
    if writer is not None and writer.graph is not graph:
        raise ValueError("blend graph and evidence writer belong to different runs")
    surfaces = EffectiveSurfaceIndex(graph) if surfaces is None else surfaces
    if surfaces.run_token is not graph.run_token:
        raise ValueError("blend graph and surface index belong to different runs")
    proposals = [
        proposal
        for chain in BlendCollapseIndex(graph, surfaces).chains()
        if (proposal := _proposal(chain, graph, surfaces)) is not None
    ]
    proposals.sort(
        key=lambda proposal: (
            proposal.record.axis,
            proposal.record.at,
            proposal.record.radius,
            proposal.record.side,
            proposal.record.axis_direction,
        )
    )
    if writer is not None:
        for proposal in proposals:
            if writer.graph.common_valid_solid(proposal.nodes) is None:
                raise ValueError("blend defining faces do not belong to one valid solid")
        for proposal in proposals:
            writer.add_defining(
                proposal.record,
                proposal.nodes,
                family=FamilyId.BLENDS,
            )
    return [proposal.record for proposal in proposals]


__all__ = ["Blend", "recognise_blends"]
