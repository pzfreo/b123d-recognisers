# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Exact quarter-sector blind steps at principal solid corners."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi

from build123d import GeomType

from b123d_recognisers._adjacency import FaceGraph, FaceNode, axis_aligned_axis
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._geometry import SMOOTH_ARC_GAP, SPAN_EPS
from b123d_recognisers._profile_regions import (
    AXES,
    CylinderRegion,
    alternating_profile_runs,
    boundary_runs,
    cylinder_region,
    empty_sweep,
    region_boundary_wire,
    region_bounds,
    region_face,
    relation,
    shared_region_edges,
)
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part


@dataclass(frozen=True, order=True)
class CircularBlindStep(Record):
    """One cap-to-envelope swept quarter-disc removal.

    ``section_axes`` are the two global transverse axes in canonical order;
    ``section_signs`` identify the removed quadrant relative to the analytic cylinder axis.
    """

    axis: str
    open_sign: int
    length: float
    section_axes: tuple[str, str]
    section_signs: tuple[int, int]
    radius: float
    at: tuple[float, float, float]


def _quarter_cylinder(
    graph: FaceGraph, cylinder: CylinderRegion, run_span: tuple[float, float]
) -> bool:
    wire = region_boundary_wire(graph, cylinder.nodes, planar=False)
    runs = alternating_profile_runs(wire) if wire is not None else None
    if runs is None:
        return False
    lines, arcs = runs
    length = run_span[1] - run_span[0]
    return (
        len(lines) == 2
        and len(arcs) == 2
        and all(abs(sum(edge.length for edge in run) - length) <= SPAN_EPS for run in lines)
        and all(
            all(abs(edge.radius - cylinder.radius) <= SPAN_EPS for edge in run)
            and abs(sum(edge.length for edge in run) - pi * cylinder.radius / 2) <= SPAN_EPS
            for run in arcs
        )
    )


def _quarter_cap(
    graph: FaceGraph,
    cap: frozenset[FaceNode],
    run: int,
    radius: float,
) -> bool:
    wire = region_boundary_wire(graph, cap)
    groups = boundary_runs(wire) if wire is not None else None
    if groups is None or len(groups) != 3:
        return False
    arcs = [members for kind, members in groups if kind == GeomType.CIRCLE]
    lines = [members for kind, members in groups if kind == GeomType.LINE]
    if len(arcs) != 1 or len(lines) != 2:
        return False
    if any(abs(edge.radius - radius) > SPAN_EPS for edge in arcs[0]) or abs(
        sum(edge.length for edge in arcs[0]) - pi * radius / 2
    ) > SPAN_EPS:
        return False
    axes: list[int] = []
    for line in lines:
        if abs(sum(edge.length for edge in line) - radius) > SPAN_EPS:
            return False
        direction = line[0].tangent_at()
        aligned = [
            axis
            for axis in range(3)
            if axis != run
            and 1.0 - abs(getattr(direction, AXES[axis].upper())) <= SMOOTH_ARC_GAP
        ]
        if len(aligned) != 1:
            return False
        axes.append(aligned[0])
    return len(set(axes)) == 2


