# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Complete cylindrical rolling-ball blend-chain recognition.

A :class:`Blend` is neutral geometry rather than a dimensioning policy: one connected,
same-solid chain of native cylindrical patches with one radius, one material side and exactly
two complete support regions.  Convex and concave chains are both reported.  The narrower
:class:`~b123d_recognisers.fillets.Fillet` family remains the dimension-worthy external edge
treatment; aggregate reconciliation prefers that family, or a CircularBlindStep, when either
describes the same curved faces.

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
from b123d_recognisers._effective_surfaces import AnalyticSurfaceFact, EffectiveSurfaceIndex
from b123d_recognisers._geometry import _canonical_axis_direction
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part


@dataclass(frozen=True)
class Blend(Record):
    """One complete cylindrical rolling-ball chain.

    ``side`` is ``"convex"`` for an external round and ``"concave"`` for an internal round.
    ``axis`` names the dominant component of the canonical unit ``axis_direction``. ``at`` is a
    subdivision-invariant leader point on the chain's common analytic cylinder.
    """

    axis: str
    radius: float
    at: tuple[float, float, float]
    side: str
    axis_direction: tuple[float, float, float]

    def __post_init__(self) -> None:
        if self.side not in {"convex", "concave"}:
            raise ValueError("blend side must be convex or concave")
        object.__setattr__(
            self,
            "axis_direction",
            _canonical_axis_direction(self.axis, self.axis_direction),
        )


@dataclass(frozen=True, slots=True)
class _BlendProposal:
    record: Blend
    nodes: tuple[FaceNode, ...]


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
