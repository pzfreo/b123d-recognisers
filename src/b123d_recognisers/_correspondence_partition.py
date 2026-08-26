# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Pure schema-three facts for bounded geometric partition correspondence."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from b123d_recognisers._body_geometry import (
    DIRECTION_TOL,
    DescriptorQuantization,
    MatchingBoundaryGraph,
    MatchingFace,
)

Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class _PrismCurve:
    kind: str
    length: float
    full: bool
    start: Vector3 | None
    end: Vector3 | None
    centre: Vector3 | None
    axis: Vector3 | None
    radius: float | None
    sweep: float | None
    direction: int


@dataclass(frozen=True, slots=True)
class _PrismCap:
    face: MatchingFace
    face_position: int
    axial_position: float
    section_curves: tuple[_PrismCurve, ...]
    side_faces: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _PrismFact:
    axis: Vector3
    interval: tuple[float, float]
    low_cap: _PrismCap
    high_cap: _PrismCap
    section_signature: object
    repeat_count: int
    edge_count: int
    section_points: tuple[Vector3, ...]
    volume: float
    centre_of_mass: Vector3
    quantization: DescriptorQuantization


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _parallel(left: Vector3, right: Vector3) -> bool:
    return 1.0 - abs(_dot(left, right)) <= 4.0 * DIRECTION_TOL


def _axis_vector(axis: str) -> Vector3:
    at = "xyz".index(axis)
    return tuple(1.0 if index == at else 0.0 for index in range(3))  # type: ignore[return-value]


def _curve_roster(
    graph: MatchingBoundaryGraph, face: MatchingFace
) -> tuple[_PrismCurve, ...] | None:
    if len(face.wires) != 1 or face.wires[0].role != "outer" or not face.wires[0].cycle:
        return None
    values = []
    for half_edge in face.wires[0].cycle:
        curve = graph.curves[half_edge.curve]
        values.append(
            _PrismCurve(
                curve.kind,
                curve.length,
                curve.full,
                None
                if half_edge.start is None or half_edge.start.vertex is None
                else graph.vertices[half_edge.start.vertex],
                None
                if half_edge.end is None or half_edge.end.vertex is None
                else graph.vertices[half_edge.end.vertex],
                curve.centre,
                curve.axis,
                curve.radius,
                curve.sweep,
                half_edge.direction,
            )
        )
    return tuple(values)


