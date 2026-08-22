# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Rectangular through steps: one open right-angle cut running across a solid.

The public record deliberately stores an open section rather than a pair of anonymous widths.
That preserves which quadrant was removed and leaves room for a later, separately proved
two-sided or slanted subset.  Discovery in this module is narrower: exactly two rectangular
logical planar regions, joined by one concave run seam and open at both source-solid ends.
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import Face, GeomType, Wire

from b123d_recognisers._adjacency import (
    FaceGraph,
    FaceNode,
    axis_aligned_axis,
)
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._geometry import (
    COORD_FLOOR,
    SMOOTH_ARC_GAP,
    SPAN_EPS,
    prism_is_empty,
)
from b123d_recognisers._record import Record
from b123d_recognisers._typing import EdgeLike, Part

_AXES = "xyz"


@dataclass(frozen=True, order=True)
class ThroughStep(Record):
    """One prismatic open-profile step spanning a source solid.

    ``section`` is the canonical three-point open polyline perpendicular to ``axis``: envelope
    endpoint, concave corner, envelope endpoint.  Its orientation and both leg dimensions are
    therefore explicit rather than inferred from unsigned widths.
    """

    axis: str
    length: float
    at: tuple[float, float, float]
    section: tuple[
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
    ]


@dataclass(frozen=True)
class _Region:
    nodes: tuple[FaceNode, ...]
    normal_axis: int
    coordinate: float
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def _four_principal_runs(wire: Wire, normal_axis: int) -> bool:
    """Whether an ordered loop is exactly two co-directed run pairs on principal axes."""

    edges = wire.edges()
    if any(edge.geom_type != GeomType.LINE for edge in edges):
        return False
    directions = [edge.tangent_at() for edge in edges]
    if not directions:
        return False
    runs = [directions[0]]
    for direction in directions[1:]:
        if 1.0 - runs[-1].dot(direction) > SMOOTH_ARC_GAP:
            runs.append(direction)
    if len(runs) > 1 and 1.0 - runs[-1].dot(runs[0]) <= SMOOTH_ARC_GAP:
        runs.pop()
    in_plane = [axis for axis in range(3) if axis != normal_axis]
    run_axes: list[int] = []
    for direction in runs:
        aligned = [
            axis
            for axis in in_plane
            if 1.0 - abs(getattr(direction, _AXES[axis].upper())) <= SMOOTH_ARC_GAP
        ]
        if len(aligned) != 1:
            return False
        run_axes.append(aligned[0])
    return len(run_axes) == 4 and all(run_axes.count(axis) == 2 for axis in in_plane)


def _rectangular_region(graph: FaceGraph, nodes: frozenset[FaceNode]) -> bool:
    """Whether *nodes* sew to one valid, hole-free principal rectangle."""

    if not nodes or any(not graph.face(node).is_valid for node in nodes):
        return False
    seed = min(nodes, key=lambda node: node.index)
    plane = axis_aligned_axis(graph.face(seed).wrapped)
    if plane is None:
        return False
    if len(nodes) == 1:
        face = graph.face(seed)
        face_wires = face.wires()
        return len(face_wires) == 1 and _four_principal_runs(face.outer_wire(), plane[0])
    uses: dict[EdgeLike, int] = {}
    for node in nodes:
        for edge in graph.edges(node):
            uses[edge] = uses.get(edge, 0) + 1
    if any(count > 2 for count in uses.values()):
        return False
    boundary = [edge for edge, count in uses.items() if count == 1]
    if not boundary:
        return False
    combined_wires = list(Wire.combine(boundary, tol=COORD_FLOOR))
    if len(combined_wires) != 1 or not combined_wires[0].is_closed:
        return False
    try:
        face = Face(combined_wires[0])
    except Exception:
        return False
    if not face.is_valid:
        return False
    return _four_principal_runs(combined_wires[0], plane[0])


