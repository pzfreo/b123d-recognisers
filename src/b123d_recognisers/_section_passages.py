# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Neutral constant-section planar-wall rings on an arbitrary run direction."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import cast

from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_OUT

from b123d_recognisers._adjacency import FaceGraph, FaceNode, connected_components
from b123d_recognisers._rings import _turn, _within
from b123d_recognisers._sections import LocalFrame, PlanarSection, SectionEnds, SectionVertex
from b123d_recognisers._typing import Part

_DIRECTION_TOL = 2e-8
_INTERVAL_TOL = 1e-6
_VOID_TOL = 1e-6
_END_PROBE = 2e-5

Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class SectionRingProposal:
    frame: LocalFrame
    run_interval: tuple[float, float]
    section: PlanarSection
    ends: SectionEnds
    nodes: tuple[FaceNode, ...]


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _point(value: object) -> Vector3:
    return (float(value.X), float(value.Y), float(value.Z))  # type: ignore[attr-defined]


def _canonical_run(edge: object) -> Vector3 | None:
    try:
        if edge.geom_type.name != "LINE":  # type: ignore[attr-defined]
            return None
        tangent = edge.tangent_at().normalized()  # type: ignore[attr-defined]
        frame = LocalFrame.canonical(_point(tangent), (0.0, 0.0, 0.0))
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        return None
    return frame.run


def _parallel(left: Vector3, right: Vector3) -> bool:
    return abs(abs(_dot(left, right)) - 1.0) <= _DIRECTION_TOL


def _pair_line(
    graph: FaceGraph, left: FaceNode, right: FaceNode, frame: LocalFrame
) -> tuple[float, float, float, float] | None:
    """Return one collinear junction as ``(u, v, t_low, t_high)``."""

    samples: list[tuple[float, float, float]] = []
    for edge in graph.shared_edges(left, right):
        run = _canonical_run(edge)
        if run is None or not _parallel(run, frame.run):
            return None
        try:
            endpoints = (_point(edge.position_at(0.0)), _point(edge.position_at(1.0)))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return None
        samples.extend(
            (_dot(point, frame.u), _dot(point, frame.v), _dot(point, frame.run))
            for point in endpoints
        )
    if not samples:
        return None
    u = sum(item[0] for item in samples) / len(samples)
    v = sum(item[1] for item in samples) / len(samples)
    if any(math.hypot(item[0] - u, item[1] - v) > _INTERVAL_TOL for item in samples):
        return None
    return u, v, min(item[2] for item in samples), max(item[2] for item in samples)


def _face_interval(graph: FaceGraph, node: FaceNode, run: Vector3) -> tuple[float, float] | None:
    try:
        values = tuple(_dot(_point(vertex), run) for vertex in graph.face(node).vertices())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return (min(values), max(values)) if values else None


def _world(frame: LocalFrame, t: float, point: tuple[float, float]) -> Vector3:
    return tuple(
        frame.origin[index]
        + t * frame.run[index]
        + point[0] * frame.u[index]
        + point[1] * frame.v[index]
        for index in range(3)
    )  # type: ignore[return-value]


def _outside(part: Part, point: Vector3) -> bool:
    classifier = BRepClass3d_SolidClassifier(part.wrapped)
    classifier.Perform(gp_Pnt(*point), _VOID_TOL)
    return bool(classifier.State() == TopAbs_OUT)


def _void_and_open(
    part: Part,
    frame: LocalFrame,
    interval: tuple[float, float],
    section: PlanarSection,
) -> bool:
    polygon = tuple(vertex.point for vertex in section.boundary)
    probes = _triangle_probes(polygon)
    if not probes:
        return False
    middle = 0.5 * (interval[0] + interval[1])
    if not all(_outside(part, _world(frame, middle, point)) for point in probes):
        return False
    scale = max(1.0, interval[1] - interval[0])
    radius = max(math.hypot(*vertex.point) for vertex in section.boundary)
    deltas = (max(_END_PROBE, scale * 1e-4), max(_END_PROBE, 0.5 * radius))
    return all(
        _outside(part, _world(frame, end + sign * delta, point))
        for end, sign in ((interval[0], -1.0), (interval[1], 1.0))
        for delta in deltas
        for point in probes
    )


