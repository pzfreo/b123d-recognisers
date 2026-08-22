# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Edge-open, round-bottom blind slots with one internal cap.

This is deliberately not the rectangular :class:`Pocket` family.  Its constant section is an
open U: a flat floor joined tangentially to two equal quarter-cylinders, open at a source-solid
depth envelope and swept from a run-envelope mouth to one planar blind cap.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi

from build123d import GeomType
from OCP.GeomAbs import GeomAbs_Cylinder

from b123d_recognisers._adjacency import FaceGraph, FaceNode, axis_aligned_axis
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._geometry import SMOOTH_ARC_GAP, SPAN_EPS
from b123d_recognisers._profile_regions import (
    CylinderRegion as _Cylinder,
)
from b123d_recognisers._profile_regions import (
    alternating_profile_runs as _alternating_profile_runs,
)
from b123d_recognisers._profile_regions import (
    boundary_runs as _boundary_runs,
)
from b123d_recognisers._profile_regions import (
    common_convex_context as _common_convex_context,
)
from b123d_recognisers._profile_regions import (
    cylinder_region as _cylinder_region,
)
from b123d_recognisers._profile_regions import (
    empty_sweep as _empty_sweep,
)
from b123d_recognisers._profile_regions import (
    principal_rectangle as _principal_rectangle,
)
from b123d_recognisers._profile_regions import (
    region_boundary_wire as _region_boundary_wire,
)
from b123d_recognisers._profile_regions import (
    region_bounds as _region_bounds,
)
from b123d_recognisers._profile_regions import (
    region_face as _region_face,
)
from b123d_recognisers._profile_regions import (
    relation as _relation,
)
from b123d_recognisers._profile_regions import (
    same_span as _same_span,
)
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part

_AXES = "xyz"


@dataclass(frozen=True, order=True)
class RoundBottomBlindSlot(Record):
    """One capped, edge-open U-section slot.

    ``axis`` is the penetration/run direction and ``open_sign`` identifies its source-envelope
    mouth. ``flat_width`` and ``radius`` define the section: total opening width is
    ``flat_width + 2 * radius`` and profile depth is ``radius``.
    """

    axis: str
    open_sign: int
    length: float
    width_axis: str
    depth_axis: str
    radius: float
    flat_width: float
    at: tuple[float, float, float]

    @property
    def width(self) -> float:
        return self.flat_width + 2 * self.radius

    @property
    def depth(self) -> float:
        return self.radius


@dataclass(frozen=True, order=True)
class SemicircularBottomBlindSlot(Record):
    """One capped slot with two straight legs and a semicircular bottom."""

    axis: str
    open_sign: int
    length: float
    width_axis: str
    depth_axis: str
    radius: float
    leg_depth: float
    at: tuple[float, float, float]

    @property
    def width(self) -> float:
        return 2 * self.radius

    @property
    def depth(self) -> float:
        return self.leg_depth + self.radius


def _quarter_cylinder(graph: FaceGraph, cylinder: _Cylinder, run_span: tuple[float, float]) -> bool:
    wire = _region_boundary_wire(graph, cylinder.nodes, planar=False)
    runs = _alternating_profile_runs(wire) if wire is not None else None
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


def _half_cylinder(graph: FaceGraph, cylinder: _Cylinder, run_span: tuple[float, float]) -> bool:
    wire = _region_boundary_wire(graph, cylinder.nodes, planar=False)
    runs = _alternating_profile_runs(wire) if wire is not None else None
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
            and abs(sum(edge.length for edge in run) - pi * cylinder.radius) <= SPAN_EPS
            for run in arcs
        )
    )