def _regions(graph: FaceGraph, solid_nodes: set[FaceNode]) -> list[_Region]:
    """Complete rectangular principal-plane regions, each once."""

    out: list[_Region] = []
    seen: set[FaceNode] = set()
    for seed in sorted(solid_nodes, key=lambda node: node.index):
        if seed in seen:
            continue
        plane = axis_aligned_axis(graph.face(seed).wrapped)
        if plane is None:
            continue
        region = graph.coplanar_region(seed) & solid_nodes
        seen.update(region)
        # The public section describes two uninterrupted rectangular walls. Apply the same
        # actual-boundary proof to singleton and subdivided representations; otherwise an inner
        # wire accepted as one face would be rejected merely by splitting that face into patches.
        if not _rectangular_region(graph, region):
            continue
        axis, coordinate = plane
        measured_bounds = tuple(
            (
                min(graph.bounds(node)[i][0] for node in region),
                max(graph.bounds(node)[i][1] for node in region),
            )
            for i in range(3)
        )
        bounds = (measured_bounds[0], measured_bounds[1], measured_bounds[2])
        out.append(
            _Region(tuple(sorted(region, key=lambda node: node.index)), axis, coordinate, bounds)
        )
    return out


def _relation(graph: FaceGraph, left: _Region, right: _Region) -> str | None:
    """One agreed arc kind between two regions, or None when absent/ambiguous."""

    kinds = {
        kind
        for a in left.nodes
        for b in right.nodes
        if (kind := graph.arc(a, b)) is not None
    }
    return kinds.pop() if len(kinds) == 1 else None


def _shared_run_is_complete(
    graph: FaceGraph, left: _Region, right: _Region, run: int, low: float, high: float
) -> bool:
    shared = [
        edge
        for a in left.nodes
        for b in right.nodes
        for edge in graph.shared_edges(a, b)
    ]
    if not shared or any(edge.geom_type != GeomType.LINE for edge in shared):
        return False
    intervals = []
    for edge in shared:
        bounds = edge.bounding_box()
        intervals_by_axis = (
            (bounds.min.X, bounds.max.X),
            (bounds.min.Y, bounds.max.Y),
            (bounds.min.Z, bounds.max.Z),
        )
        interval = intervals_by_axis[run]
        if any(
            abs(getattr(edge.tangent_at(), _AXES[axis].upper())) > SMOOTH_ARC_GAP
            for axis in range(3)
            if axis != run
        ):
            return False
        intervals.append(interval)
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + SPAN_EPS:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return (
        len(merged) == 1
        and abs(merged[0][0] - low) <= SPAN_EPS
        and abs(merged[0][1] - high) <= SPAN_EPS
    )


def _common_terminal(
    graph: FaceGraph,
    left: _Region,
    right: _Region,
    run: int,
    station: float,
    spans: dict[str, tuple[float, float]],
) -> bool:
    left_neighbours = {n for source in left.nodes for n in graph.neighbours(source)}
    right_neighbours = {n for source in right.nodes for n in graph.neighbours(source)}
    seen: set[FaceNode] = set()
    for seed in sorted(left_neighbours | right_neighbours, key=lambda item: item.index):
        if seed in seen:
            continue
        region = graph.coplanar_region(seed)
        seen.update(region)
        plane = axis_aligned_axis(graph.face(seed).wrapped)
        if plane is None or plane[0] != run or abs(plane[1] - station) > SPAN_EPS:
            continue
        if not (region & left_neighbours and region & right_neighbours):
            continue
        node_bounds = tuple(
            (
                min(graph.bounds(node)[axis][0] for node in region),
                max(graph.bounds(node)[axis][1] for node in region),
            )
            for axis in range(3)
        )
        if any(
            node_bounds[axis][0] > spans[_AXES[axis]][0] + SPAN_EPS
            or node_bounds[axis][1] < spans[_AXES[axis]][1] - SPAN_EPS
            for axis in range(3)
            if axis != run
        ):
            continue
        left_arcs = [
            graph.arc(source, node)
            for source in left.nodes
            for node in region & set(graph.neighbours(source))
        ]
        right_arcs = [
            graph.arc(source, node)
            for source in right.nodes
            for node in region & set(graph.neighbours(source))
        ]
        if left_arcs and right_arcs and all(
            kind == "convex" for kind in (*left_arcs, *right_arcs)
        ):
            return True
    return False


