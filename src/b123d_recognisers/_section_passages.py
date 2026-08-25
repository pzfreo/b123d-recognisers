# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Neutral constant-section planar-wall rings on an arbitrary run direction."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import cast

from build123d import Face, Solid, Vector, Wire
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_OUT

from b123d_recognisers._adjacency import FaceGraph, FaceNode, SolidRef, connected_components
from b123d_recognisers._rings import _turn, _within
from b123d_recognisers._sections import (
    BodyRef,
    BodyRefIssuer,
    LocalFrame,
    PlanarSection,
    SectionEnds,
    SectionOccurrence,
    SectionVertex,
    validate_occurrence,
)
from b123d_recognisers._typing import Part

_DIRECTION_TOL = 2e-8
_INTERVAL_TOL = 1e-6
_VOID_TOL = 1e-6
_END_PROBE = 2e-5
_COORD_FLOOR = 1e-6
_MATERIAL_VOL_FRAC = 1e-9

Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class SectionRingProposal:
    occurrence: SectionOccurrence
    nodes: tuple[FaceNode, ...]
    solid: SolidRef
    body_adapter: _BodyAdapter

    @property
    def frame(self) -> LocalFrame:
        return self.occurrence.frame

    @property
    def run_interval(self) -> tuple[float, float]:
        return self.occurrence.run_interval

    @property
    def section(self) -> PlanarSection:
        return self.occurrence.section

    @property
    def ends(self) -> SectionEnds:
        return self.occurrence.ends


class _BodyAdapter:
    """One-to-one bridge between graph and neutral section body authorities."""

    def __init__(self) -> None:
        self._issuer = BodyRefIssuer()
        self._pairs: dict[SolidRef, BodyRef] = {}

    def body(self, solid: SolidRef) -> BodyRef:
        current = self._pairs.get(solid)
        if current is None:
            current = self._issuer.issue()
            self._pairs[solid] = current
        return current

    def validate(self, solid: SolidRef, occurrence: SectionOccurrence) -> None:
        if self._pairs.get(solid) is not occurrence.body:
            raise ValueError("section occurrence body does not match its graph solid")
        validate_occurrence(occurrence, body_refs=self._issuer)


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
    segments: list[tuple[float, float]] = []
    for edge in graph.shared_edges(left, right):
        run = _canonical_run(edge)
        if run is None or not _parallel(run, frame.run):
            return None
        try:
            endpoints = (_point(edge.position_at(0.0)), _point(edge.position_at(1.0)))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return None
        projected = tuple(
            (_dot(point, frame.u), _dot(point, frame.v), _dot(point, frame.run))
            for point in endpoints
        )
        samples.extend(projected)
        segments.append(tuple(sorted((projected[0][2], projected[1][2]))))  # type: ignore[arg-type]
    if not samples:
        return None
    u = sum(item[0] for item in samples) / len(samples)
    v = sum(item[1] for item in samples) / len(samples)
    if any(math.hypot(item[0] - u, item[1] - v) > _INTERVAL_TOL for item in samples):
        return None
    ordered = sorted(segments)
    for previous, following in zip(ordered, ordered[1:], strict=False):
        delta = following[0] - previous[1]
        if delta > _INTERVAL_TOL or delta < -_INTERVAL_TOL:
            return None
    return u, v, ordered[0][0], ordered[-1][1]


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


def _probe_prism(
    frame: LocalFrame,
    interval: tuple[float, float],
    section: PlanarSection,
) -> Solid:
    low, high = interval
    if high - low <= 2 * _COORD_FLOOR:
        raise ValueError("section prism is too short to classify")
    points = tuple(
        Vector(*_world(frame, low + _COORD_FLOOR, vertex.point)) for vertex in section.boundary
    )
    wire = Wire.make_polygon((*points, points[0]))
    vector = Vector(*(component * (high - low - 2 * _COORD_FLOOR) for component in frame.run))
    return Solid.extrude(Face(wire), vector)


def _end_slab(
    frame: LocalFrame,
    end: float,
    sign: float,
    thickness: float,
    section: PlanarSection,
) -> Solid:
    """Build the complete section slab strictly outside one occurrence end."""

    inner = end + sign * _COORD_FLOOR
    outer = end + sign * thickness
    low, high = sorted((inner, outer))
    if high - low <= _COORD_FLOOR:
        raise ValueError("section end slab is too thin to classify")
    points = tuple(Vector(*_world(frame, low, vertex.point)) for vertex in section.boundary)
    wire = Wire.make_polygon((*points, points[0]))
    return Solid.extrude(
        Face(wire),
        Vector(*(component * (high - low) for component in frame.run)),
    )


def _material_fraction(part: Part, probe: Solid) -> float:
    intersection = part.intersect(probe)
    if intersection is None:
        volume = 0.0
    elif hasattr(intersection, "volume"):
        volume = float(intersection.volume)
    else:
        volume = sum(float(shape.volume) for shape in intersection)
    return volume / float(probe.volume)