def _semicircular_cap_matches_profile(
    graph: FaceGraph,
    cap: frozenset[FaceNode],
    radius: float,
    leg_depth: float,
    width_axis: int,
    depth_axis: int,
) -> bool:
    wire = _region_boundary_wire(graph, cap)
    groups = _boundary_runs(wire) if wire is not None else None
    if groups is None or len(groups) != 4:
        return False
    arcs = [members for kind, members in groups if kind == GeomType.CIRCLE]
    lines = [members for kind, members in groups if kind == GeomType.LINE]
    if len(arcs) != 1 or len(lines) != 3:
        return False
    arc = arcs[0]
    if any(abs(edge.radius - radius) > SPAN_EPS for edge in arc):
        return False
    if abs(sum(edge.length for edge in arc) - pi * radius) > SPAN_EPS:
        return False
    lengths: dict[int, list[float]] = {width_axis: [], depth_axis: []}
    for run in lines:
        direction = run[0].tangent_at()
        aligned = [
            axis
            for axis in (width_axis, depth_axis)
            if 1.0 - abs(getattr(direction, _AXES[axis].upper())) <= SMOOTH_ARC_GAP
        ]
        if len(aligned) != 1:
            return False
        lengths[aligned[0]].append(sum(edge.length for edge in run))
    return (
        len(lengths[width_axis]) == 1
        and abs(lengths[width_axis][0] - 2 * radius) <= SPAN_EPS
        and len(lengths[depth_axis]) == 2
        and all(abs(length - leg_depth) <= SPAN_EPS for length in lengths[depth_axis])
    )


def _cap_matches_profile(
    graph: FaceGraph,
    cap: frozenset[FaceNode],
    radius: float,
    flat_width: float,
) -> bool:
    wire = _region_boundary_wire(graph, cap)
    runs = _alternating_profile_runs(wire) if wire is not None else None
    if runs is None:
        return False
    lines, arcs = runs
    expected_width = flat_width + 2 * radius
    return (
        len(arcs) == 2
        and len(lines) == 2
        and all(
            all(abs(edge.radius - radius) <= SPAN_EPS for edge in run)
            and abs(sum(edge.length for edge in run) - pi * radius / 2) <= SPAN_EPS
            for run in arcs
        )
        and abs(min(sum(edge.length for edge in run) for run in lines) - flat_width) <= SPAN_EPS
        and abs(max(sum(edge.length for edge in run) for run in lines) - expected_width) <= SPAN_EPS
    )