def _section_and_spans(
    left: _Region, right: _Region, run: int, solid_bounds
) -> tuple[tuple[tuple[float, float], ...], dict[str, tuple[float, float]]] | None:
    section_axes = [axis for axis in range(3) if axis != run]
    if {left.normal_axis, right.normal_axis} != set(section_axes):
        return None
    corner = {left.normal_axis: left.coordinate, right.normal_axis: right.coordinate}
    endpoint: dict[int, float] = {}
    for region, varying in ((left, right.normal_axis), (right, left.normal_axis)):
        lo, hi = region.bounds[varying]
        at = corner[varying]
        candidates = [
            value
            for value, envelope in (
                (lo, solid_bounds[varying][0]),
                (hi, solid_bounds[varying][1]),
            )
            if abs(value - envelope) <= SPAN_EPS and abs(value - at) > SPAN_EPS
        ]
        if len(candidates) != 1:
            return None
        endpoint[varying] = candidates[0]
    a, b = section_axes
    points = (
        (corner[a], endpoint[b]) if left.normal_axis == a else (endpoint[a], corner[b]),
        (corner[a], corner[b]),
        (endpoint[a], corner[b]) if right.normal_axis == b else (corner[a], endpoint[b]),
    )
    canonical = min(points, tuple(reversed(points)))
    a_span = tuple(sorted((corner[a], endpoint[a])))
    b_span = tuple(sorted((corner[b], endpoint[b])))
    spans: dict[str, tuple[float, float]] = {
        _AXES[run]: (left.bounds[run][0], left.bounds[run][1]),
        _AXES[a]: (a_span[0], a_span[1]),
        _AXES[b]: (b_span[0], b_span[1]),
    }
    return canonical, spans


def _recognise_one(solid, graph: FaceGraph, ledger: ClaimLedger | None) -> list[ThroughStep]:
    solid_nodes = {graph.require_node(face) for face in solid.faces()}
    regions = _regions(graph, solid_nodes)
    bounds = solid.bounding_box()
    solid_bounds = (
        (bounds.min.X, bounds.max.X),
        (bounds.min.Y, bounds.max.Y),
        (bounds.min.Z, bounds.max.Z),
    )
    out: list[ThroughStep] = []
    claimed: set[frozenset[FaceNode]] = set()
    for index, left in enumerate(regions):
        for right in regions[index + 1 :]:
            if left.normal_axis == right.normal_axis or _relation(graph, left, right) != "concave":
                continue
            run = 3 - left.normal_axis - right.normal_axis
            low, high = left.bounds[run]
            measured = _section_and_spans(left, right, run, solid_bounds)
            if measured is None:
                continue
            section, spans = measured
            if (
                abs(low - right.bounds[run][0]) > SPAN_EPS
                or abs(high - right.bounds[run][1]) > SPAN_EPS
                or abs(low - solid_bounds[run][0]) > SPAN_EPS
                or abs(high - solid_bounds[run][1]) > SPAN_EPS
                or not _shared_run_is_complete(graph, left, right, run, low, high)
                or not _common_terminal(graph, left, right, run, low, spans)
                or not _common_terminal(graph, left, right, run, high, spans)
            ):
                continue
            # A channel/pocket floor has another co-spanning concave wall.  The defining
            # dihedral of a rectangular through step is maximal in that relation.
            if any(
                candidate not in (left, right)
                and abs(candidate.bounds[run][0] - low) <= SPAN_EPS
                and abs(candidate.bounds[run][1] - high) <= SPAN_EPS
                and (
                    _relation(graph, left, candidate) == "concave"
                    or _relation(graph, right, candidate) == "concave"
                )
                for candidate in regions
            ):
                continue
            if not prism_is_empty(spans, solid, inset=COORD_FLOOR):
                continue
            nodes = frozenset((*left.nodes, *right.nodes))
            if nodes in claimed:
                continue
            claimed.add(nodes)
            at = tuple(sum(spans[_AXES[axis]]) / 2 for axis in range(3))
            rounded_section = tuple(
                (round(point[0], 3), round(point[1], 3)) for point in section
            )
            record = ThroughStep(
                _AXES[run],
                round(high - low, 3),
                (round(at[0], 3), round(at[1], 3), round(at[2], 3)),
                (rounded_section[0], rounded_section[1], rounded_section[2]),
            )
            out.append(record)
            if ledger is not None:
                ledger.add_defining(record, nodes)
    return out


def recognise_through_steps(
    part: Part, *, ledger: ClaimLedger | None = None
) -> list[ThroughStep]:
    """Recognise the proven rectangular subset of open-profile through steps."""

    graph = ledger.graph if ledger is not None else FaceGraph(part)
    return sorted(
        record
        for solid in part.solids()
        for record in _recognise_one(solid, graph, ledger)
    )