def prism_fact(
    graph: MatchingBoundaryGraph,
    *,
    axis_name: str,
    span: tuple[float, float],
    section_signature: object,
    repeat_count: int,
    edge_count: int,
    volume: float,
    centre_of_mass: Vector3,
    quantization: DescriptorQuantization,
    charge: Callable[[], None] | None = None,
) -> _PrismFact | None:
    """Return one exact bounded extrusion fact, or ``None`` when ineligible."""

    def charged() -> None:
        if charge is not None:
            charge()

    axis = _axis_vector(axis_name)
    cap_candidates = []
    for position, face in enumerate(graph.faces):
        charged()
        if (
            face.kind == "PLANE"
            and len(face.parameters) == 4
            and _parallel(face.parameters[:3], axis)
        ):
            cap_candidates.append(position)
    cap_positions = tuple(cap_candidates)
    if len(cap_positions) != 2:
        return None
    ordered_caps = tuple(
        sorted(cap_positions, key=lambda position: _dot(graph.faces[position].centroid, axis))
    )
    low_position, high_position = ordered_caps
    low_face, high_face = graph.faces[low_position], graph.faces[high_position]
    if low_face.material_side == high_face.material_side:
        return None
    low_curves = _curve_roster(graph, low_face)
    high_curves = _curve_roster(graph, high_face)
    if low_curves is None or high_curves is None or len(low_curves) != len(high_curves):
        return None
    if any(face.kind not in {"PLANE", "CYLINDER"} for face in graph.faces):
        return None
    if any(any(wire.role != "outer" for wire in face.wires) for face in graph.faces):
        return None

    incidence = dict(graph.incidence)

    def side_for(cap_position: int, curve_position: int) -> int | None:
        charged()
        owners = {
            face_position
            for face_position, _wire_position, _edge_position in incidence.get(curve_position, ())
        }
        if cap_position not in owners or len(owners) != 2:
            return None
        (side,) = owners - {cap_position}
        return side

    low_curve_positions = tuple(item.curve for item in low_face.wires[0].cycle)
    high_curve_positions = tuple(item.curve for item in high_face.wires[0].cycle)
    low_sides = tuple(side_for(low_position, curve) for curve in low_curve_positions)
    high_sides = tuple(side_for(high_position, curve) for curve in high_curve_positions)
    if any(side is None for side in (*low_sides, *high_sides)):
        return None
    closed_low_sides = cast(tuple[int, ...], low_sides)
    closed_high_sides = cast(tuple[int, ...], high_sides)
    low_side_set = set(closed_low_sides)
    high_side_set = set(closed_high_sides)
    side_faces = set(range(len(graph.faces))) - {low_position, high_position}
    if low_side_set != side_faces or high_side_set != side_faces:
        return None
    if len(low_sides) != len(side_faces) or len(high_sides) != len(side_faces):
        return None

    low_by_side = dict(zip(low_sides, low_curves, strict=True))
    high_by_side = dict(zip(high_sides, high_curves, strict=True))
    metric = 2.0 * quantization.metric_quantum
    lo = _dot(low_face.centroid, axis)
    hi = _dot(high_face.centroid, axis)
    for side_position in side_faces:
        charged()
        low_curve = low_by_side[side_position]
        high_curve = high_by_side[side_position]
        side = graph.faces[side_position]
        if (
            low_curve.kind != high_curve.kind
            or low_curve.full != high_curve.full
            or abs(low_curve.length - high_curve.length) > metric
            or (low_curve.radius is None) != (high_curve.radius is None)
            or (
                low_curve.radius is not None
                and high_curve.radius is not None
                and abs(low_curve.radius - high_curve.radius) > metric
            )
            or (low_curve.sweep is None) != (high_curve.sweep is None)
            or (
                low_curve.sweep is not None
                and high_curve.sweep is not None
                and abs(abs(low_curve.sweep) - abs(high_curve.sweep)) > 4.0 * DIRECTION_TOL
            )
        ):
            return None
        if low_curve.kind == "LINE" and side.kind != "PLANE":
            return None
        if low_curve.kind == "CIRCLE" and side.kind != "CYLINDER":
            return None
        if (
            side.kind == "PLANE"
            and abs(_dot(cast(Vector3, side.parameters[:3]), axis)) > 4.0 * DIRECTION_TOL
        ):
            return None
        if side.kind == "CYLINDER" and (
            not _parallel(cast(Vector3, side.parameters[:3]), axis)
            or low_curve.radius is None
            or len(side.parameters) != 7
            or abs(side.parameters[6] - low_curve.radius) > metric
        ):
            return None
        if len(side.wires) != 1 or side.wires[0].role != "outer":
            return None
        side_curve_positions = tuple(item.curve for item in side.wires[0].cycle)
        if low_curve_positions[low_sides.index(side_position)] not in side_curve_positions:
            return None
        if high_curve_positions[high_sides.index(side_position)] not in side_curve_positions:
            return None
        joining = tuple(
            graph.curves[position]
            for position in side_curve_positions
            if position
            not in {
                low_curve_positions[low_sides.index(side_position)],
                high_curve_positions[high_sides.index(side_position)],
            }
        )
        expected_joining = 0 if low_curve.full else 2
        if len(joining) != expected_joining or any(
            curve.kind != "LINE" or curve.vertices is None for curve in joining
        ):
            return None
        joining_positions = tuple(
            position
            for position in side_curve_positions
            if position
            not in {
                low_curve_positions[low_sides.index(side_position)],
                high_curve_positions[high_sides.index(side_position)],
            }
        )
        for curve_position, curve in zip(joining_positions, joining, strict=True):
            charged()
            owners = incidence.get(curve_position, ())
            if len(owners) != 2 or side_position not in {
                face_position for face_position, _wire, _edge in owners
            }:
                return None
            assert curve.vertices is not None
            start, end = (graph.vertices[position] for position in curve.vertices)
            delta = cast(
                Vector3,
                tuple(right - left for left, right in zip(start, end, strict=True)),
            )
            along = _dot(delta, axis)
            transverse = tuple(
                value - along * direction for value, direction in zip(delta, axis, strict=True)
            )
            if (
                sum(value * value for value in transverse) > metric**2
                or abs(abs(along) - (hi - lo)) > metric
            ):
                return None

    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return None
    record_lo, record_hi = span
    bound = 2.0 * quantization.metric_quantum
    placement = _dot(centre_of_mass, axis)
    if abs((placement + lo) - record_lo) > bound or abs((placement + hi) - record_hi) > bound:
        return None

    return _PrismFact(
        axis,
        (record_lo, record_hi),
        _PrismCap(low_face, low_position, lo, low_curves, closed_low_sides),
        _PrismCap(high_face, high_position, hi, high_curves, closed_high_sides),
        section_signature,
        repeat_count,
        edge_count,
        tuple(
            graph.vertices[index]
            for index in sorted(
                {
                    int(vertex)
                    for half_edge in low_face.wires[0].cycle
                    for vertex in (
                        None if half_edge.start is None else half_edge.start.vertex,
                        None if half_edge.end is None else half_edge.end.vertex,
                    )
                    if vertex is not None
                }
            )
        ),
        volume,
        centre_of_mass,
        quantization,
    )
