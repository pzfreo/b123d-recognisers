# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Conservative recognition of a two-ramp through step cut into a stock side.

This family deliberately starts with the unfragmented, mirror-symmetric case.  Two oblique
planar quadrilaterals meet along the run axis, share one convex exterior opening and one concave
three- or five-sided terminal, and belong to one valid solid. Polygonal pockets have superficially
similar adjacency; the paired cross-section, arc directions and terminal contract discriminate
geometry, while rigid axis permutations deliberately remain equivalent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import GeomType

from b123d_recognisers._adjacency import FaceGraph, FaceNode
from b123d_recognisers._bevel import BevelReject, classify_bevel
from b123d_recognisers._candidates import EvidenceSink, FamilyId
from b123d_recognisers._claims import ClaimLedger, EvidenceWriter
from b123d_recognisers._geometry import AXIS_ALIGNED_COS, SMOOTH_ARC_GAP, length_tol, part_scale
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part

_RUN_DIRECTION_COS = 1.0 - SMOOTH_ARC_GAP


@dataclass(frozen=True, order=True)
class PairedRampStep(Record):
    """One mirror-symmetric, two-sided through step.

    ``axis`` is the principal run direction, ``angle`` is either ramp's acute cross-section
    angle in degrees, ``length`` is the open-to-terminal run, and ``at`` is the midpoint of the
    ramps' shared ridge.  The ridge is an original topological edge and therefore a stable
    geometry anchor rather than an inferred stock coordinate.
    """

    axis: str
    angle: float
    length: float
    at: tuple[float, float, float]


def _axis_terminal(graph: FaceGraph, node: FaceNode, axis: int) -> bool:
    normal = graph.normal(node)
    return normal is not None and abs(normal[axis]) >= AXIS_ALIGNED_COS


def _terminal_coordinate(graph: FaceGraph, node: FaceNode, axis: int) -> float:
    lo, hi = graph.bounds(node)[axis]
    return 0.5 * (lo + hi)


def _is_concave(graph: FaceGraph, left: FaceNode, right: FaceNode) -> bool:
    return graph.arc(left, right) == "concave"


def _is_convex(graph: FaceGraph, left: FaceNode, right: FaceNode) -> bool:
    return graph.arc(left, right) == "convex"