def _quadrant(
    graph: FaceGraph, cylinder: CylinderRegion
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    transverse = [axis for axis in range(3) if axis != cylinder.axis]
    axes = (transverse[0], transverse[1])
    bounds = region_bounds(graph, cylinder.nodes)
    signs: list[int] = []
    for axis in axes:
        low, high = bounds[axis]
        centre = cylinder.centre[axis]
        if abs(low - centre) <= SPAN_EPS and abs(high - centre - cylinder.radius) <= SPAN_EPS:
            signs.append(1)
        elif abs(high - centre) <= SPAN_EPS and abs(centre - low - cylinder.radius) <= SPAN_EPS:
            signs.append(-1)
        else:
            return None
    return axes, (signs[0], signs[1])


def _context_region(
    graph: FaceGraph,
    source: frozenset[FaceNode],
    normal_axis: int,
    station: float,
    *,
    source_kind: GeomType,
    source_length: float,
    additionally_touches: frozenset[FaceNode] | None = None,
    additional_kind: GeomType | None = None,
    additional_length: float | None = None,
) -> bool:
    seen: set[FaceNode] = set()
    neighbours = {node for member in source for node in graph.neighbours(member)}
    for seed in sorted(neighbours, key=lambda node: node.index):
        if seed in seen or not graph.is_planar(seed):
            continue
        region = graph.coplanar_region(seed)
        seen.update(region)
        plane = axis_aligned_axis(graph.face(seed).wrapped)
        if plane is None or plane[0] != normal_axis or abs(plane[1] - station) > SPAN_EPS:
            continue
        source_arcs = [
            graph.arc(member, node)
            for member in source
            for node in region & set(graph.neighbours(member))
        ]
        source_edges = shared_region_edges(graph, source, region)
        if (
            not source_arcs
            or any(kind != "convex" for kind in source_arcs)
            or not source_edges
            or any(edge.geom_type != source_kind for edge in source_edges)
            or abs(sum(edge.length for edge in source_edges) - source_length) > SPAN_EPS
        ):
            continue
        if additionally_touches is None:
            return True
        other_arcs = [
            graph.arc(member, node)
            for member in additionally_touches
            for node in region & set(graph.neighbours(member))
        ]
        other_edges = shared_region_edges(graph, additionally_touches, region)
        if (
            other_arcs
            and all(kind == "convex" for kind in other_arcs)
            and additional_kind is not None
            and additional_length is not None
            and other_edges
            and all(edge.geom_type == additional_kind for edge in other_edges)
            and abs(sum(edge.length for edge in other_edges) - additional_length) <= SPAN_EPS
        ):
            return True
    return False


def _recognise_one(
    solid, graph: FaceGraph
) -> list[tuple[CircularBlindStep, frozenset[FaceNode]]]:
    solid_nodes = {graph.require_node(face) for face in solid.faces()}
    box = solid.bounding_box()
    envelope = (
        (box.min.X, box.max.X),
        (box.min.Y, box.max.Y),
        (box.min.Z, box.max.Z),
    )
    out: list[tuple[CircularBlindStep, frozenset[FaceNode]]] = []
    seen_cylinders: set[FaceNode] = set()
    for seed in sorted(solid_nodes, key=lambda node: node.index):
        if seed in seen_cylinders:
            continue
        candidate = cylinder_region(graph, seed)
        if candidate is None:
            continue
        nodes = candidate.nodes & solid_nodes
        seen_cylinders.update(nodes)
        cylinder = replace(candidate, nodes=nodes)
        run = cylinder.axis
        bounds = region_bounds(graph, nodes)
        run_span = bounds[run]
        quadrant = _quadrant(graph, cylinder)
        if quadrant is None or not _quarter_cylinder(graph, cylinder, run_span):
            continue
        cap_regions: set[frozenset[FaceNode]] = set()
        for member in nodes:
            for neighbour in graph.neighbours(member):
                if graph.is_planar(neighbour):
                    region = graph.coplanar_region(neighbour) & solid_nodes
                    plane = axis_aligned_axis(graph.face(neighbour).wrapped)
                    if (
                        plane is not None
                        and plane[0] == run
                        and relation(graph, nodes, region) == "concave"
                    ):
                        cap_regions.add(region)
        if len(cap_regions) != 1:
            continue
        cap = next(iter(cap_regions))
        cap_node = min(cap, key=lambda node: node.index)
        cap_plane = axis_aligned_axis(graph.face(cap_node).wrapped)
        if cap_plane is None or not _quarter_cap(graph, cap, run, cylinder.radius):
            continue
        cap_seam = shared_region_edges(graph, nodes, cap)
        if (
            relation(graph, nodes, cap) != "concave"
            or not cap_seam
            or any(edge.geom_type != GeomType.CIRCLE for edge in cap_seam)
            or any(abs(edge.radius - cylinder.radius) > SPAN_EPS for edge in cap_seam)
            or abs(sum(edge.length for edge in cap_seam) - pi * cylinder.radius / 2) > SPAN_EPS
        ):
            continue
        cap_station = cap_plane[1]
        low, high = run_span
        if abs(cap_station - low) <= SPAN_EPS and abs(high - envelope[run][1]) <= SPAN_EPS:
            open_sign, open_station = 1, high
        elif abs(cap_station - high) <= SPAN_EPS and abs(low - envelope[run][0]) <= SPAN_EPS:
            open_sign, open_station = -1, low
        else:
            continue
        section_axes, section_signs = quadrant
        if any(
            not _context_region(
                graph,
                nodes,
                axis,
                cylinder.centre[axis],
                source_kind=GeomType.LINE,
                source_length=high - low,
                additionally_touches=cap,
                additional_kind=GeomType.LINE,
                additional_length=cylinder.radius,
            )
            for axis in section_axes
        ) or not _context_region(
            graph,
            nodes,
            run,
            open_station,
            source_kind=GeomType.CIRCLE,
            source_length=pi * cylinder.radius / 2,
        ):
            continue
        cap_face = region_face(graph, cap)
        if cap_face is None or not empty_sweep(
            cap_face, solid, run, open_station - cap_station
        ):
            continue
        at = list(cylinder.centre)
        at[run] = (low + high) / 2
        record = CircularBlindStep(
            axis=AXES[run],
            open_sign=open_sign,
            length=round(high - low, 3),
            section_axes=(AXES[section_axes[0]], AXES[section_axes[1]]),
            section_signs=section_signs,
            radius=round(cylinder.radius, 3),
            at=(round(at[0], 3), round(at[1], 3), round(at[2], 3)),
        )
        out.append((record, frozenset((*nodes, *cap))))
    return out


def recognise_circular_blind_steps(
    part: Part, *, ledger: ClaimLedger | None = None
) -> list[CircularBlindStep]:
    """Recognise exact envelope-open quarter-sector blind steps."""

    graph = ledger.graph if ledger is not None else FaceGraph(part)
    found: list[CircularBlindStep] = []
    for solid in part.solids():
        for record, nodes in _recognise_one(solid, graph):
            found.append(record)
            if ledger is not None:
                ledger.add_defining(record, nodes)
    return sorted(found)
