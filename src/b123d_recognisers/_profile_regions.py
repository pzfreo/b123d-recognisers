# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Neutral local-region geometry for analytic open-profile recognisers.

This module derives attributed planar/cylindrical regions and their actual boundaries. It does
not decide whether a region is a slot or step; family policy remains in the public recognisers.
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import Face, GeomType, Solid, Vector, Wire
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder

from b123d_recognisers._adjacency import FaceGraph, FaceNode, axis_aligned_axis
from b123d_recognisers._geometry import (
    AXIS_ALIGNED_COS,
    AXIS_ZERO_COS,
    COORD_FLOOR,
    SMOOTH_ARC_GAP,
    SPAN_EPS,
)
from b123d_recognisers._typing import EdgeLike

AXES = "xyz"


@dataclass(frozen=True)
class CylinderRegion:
    nodes: frozenset[FaceNode]
    radius: float
    axis: int
    centre: tuple[float, float, float]


def cylinder_surface(
    graph: FaceGraph, node: FaceNode
) -> tuple[float, int, tuple[float, float, float]] | None:
    surface = BRepAdaptor_Surface(graph.face(node).wrapped)
    if surface.GetType() != GeomAbs_Cylinder:
        return None
    cylinder = surface.Cylinder()
    direction = cylinder.Axis().Direction()
    components = (direction.X(), direction.Y(), direction.Z())
    aligned = [
        axis
        for axis, value in enumerate(components)
        if abs(value) >= AXIS_ALIGNED_COS
        and all(abs(other) <= AXIS_ZERO_COS for i, other in enumerate(components) if i != axis)
    ]
    if len(aligned) != 1:
        return None
    location = cylinder.Axis().Location()
    return (
        float(cylinder.Radius()),
        aligned[0],
        (float(location.X()), float(location.Y()), float(location.Z())),
    )


def _same_cylinder(
    left: tuple[float, int, tuple[float, float, float]],
    right: tuple[float, int, tuple[float, float, float]],
) -> bool:
    radius, axis, centre = left
    other_radius, other_axis, other_centre = right
    return (
        axis == other_axis
        and abs(radius - other_radius) <= SPAN_EPS
        and all(abs(centre[i] - other_centre[i]) <= SPAN_EPS for i in range(3) if i != axis)
    )


def cylinder_region(graph: FaceGraph, seed: FaceNode) -> CylinderRegion | None:
    surface = cylinder_surface(graph, seed)
    if surface is None:
        return None
    found = {seed}
    pending = [seed]
    while pending:
        current = pending.pop()
        for neighbour in graph.neighbours(current):
            candidate = cylinder_surface(graph, neighbour)
            if (
                neighbour in found
                or candidate is None
                or not _same_cylinder(surface, candidate)
                or graph.arc(current, neighbour) != "smooth"
            ):
                continue
            found.add(neighbour)
            pending.append(neighbour)
    radius, axis, centre = surface
    return CylinderRegion(frozenset(found), radius, axis, centre)


def region_boundary_wire(
    graph: FaceGraph, nodes: frozenset[FaceNode], *, planar: bool = True
) -> Wire | None:
    if not nodes or any(not graph.face(node).is_valid for node in nodes):
        return None
    uses: dict[EdgeLike, int] = {}
    for node in nodes:
        for edge in graph.edges(node):
            uses[edge] = uses.get(edge, 0) + 1
    if any(count > 2 for count in uses.values()):
        return None
    boundary = [edge for edge, count in uses.items() if count == 1]
    wires = list(Wire.combine(boundary, tol=COORD_FLOOR))
    if len(wires) != 1 or not wires[0].is_closed:
        return None
    if not planar:
        return wires[0]
    try:
        face = Face(wires[0])
    except Exception:
        return None
    return wires[0] if face.is_valid else None


def region_face(graph: FaceGraph, nodes: frozenset[FaceNode]) -> Face | None:
    wire = region_boundary_wire(graph, nodes)
    if wire is None:
        return None
    try:
        face = Face(wire)
    except Exception:
        return None
    return face if face.is_valid else None


def relation(
    graph: FaceGraph, left: frozenset[FaceNode], right: frozenset[FaceNode]
) -> str | None:
    kinds = {kind for a in left for b in right if (kind := graph.arc(a, b)) is not None}
    return kinds.pop() if len(kinds) == 1 else None


def shared_region_edges(
    graph: FaceGraph, left: frozenset[FaceNode], right: frozenset[FaceNode]
) -> frozenset[EdgeLike]:
    """Return the actual topological boundary shared by two logical regions."""

    left_edges = {edge for node in left for edge in graph.edges(node)}
    right_edges = {edge for node in right for edge in graph.edges(node)}
    return frozenset(left_edges & right_edges)