def _triangle_probes(
    polygon: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    """One interior point per ear in a deterministic triangulation."""

    remaining = list(range(len(polygon)))
    probes: list[tuple[float, float]] = []

    def add_triangle(
        a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
    ) -> None:
        for weights in ((1 / 3, 1 / 3, 1 / 3), (0.6, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.6)):
            probes.append(
                (
                    weights[0] * a[0] + weights[1] * b[0] + weights[2] * c[0],
                    weights[0] * a[1] + weights[1] * b[1] + weights[2] * c[1],
                )
            )

    while len(remaining) > 3:
        removed = False
        for offset, current in enumerate(remaining):
            before = remaining[offset - 1]
            after = remaining[(offset + 1) % len(remaining)]
            a, b, c = polygon[before], polygon[current], polygon[after]
            if _turn(a, b, c) <= _VOID_TOL:
                continue
            if any(
                _within(polygon[other], a, b, c)
                for other in remaining
                if other not in {before, current, after}
            ):
                continue
            add_triangle(a, b, c)
            remaining.pop(offset)
            removed = True
            break
        if not removed:
            return ()
    a, b, c = (polygon[index] for index in remaining)
    add_triangle(a, b, c)
    return tuple(probes)


def _ordered_cycle(
    graph: FaceGraph, members: tuple[FaceNode, ...], adjacency: dict[FaceNode, set[FaceNode]]
) -> tuple[FaceNode, ...]:
    start = min(members, key=lambda node: node.index)
    first = min(adjacency[start], key=lambda node: node.index)
    order = [start, first]
    while len(order) < len(members):
        choices = adjacency[order[-1]] - {order[-2]}
        order.append(next(iter(choices)))
    return tuple(order)


def section_ring_proposals(part: Part, graph: FaceGraph) -> tuple[SectionRingProposal, ...]:
    """Return every supported line-walled, constant-section, two-open-end void."""

    for face in part.faces():
        graph.require_node(face)
    planar = tuple(node for node in graph.nodes if graph.is_planar(node))
    directions: dict[tuple[float, float, float], Vector3] = {}
    for left in planar:
        for right in graph.neighbours(left):
            if right not in planar or right.index <= left.index:
                continue
            for edge in graph.shared_edges(left, right):
                run = _canonical_run(edge)
                if run is not None:
                    key = cast(Vector3, tuple(round(value, 9) for value in run))
                    directions[key] = run

    proposals: list[SectionRingProposal] = []
    seen: set[tuple[int, ...]] = set()
    for run in directions.values():
        base = LocalFrame.canonical(run, (0.0, 0.0, 0.0))
        walls = tuple(
            node
            for node in planar
            if (normal := graph.normal(node)) is not None
            and abs(_dot(normal, base.run)) <= _DIRECTION_TOL
        )
        pair_lines: dict[frozenset[FaceNode], tuple[float, float, float, float]] = {}
        adjacency: dict[FaceNode, set[FaceNode]] = defaultdict(set)
        for left in walls:
            for right in graph.neighbours(left):
                if right not in walls or right.index <= left.index:
                    continue
                line = _pair_line(graph, left, right, base)
                if line is None:
                    continue
                left_span = _face_interval(graph, left, base.run)
                right_span = _face_interval(graph, right, base.run)
                if left_span is None or right_span is None or any(
                    abs(actual - expected) > _INTERVAL_TOL
                    for actual, expected in zip(
                        (*left_span, *right_span),
                        (line[2], line[3], line[2], line[3]),
                        strict=True,
                    )
                ):
                    continue
                pair_lines[frozenset((left, right))] = line
                adjacency[left].add(right)
                adjacency[right].add(left)

        def connected(
            left: FaceNode,
            right: FaceNode,
            adjacency: dict[FaceNode, set[FaceNode]] = adjacency,
        ) -> bool:
            return right in adjacency[left]

        for component in connected_components(walls, connected):
            members = set(component)
            if len(component) < 3 or any(len(adjacency[node] & members) != 2 for node in component):
                continue
            identity = tuple(sorted(node.index for node in component))
            if identity in seen or graph.common_valid_solid(component) is None:
                continue
            order = _ordered_cycle(graph, component, adjacency)
            lines = tuple(
                pair_lines[frozenset((node, order[(at + 1) % len(order)]))]
                for at, node in enumerate(order)
            )
            low, high = lines[0][2], lines[0][3]
            spans = tuple(_face_interval(graph, node, base.run) for node in order)
            if any(span is None for span in spans):
                continue
            complete_spans = cast(tuple[tuple[float, float], ...], spans)
            low, high = complete_spans[0]
            if any(
                abs(span[0] - low) > _INTERVAL_TOL or abs(span[1] - high) > _INTERVAL_TOL
                for span in complete_spans
            ):
                continue
            try:
                raw = PlanarSection(tuple(SectionVertex((line[0], line[1])) for line in lines))
                centre = raw.centroid
                frame = LocalFrame.canonical(
                    base.run,
                    tuple(
                        centre[0] * base.u[index] + centre[1] * base.v[index] for index in range(3)
                    ),  # type: ignore[arg-type]
                )
                section = PlanarSection(
                    tuple(
                        SectionVertex(
                            (vertex.point[0] - centre[0], vertex.point[1] - centre[1]),
                            vertex.bulge,
                        )
                        for vertex in raw.boundary
                    )
                )
            except ValueError:
                continue
            if not _void_and_open(part, frame, (low, high), section):
                continue
            seen.add(identity)
            proposals.append(
                SectionRingProposal(frame, (low, high), section, SectionEnds(False, False), order)
            )
    proposals.sort(key=lambda item: (item.frame.run, item.run_interval, item.frame.origin))
    return tuple(proposals)