def _recognise_one(
    solid, graph: FaceGraph
) -> list[tuple[RoundBottomBlindSlot, frozenset[FaceNode]]]:
    solid_nodes = {graph.require_node(face) for face in solid.faces()}
    bounds = solid.bounding_box()
    envelope = (
        (bounds.min.X, bounds.max.X),
        (bounds.min.Y, bounds.max.Y),
        (bounds.min.Z, bounds.max.Z),
    )
    out: list[tuple[RoundBottomBlindSlot, frozenset[FaceNode]]] = []
    seen_caps: set[FaceNode] = set()
    for cap in sorted(solid_nodes, key=lambda node: node.index):
        if cap in seen_caps:
            continue
        cap_plane = axis_aligned_axis(graph.face(cap).wrapped)
        if cap_plane is None:
            continue
        # Most planar faces are stock or belong to another family. A defining cap must touch at
        # least one of its curved walls concavely; establish that cheap AAG fact before region
        # sewing, repeated cylinder adaptation, or any Boolean work. A split cap still satisfies
        # it on each patch because each half touches one quarter cylinder.
        if not any(
            graph.surface(node) == GeomAbs_Cylinder and graph.arc(cap, node) == "concave"
            for node in graph.neighbours(cap)
        ):
            continue
        cap_region = graph.coplanar_region(cap) & solid_nodes
        seen_caps.update(cap_region)
        if any(axis_aligned_axis(graph.face(node).wrapped) != cap_plane for node in cap_region):
            continue
        run, cap_station = cap_plane
        neighbours = {
            node
            for source in cap_region
            for node in graph.neighbours(source)
            if node not in cap_region
        }
        cylinder_by_nodes: dict[frozenset[FaceNode], _Cylinder] = {}
        planar_regions: set[frozenset[FaceNode]] = set()
        for node in neighbours:
            cylinder = _cylinder_region(graph, node)
            if cylinder is not None:
                nodes = cylinder.nodes & solid_nodes
                cylinder_by_nodes[nodes] = replace(cylinder, nodes=nodes)
            elif graph.is_planar(node):
                planar_regions.add(graph.coplanar_region(node) & solid_nodes)
        cylinders = tuple(
            cylinder
            for nodes, cylinder in cylinder_by_nodes.items()
            if _relation(graph, cap_region, nodes) == "concave"
        )
        planar = tuple(
            region for region in planar_regions if _relation(graph, cap_region, region) == "concave"
        )
        if len(cylinders) != 2 or len(planar) != 1:
            continue
        left, right = cylinders
        floor_region = planar[0]
        floor = min(floor_region, key=lambda node: node.index)
        floor_plane = axis_aligned_axis(graph.face(floor).wrapped)
        if (
            left.axis != run
            or right.axis != run
            or floor_plane is None
            or floor_plane[0] == run
            or not _principal_rectangle(graph, floor_region, floor_plane[0])
            or abs(left.radius - right.radius) > SPAN_EPS
            or _relation(graph, left.nodes, floor_region) != "smooth"
            or _relation(graph, right.nodes, floor_region) != "smooth"
        ):
            continue
        depth = floor_plane[0]
        width = 3 - run - depth
        side_regions = (left.nodes, floor_region, right.nodes)
        side_nodes = tuple(node for region in side_regions for node in region)
        run_span = _same_span(graph, side_regions, run)
        if run_span is None or not all(
            _quarter_cylinder(graph, cylinder, run_span) for cylinder in (left, right)
        ):
            continue
        low, high = run_span
        if abs(cap_station - low) <= SPAN_EPS and abs(high - envelope[run][1]) <= SPAN_EPS:
            open_sign, open_station = 1, high
        elif abs(cap_station - high) <= SPAN_EPS and abs(low - envelope[run][0]) <= SPAN_EPS:
            open_sign, open_station = -1, low
        else:
            continue
        floor_bounds = _region_bounds(graph, floor_region)
        flat_width = floor_bounds[width][1] - floor_bounds[width][0]
        radius = (left.radius + right.radius) / 2
        side_bounds = [_region_bounds(graph, left.nodes), _region_bounds(graph, right.nodes)]
        profile_low = min(item[width][0] for item in side_bounds)
        profile_high = max(item[width][1] for item in side_bounds)
        depth_low = min(item[depth][0] for item in side_bounds)
        depth_high = max(item[depth][1] for item in side_bounds)
        floor_coord = floor_plane[1]
        depth_open = depth_high if abs(depth_low - floor_coord) <= SPAN_EPS else depth_low
        if (
            flat_width <= 0
            or abs((profile_high - profile_low) - (flat_width + 2 * radius)) > SPAN_EPS
            or abs(abs(depth_open - floor_coord) - radius) > SPAN_EPS
            or not any(abs(depth_open - end) <= SPAN_EPS for end in envelope[depth])
            or not _cap_matches_profile(graph, cap_region, radius, flat_width)
            or not _common_convex_context(graph, side_regions, run, open_station)
            or not _common_convex_context(
                graph,
                (left.nodes, cap_region, right.nodes),
                depth,
                depth_open,
            )
        ):
            continue
        cap_face = _region_face(graph, cap_region)
        if cap_face is None or not _empty_sweep(cap_face, solid, run, open_station - cap_station):
            continue
        centre = [0.0, 0.0, 0.0]
        centre[run] = (low + high) / 2
        centre[width] = (profile_low + profile_high) / 2
        centre[depth] = (floor_coord + depth_open) / 2
        record = RoundBottomBlindSlot(
            axis=_AXES[run],
            open_sign=open_sign,
            length=round(high - low, 3),
            width_axis=_AXES[width],
            depth_axis=_AXES[depth],
            radius=round(radius, 3),
            flat_width=round(flat_width, 3),
            at=(round(centre[0], 3), round(centre[1], 3), round(centre[2], 3)),
        )
        out.append((record, frozenset((*side_nodes, *cap_region))))
    return out