def _candidate(
    graph: FaceGraph,
    left: FaceNode,
    right: FaceNode,
    left_read: tuple,
    right_read: tuple,
) -> tuple[PairedRampStep, FaceNode] | None:
    axis, left_normal, left_span, _left_hi, _left_lo = left_read
    right_axis, right_normal, right_span, _right_hi, _right_lo = right_read
    # No world-axis semantic gate belongs here: the same physical boundary remains the same
    # occurrence under a rigid principal-axis permutation (ADR 0011).
    if right_axis != axis:
        return None
    cross = tuple(index for index in (0, 1, 2) if index != axis)
    opposed = tuple(index for index in cross if left_normal[index] * right_normal[index] < 0.0)
    same = tuple(index for index in cross if left_normal[index] * right_normal[index] > 0.0)
    if len(opposed) != 1 or len(same) != 1:
        return None
    # The first supported domain is a mirror pair.  This is an angular equality tolerance, not
    # a dataset-fitted feature-size threshold (ADR 0008).
    if any(
        abs(abs(left_normal[index]) - abs(right_normal[index])) > SMOOTH_ARC_GAP
        for index in cross
    ):
        return None

    shared = graph.shared_edges(left, right)
    if len(shared) != 1 or shared[0].geom_type != GeomType.LINE:
        return None
    if len(graph.edges(left)) != 4 or len(graph.edges(right)) != 4:
        return None
    try:
        tangent = shared[0].tangent_at()
    except Exception:  # pragma: no cover - defensive imported-kernel boundary
        return None
    if abs((tangent.X, tangent.Y, tangent.Z)[axis]) < _RUN_DIRECTION_COS:
        return None
    if not _is_concave(graph, left, right):
        return None

    common = set(graph.neighbours(left)).intersection(graph.neighbours(right))
    terminals = sorted(
        (node for node in common if _axis_terminal(graph, node, axis)),
        key=lambda node: node.index,
    )
    if len(terminals) != 2:
        return None
    solid = graph.common_valid_solid((left, right, *terminals))
    if solid is None:
        return None
    bounds = graph.solid_shape(solid).bounding_box()
    solid_axis = (
        (bounds.min.X, bounds.max.X),
        (bounds.min.Y, bounds.max.Y),
        (bounds.min.Z, bounds.max.Z),
    )[axis]
    scale = part_scale(bounds)
    tolerance = length_tol(scale, rel=1e-9, floor=1e-6)
    solid_extents = (
        bounds.max.X - bounds.min.X,
        bounds.max.Y - bounds.min.Y,
        bounds.max.Z - bounds.min.Z,
    )
    # A through cut opening along the stock's unique thickness direction is a top-opening
    # triangular pocket, not a side step.  Using the solid extents (rather than world Z) keeps
    # this boundary invariant under principal-axis permutations while preserving the explicit
    # exclusion in the family contract.
    if solid_extents[axis] < min(
        solid_extents[index] for index in (0, 1, 2) if index != axis
    ) - tolerance:
        return None
    exterior = [
        node
        for node in terminals
        if min(
            abs(_terminal_coordinate(graph, node, axis) - solid_axis[0]),
            abs(_terminal_coordinate(graph, node, axis) - solid_axis[1]),
        )
        <= tolerance
    ]
    internal = [node for node in terminals if node not in exterior]
    if len(exterior) != 1 or len(internal) != 1:
        return None
    if not (
        _is_convex(graph, left, exterior[0])
        and _is_convex(graph, right, exterior[0])
    ):
        return None
    if not (
        _is_concave(graph, left, internal[0])
        and _is_concave(graph, right, internal[0])
    ):
        return None
    # One original planar terminal with exact concave arcs to both ramps is the authority. Its
    # remaining boundary may be subdivided or independently interrupted; edge count is a B-Rep
    # presentation fact and does not weaken the terminal, material, opening or run proofs.

    edge_box = shared[0].bounding_box()
    edge_bounds = (
        (edge_box.min.X, edge_box.max.X),
        (edge_box.min.Y, edge_box.max.Y),
        (edge_box.min.Z, edge_box.max.Z),
    )
    run_tolerance = length_tol(
        max(
            left_span[axis][1] - left_span[axis][0],
            right_span[axis][1] - right_span[axis][0],
        ),
        rel=1e-9,
        floor=1e-6,
    )
    shared_run = edge_bounds[axis]
    if any(
        abs(face_run[end] - shared_run[end]) > run_tolerance
        for face_run in (left_span[axis], right_span[axis])
        for end in (0, 1)
    ):
        return None
    at = (
        round(0.5 * sum(edge_bounds[0]), 3),
        round(0.5 * sum(edge_bounds[1]), 3),
        round(0.5 * sum(edge_bounds[2]), 3),
    )
    length = shared_run[1] - shared_run[0]
    angle = math.degrees(math.atan2(abs(left_normal[opposed[0]]), abs(left_normal[same[0]])))
    return PairedRampStep("xyz"[axis], round(angle, 2), round(length, 3), at), internal[0]


def recognise_paired_ramp_steps(
    part: Part, *, ledger: ClaimLedger | EvidenceWriter | None = None
) -> list[PairedRampStep]:
    """Return supported paired-ramp through steps in deterministic geometry order."""

    graph = FaceGraph(part) if ledger is None else ledger.graph
    sink: EvidenceSink | None = None if ledger is None else ledger.sink
    bevels: dict[FaceNode, tuple] = {}
    for node in graph.nodes:
        try:
            bevels[node] = classify_bevel(graph.face(node))
        except BevelReject:
            continue

    found: list[tuple[PairedRampStep, FaceNode, FaceNode, FaceNode]] = []
    for left in graph.nodes:
        left_read = bevels.get(left)
        if left_read is None:
            continue
        for right in graph.neighbours(left):
            if right.index <= left.index or right not in bevels:
                continue
            candidate = _candidate(graph, left, right, left_read, bevels[right])
            if candidate is not None:
                record, terminal = candidate
                found.append((record, left, right, terminal))
    found.sort(key=lambda item: item[0])
    if sink is not None:
        for record, left, right, terminal in found:
            sink.propose(
                FamilyId.PAIRED_RAMP_STEPS,
                record,
                defining=(left, right, terminal),
            )
    return [record for record, _left, _right, _terminal in found]