def _void_and_open(
    solid: Part,
    frame: LocalFrame,
    interval: tuple[float, float],
    section: PlanarSection,
) -> bool:
    try:
        if _material_fraction(solid, _probe_prism(frame, interval, section)) > _MATERIAL_VOL_FRAC:
            return False
        scale = max(1.0, interval[1] - interval[0])
        radius = max(math.hypot(*vertex.point) for vertex in section.boundary)
        thickness = max(_END_PROBE, scale * 1e-4, radius * 1e-4)
        return all(
            _material_fraction(solid, _end_slab(frame, end, sign, thickness, section))
            <= _MATERIAL_VOL_FRAC
            for end, sign in ((interval[0], -1.0), (interval[1], 1.0))
        )
    except (RuntimeError, TypeError, ValueError, ZeroDivisionError):
        return False


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
    members: tuple[FaceNode, ...],
    adjacency: dict[FaceNode, set[FaceNode]],
    pair_lines: dict[frozenset[FaceNode], tuple[float, float, float, float]],
) -> tuple[FaceNode, ...]:
    """Choose the cycle by its geometric corner sequence, never node/traversal order."""

    candidates: list[tuple[tuple[tuple[float, float], ...], tuple[FaceNode, ...]]] = []
    for start in members:
        for first in adjacency[start]:
            order = [start, first]
            while len(order) < len(members):
                choices = adjacency[order[-1]] - {order[-2]}
                if len(choices) != 1:
                    raise ValueError("section wall component is not one simple cycle")
                order.append(next(iter(choices)))
            closed = tuple(order)
            corners = tuple(
                pair_lines[frozenset((node, closed[(at + 1) % len(closed)]))][:2]
                for at, node in enumerate(closed)
            )
            candidates.append((corners, closed))
    return min(candidates, key=lambda item: item[0])[1]


def section_ring_proposals(part: Part, graph: FaceGraph) -> tuple[SectionRingProposal, ...]:
    """Return every supported line-walled, constant-section, two-open-end void."""

    bodies = _BodyAdapter()
    for face in part.faces():
        graph.require_node(face)
    planar = tuple(node for node in graph.nodes if graph.is_planar(node))
    directions: dict[tuple[float, float, float], list[Vector3]] = defaultdict(list)
    inspected_pairs: set[frozenset[FaceNode]] = set()
    for left in planar:
        for right in graph.neighbours(left):
            pair = frozenset((left, right))
            if right not in planar or pair in inspected_pairs:
                continue
            inspected_pairs.add(pair)
            for edge in graph.shared_edges(left, right):
                run = _canonical_run(edge)
                if run is not None:
                    key = cast(Vector3, tuple(round(value, 9) for value in run))
                    directions[key].append(run)

    proposals: list[SectionRingProposal] = []
    seen: set[frozenset[FaceNode]] = set()
    for key in sorted(directions):
        run = min(directions[key])
        base = LocalFrame.canonical(run, (0.0, 0.0, 0.0))
        walls = tuple(
            node
            for node in planar
            if (normal := graph.normal(node)) is not None
            and abs(_dot(normal, base.run)) <= _DIRECTION_TOL
        )
        pair_lines: dict[frozenset[FaceNode], tuple[float, float, float, float]] = {}
        adjacency: dict[FaceNode, set[FaceNode]] = defaultdict(set)
        inspected_pairs = set()
        for left in walls:
            for right in graph.neighbours(left):
                pair = frozenset((left, right))
                if right not in walls or pair in inspected_pairs:
                    continue
                inspected_pairs.add(pair)
                line = _pair_line(graph, left, right, base)
                if line is None:
                    continue
                left_span = _face_interval(graph, left, base.run)
                right_span = _face_interval(graph, right, base.run)
                if (
                    left_span is None
                    or right_span is None
                    or any(
                        abs(actual - expected) > _INTERVAL_TOL
                        for actual, expected in zip(
                            (*left_span, *right_span),
                            (line[2], line[3], line[2], line[3]),
                            strict=True,
                        )
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
            identity = frozenset(component)
            solid = graph.common_valid_solid(component)
            if identity in seen or solid is None:
                continue
            order = _ordered_cycle(component, adjacency, pair_lines)
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
            if not _void_and_open(graph.solid_shape(solid), frame, (low, high), section):
                continue
            seen.add(identity)
            occurrence = SectionOccurrence(
                bodies.body(solid),
                frame,
                (low, high),
                section,
                SectionEnds(False, False),
            )
            bodies.validate(solid, occurrence)
            proposals.append(
                SectionRingProposal(
                    occurrence,
                    order,
                    solid,
                    bodies,
                )
            )
    proposals.sort(key=lambda item: (item.frame.run, item.run_interval, item.frame.origin))
    return tuple(proposals)