def region_bounds(
    graph: FaceGraph, nodes: frozenset[FaceNode]
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    values = tuple(
        (
            min(graph.bounds(node)[axis][0] for node in nodes),
            max(graph.bounds(node)[axis][1] for node in nodes),
        )
        for axis in range(3)
    )
    return values  # type: ignore[return-value]


def principal_rectangle(graph: FaceGraph, nodes: frozenset[FaceNode], normal_axis: int) -> bool:
    """Whether a logical planar region is one valid hole-free principal rectangle."""

    wire = region_boundary_wire(graph, nodes)
    if wire is None:
        return False
    edges = wire.edges()
    if not edges or any(edge.geom_type != GeomType.LINE for edge in edges):
        return False
    directions = [edge.tangent_at() for edge in edges]
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
            if 1.0 - abs(getattr(direction, AXES[axis].upper())) <= SMOOTH_ARC_GAP
        ]
        if len(aligned) != 1:
            return False
        run_axes.append(aligned[0])
    return len(run_axes) == 4 and all(run_axes.count(axis) == 2 for axis in in_plane)


def boundary_runs(wire: Wire) -> list[tuple[GeomType, list[EdgeLike]]] | None:
    """Co-directed straight or same-directed-support-circle runs around one boundary."""

    edges = wire.edges()
    if not edges or any(edge.geom_type not in (GeomType.LINE, GeomType.CIRCLE) for edge in edges):
        return None
    groups: list[tuple[GeomType, list[EdgeLike]]] = []
    for edge in edges:
        if groups and groups[-1][0] == edge.geom_type:
            kind, members = groups[-1]
            if (
                (
                    kind == GeomType.LINE
                    and 1.0 - members[-1].tangent_at().dot(edge.tangent_at()) > SMOOTH_ARC_GAP
                )
                or kind == GeomType.CIRCLE
                and not _same_directed_circle(members[-1], edge)
            ):
                groups.append((edge.geom_type, [edge]))
            else:
                members.append(edge)
        else:
            groups.append((edge.geom_type, [edge]))
    if len(groups) > 1 and groups[0][0] == groups[-1][0]:
        kind, members = groups[0]
        tail = groups[-1][1]
        compatible = (
            kind == GeomType.LINE
            and 1.0 - tail[-1].tangent_at().dot(members[0].tangent_at()) <= SMOOTH_ARC_GAP
        ) or (kind == GeomType.CIRCLE and _same_directed_circle(tail[-1], members[0]))
        if compatible:
            groups[0] = kind, [*groups.pop()[1], *members]
    return groups


def _same_directed_circle(left: EdgeLike, right: EdgeLike) -> bool:
    """Whether consecutive circular edges continue on one oriented support circle."""

    a = left.arc_center
    b = right.arc_center
    return (
        abs(left.radius - right.radius) <= SPAN_EPS
        and all(abs(value) <= SPAN_EPS for value in (a.X - b.X, a.Y - b.Y, a.Z - b.Z))
        and 1.0 - left.tangent_at(1).dot(right.tangent_at(0)) <= SMOOTH_ARC_GAP
    )


def alternating_profile_runs(
    wire: Wire,
) -> tuple[list[list[EdgeLike]], list[list[EdgeLike]]] | None:
    groups = boundary_runs(wire)
    if groups is None or len(groups) != 4 or any(
        groups[index][0] == groups[(index + 1) % 4][0] for index in range(4)
    ):
        return None
    return (
        [members for kind, members in groups if kind == GeomType.LINE],
        [members for kind, members in groups if kind == GeomType.CIRCLE],
    )


def same_span(
    graph: FaceGraph, regions: tuple[frozenset[FaceNode], ...], axis: int
) -> tuple[float, float] | None:
    spans = [region_bounds(graph, region)[axis] for region in regions]
    low, high = spans[0]
    if all(abs(a - low) <= SPAN_EPS and abs(b - high) <= SPAN_EPS for a, b in spans[1:]):
        return low, high
    return None


def common_convex_context(
    graph: FaceGraph,
    sources: tuple[frozenset[FaceNode], ...],
    normal_axis: int,
    station: float,
) -> bool:
    neighbours = {
        source: {node for member in source for node in graph.neighbours(member)}
        for source in sources
    }
    seen: set[FaceNode] = set()
    for seed in sorted(set().union(*neighbours.values()), key=lambda node: node.index):
        if seed in seen:
            continue
        region = graph.coplanar_region(seed)
        seen.update(region)
        plane = axis_aligned_axis(graph.face(seed).wrapped)
        if plane is None or plane[0] != normal_axis or abs(plane[1] - station) > SPAN_EPS:
            continue
        arcs = {
            source: [
                graph.arc(member, node)
                for member in source
                for node in region & set(graph.neighbours(member))
            ]
            for source in sources
        }
        if all(kinds and all(kind == "convex" for kind in kinds) for kinds in arcs.values()):
            return True
    return False


def empty_sweep(cap_face: Face, part, run: int, distance: float) -> bool:
    direction = [0.0, 0.0, 0.0]
    direction[run] = distance
    probe = Solid.extrude(cap_face, Vector(*direction))
    intersection = part.intersect(probe)
    if intersection is None:
        return True
    if hasattr(intersection, "volume"):
        return bool(intersection.volume == 0.0)
    return bool(sum(shape.volume for shape in intersection) == 0.0)