def _recognise_semicircular_one(
    solid, graph: FaceGraph
) -> list[tuple[SemicircularBottomBlindSlot, frozenset[FaceNode]]]:
    """Recognise the sharp two-leg plus half-cylinder profile in one source solid."""

    solid_nodes = {graph.require_node(face) for face in solid.faces()}
    bounds = solid.bounding_box()
    envelope = (
        (bounds.min.X, bounds.max.X),
        (bounds.min.Y, bounds.max.Y),
        (bounds.min.Z, bounds.max.Z),
    )
    out: list[tuple[SemicircularBottomBlindSlot, frozenset[FaceNode]]] = []
    seen_caps: set[FaceNode] = set()
    for cap in sorted(solid_nodes, key=lambda node: node.index):
        if cap in seen_caps:
            continue
        cap_plane = axis_aligned_axis(graph.face(cap).wrapped)
        if cap_plane is None or not any(
            graph.surface(node) == GeomAbs_Cylinder and graph.arc(cap, node) == "concave"
            for node in graph.neighbours(cap)
        ):
            continue
        cap_region = graph.coplanar_region(cap) & solid_nodes
        seen_caps.update(cap_region)
        if any(axis_aligned_axis(graph.face(node).wrapped) != cap_plane for node in cap_region):
            continue
        run, cap_station = cap_plane
        neighbours = {
            node
            for source in cap_region
            for node in graph.neighbours(source)
            if node not in cap_region
        }
        cylinder_by_nodes: dict[frozenset[FaceNode], _Cylinder] = {}
        planar_regions: set[frozenset[FaceNode]] = set()
        for node in neighbours:
            cylinder = _cylinder_region(graph, node)
            if cylinder is not None:
                nodes = cylinder.nodes & solid_nodes
                cylinder_by_nodes[nodes] = replace(cylinder, nodes=nodes)
            elif graph.is_planar(node):
                planar_regions.add(graph.coplanar_region(node) & solid_nodes)
        cylinders = tuple(
            cylinder
            for nodes, cylinder in cylinder_by_nodes.items()
            if _relation(graph, cap_region, nodes) == "concave"
        )
        legs = tuple(
            region for region in planar_regions if _relation(graph, cap_region, region) == "concave"
        )
        if len(cylinders) != 1 or len(legs) != 2:
            continue
        cylinder = cylinders[0]
        leg_planes = [
            axis_aligned_axis(graph.face(min(region, key=lambda node: node.index)).wrapped)
            for region in legs
        ]
        if (
            cylinder.axis != run
            or any(plane is None for plane in leg_planes)
            or leg_planes[0][0] != leg_planes[1][0]  # type: ignore[index]
            or leg_planes[0][0] == run  # type: ignore[index]
        ):
            continue
        width = leg_planes[0][0]  # type: ignore[index]
        depth = 3 - run - width
        if any(
            not _principal_rectangle(graph, region, width)
            or _relation(graph, cylinder.nodes, region) != "smooth"
            for region in legs
        ):
            continue
        side_regions = (legs[0], cylinder.nodes, legs[1])
        run_span = _same_span(graph, side_regions, run)
        if run_span is None or not _half_cylinder(graph, cylinder, run_span):
            continue
        low, high = run_span
        if abs(cap_station - low) <= SPAN_EPS and abs(high - envelope[run][1]) <= SPAN_EPS:
            open_sign, open_station = 1, high
        elif abs(cap_station - high) <= SPAN_EPS and abs(low - envelope[run][0]) <= SPAN_EPS:
            open_sign, open_station = -1, low
        else:
            continue
        radius = cylinder.radius
        leg_stations = sorted(plane[1] for plane in leg_planes if plane is not None)
        leg_bounds = [_region_bounds(graph, region) for region in legs]
        cylinder_bounds = _region_bounds(graph, cylinder.nodes)
        if (
            abs((leg_stations[1] - leg_stations[0]) - 2 * radius) > SPAN_EPS
            or abs((cylinder_bounds[width][1] - cylinder_bounds[width][0]) - 2 * radius)
            > SPAN_EPS
            or abs((cylinder_bounds[depth][1] - cylinder_bounds[depth][0]) - radius) > SPAN_EPS
        ):
            continue
        depth_intervals = [item[depth] for item in leg_bounds]
        if any(
            abs(interval[index] - depth_intervals[0][index]) > SPAN_EPS
            for interval in depth_intervals[1:]
            for index in (0, 1)
        ):
            continue
        tangent_candidates = [
            station
            for station in depth_intervals[0]
            if any(abs(station - end) <= SPAN_EPS for end in cylinder_bounds[depth])
        ]
        if len(tangent_candidates) != 1:
            continue
        tangent = tangent_candidates[0]
        depth_open = (
            depth_intervals[0][1]
            if abs(tangent - depth_intervals[0][0]) <= SPAN_EPS
            else depth_intervals[0][0]
        )
        leg_depth = abs(depth_open - tangent)
        if (
            leg_depth <= 0
            or not any(abs(depth_open - end) <= SPAN_EPS for end in envelope[depth])
            or not _semicircular_cap_matches_profile(
                graph, cap_region, radius, leg_depth, width, depth
            )
            or not _common_convex_context(graph, side_regions, run, open_station)
            or not _common_convex_context(graph, (legs[0], cap_region, legs[1]), depth, depth_open)
        ):
            continue
        cap_face = _region_face(graph, cap_region)
        if cap_face is None or not _empty_sweep(cap_face, solid, run, open_station - cap_station):
            continue
        centre = [0.0, 0.0, 0.0]
        centre[run] = (low + high) / 2
        centre[width] = (leg_stations[0] + leg_stations[1]) / 2
        profile_bottom = (
            cylinder_bounds[depth][0]
            if abs(tangent - cylinder_bounds[depth][1]) <= SPAN_EPS
            else cylinder_bounds[depth][1]
        )
        centre[depth] = (profile_bottom + depth_open) / 2
        record = SemicircularBottomBlindSlot(
            axis=_AXES[run],
            open_sign=open_sign,
            length=round(high - low, 3),
            width_axis=_AXES[width],
            depth_axis=_AXES[depth],
            radius=round(radius, 3),
            leg_depth=round(leg_depth, 3),
            at=(round(centre[0], 3), round(centre[1], 3), round(centre[2], 3)),
        )
        defining = frozenset((*legs[0], *cylinder.nodes, *legs[1], *cap_region))
        out.append((record, defining))
    return out


def recognise_round_bottom_blind_slots(
    part: Part, *, ledger: ClaimLedger | None = None
) -> list[RoundBottomBlindSlot]:
    """Recognise the exact analytic U-section, one-cap subset described by the record."""

    graph = ledger.graph if ledger is not None else FaceGraph(part)
    solids = list(part.solids())
    found: list[RoundBottomBlindSlot] = []
    for solid in solids:
        for record, nodes in _recognise_one(solid, graph):
            found.append(record)
            if ledger is not None:
                ledger.add_defining(record, nodes)
    return sorted(found)


def recognise_semicircular_bottom_blind_slots(
    part: Part, *, ledger: ClaimLedger | None = None
) -> list[SemicircularBottomBlindSlot]:
    """Recognise the exact two-leg, half-cylinder, one-cap supported subset."""

    graph = ledger.graph if ledger is not None else FaceGraph(part)
    found: list[SemicircularBottomBlindSlot] = []
    for solid in part.solids():
        for record, nodes in _recognise_semicircular_one(solid, graph):
            found.append(record)
            if ledger is not None:
                ledger.add_defining(record, nodes)
    return sorted(found)
