# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Private, traversal-neutral geometry facts for one graph-authorized solid.

The values in this module are correspondence evidence, never persistent identity.  They contain
no graph handles or kernel objects and deliberately preserve equal multiplicity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import permutations, product
from typing import TypeAlias

from build123d import GeomType
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_Orientation

DESCRIPTOR_REL = 1e-9
DESCRIPTOR_FLOOR = 1e-7
DIRECTION_TOL = 1e-10
ANGLE_TOL = 1e-10
CANONICAL_SERIALIZATION_BUDGET = 100_000

QScalar: TypeAlias = float
QPoint: TypeAlias = tuple[QScalar, QScalar, QScalar]


class UnsupportedBodyGeometry(ValueError):
    """An authorized solid cannot be represented by the bounded analytic grammar."""


@dataclass(frozen=True, slots=True)
class BodyPlacement:
    centre_of_mass: tuple[float, float, float]
    frame_status: str = "unframed"


@dataclass(frozen=True, slots=True)
class BodyIntrinsic:
    volume: QScalar
    surface_area: QScalar
    principal_moments: tuple[QScalar, QScalar, QScalar]


@dataclass(frozen=True, order=True, slots=True)
class EdgeGeometry:
    kind: str
    start: QPoint
    end: QPoint
    length: QScalar
    centre: QPoint | None = None
    axis: QPoint | None = None
    radius: QScalar | None = None
    sweep: QScalar | None = None
    full: bool = False


@dataclass(frozen=True, order=True, slots=True)
class WireGeometry:
    role: str
    semantic_winding: int
    edges: tuple[tuple[EdgeGeometry, int], ...]


@dataclass(frozen=True, order=True, slots=True)
class FaceGeometry:
    kind: str
    parameters: tuple[QScalar, ...]
    area: QScalar
    centroid: QPoint
    material_side: int
    wires: tuple[WireGeometry, ...]


@dataclass(frozen=True, slots=True)
class BodyBoundaryGeometry:
    faces: tuple[FaceGeometry, ...]
    incidence: tuple[
        tuple[EdgeGeometry, tuple[tuple[int, str], ...]], ...
    ]
    face_count: int
    wire_count: int
    edge_occurrence_count: int
    symmetric: bool


@dataclass(frozen=True, slots=True)
class BodyGeometryDescriptor:
    intrinsic: BodyIntrinsic
    boundary: BodyBoundaryGeometry
    placement: BodyPlacement


def _finite(*values: float) -> tuple[float, ...]:
    converted = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in converted):
        raise UnsupportedBodyGeometry("body geometry contains a non-finite value")
    return converted


def _metric_tolerance(scale: float) -> float:
    return DESCRIPTOR_REL * scale + DESCRIPTOR_FLOOR


def _snap(value: float, quantum: float) -> float:
    if not math.isfinite(value) or not math.isfinite(quantum) or quantum <= 0.0:
        raise UnsupportedBodyGeometry("body geometry cannot be quantized")
    snapped = float(round(value / quantum) * quantum)
    return 0.0 if snapped == 0.0 else snapped


def _point(value, centre: tuple[float, float, float], quantum: float) -> QPoint:
    return tuple(
        _snap(component - origin, quantum)
        for component, origin in zip(_finite(value.X, value.Y, value.Z), centre, strict=True)
    )  # type: ignore[return-value]


def _vector(value) -> tuple[float, float, float]:
    raw = _finite(value.X(), value.Y(), value.Z())
    norm = math.sqrt(sum(component * component for component in raw))
    if norm <= DIRECTION_TOL:
        raise UnsupportedBodyGeometry("analytic direction is degenerate")
    return (raw[0] / norm, raw[1] / norm, raw[2] / norm)


def _canonical_axis(raw: tuple[float, float, float]) -> tuple[tuple[float, float, float], int]:
    sign = 1
    for component in raw:
        if abs(component) >= DIRECTION_TOL:
            sign = 1 if component > 0.0 else -1
            break
    canonical = (sign * raw[0], sign * raw[1], sign * raw[2])
    return canonical, sign


def _qaxis(raw: tuple[float, float, float]) -> QPoint:
    canonical, _ = _canonical_axis(raw)
    return tuple(_snap(component, DIRECTION_TOL) for component in canonical)  # type: ignore[return-value]


def _reverse_edge(item: tuple[EdgeGeometry, int]) -> tuple[EdgeGeometry, int]:
    edge, direction = item
    reversed_edge = EdgeGeometry(
        edge.kind,
        edge.end,
        edge.start,
        edge.length,
        edge.centre,
        edge.axis,
        edge.radius,
        None if edge.sweep is None else -edge.sweep,
        edge.full,
    )
    return reversed_edge, -direction


def _canonical_cycle(
    items: tuple[tuple[EdgeGeometry, int], ...],
) -> tuple[tuple[EdgeGeometry, int], ...]:
    if not items:
        raise UnsupportedBodyGeometry("body wire has no supported edge occurrences")
    forward = tuple(items[index:] + items[:index] for index in range(len(items)))
    reversed_items = tuple(_reverse_edge(item) for item in reversed(items))
    backward = tuple(
        reversed_items[index:] + reversed_items[:index] for index in range(len(reversed_items))
    )
    return min((*forward, *backward))


def _arc_sweep(edge, axis: tuple[float, float, float]) -> float:
    radius = float(edge.radius)
    if radius <= 0.0:
        raise UnsupportedBodyGeometry("circle radius is degenerate")
    magnitude = float(edge.length) / radius
    if magnitude <= ANGLE_TOL or magnitude > 2.0 * math.pi + ANGLE_TOL:
        raise UnsupportedBodyGeometry("circle sweep is outside the supported range")
    if abs(magnitude - 2.0 * math.pi) <= ANGLE_TOL:
        return 2.0 * math.pi
    start = edge.position_at(0.0)
    middle = edge.position_at(0.5)
    centre = edge.arc_center
    sx, sy, sz = start.X - centre.X, start.Y - centre.Y, start.Z - centre.Z
    mx, my, mz = middle.X - centre.X, middle.Y - centre.Y, middle.Z - centre.Z
    cross = (sy * mz - sz * my, sz * mx - sx * mz, sx * my - sy * mx)
    direction = sum(component * normal for component, normal in zip(cross, axis, strict=True))
    return magnitude if direction >= 0.0 else -magnitude


def _edge_geometry(edge, centre: tuple[float, float, float], quantum: float) -> EdgeGeometry:
    kind = getattr(edge.geom_type, "name", str(edge.geom_type))
    start = _point(edge.position_at(0.0), centre, quantum)
    end = _point(edge.position_at(1.0), centre, quantum)
    length = float(edge.length)
    if length <= quantum:
        raise UnsupportedBodyGeometry("edge length is degenerate")
    if edge.geom_type == GeomType.LINE:
        return EdgeGeometry("LINE", min(start, end), max(start, end), _snap(length, quantum))
    if edge.geom_type != GeomType.CIRCLE:
        raise UnsupportedBodyGeometry(f"unsupported body edge curve {kind}")
    curve = BRepAdaptor_Curve(edge.wrapped)
    circle = curve.Circle()
    raw_axis = _vector(circle.Axis().Direction())
    axis, axis_sign = _canonical_axis(raw_axis)
    sweep = axis_sign * _arc_sweep(edge, raw_axis)
    first = (start, end, _snap(sweep, ANGLE_TOL))
    second = (end, start, _snap(-sweep, ANGLE_TOL))
    canonical_start, canonical_end, canonical_sweep = min(first, second)
    return EdgeGeometry(
        "CIRCLE",
        canonical_start,
        canonical_end,
        _snap(length, quantum),
        _point(edge.arc_center, centre, quantum),
        _qaxis(axis),
        _snap(float(edge.radius), quantum),
        canonical_sweep,
        abs(abs(sweep) - 2.0 * math.pi) <= ANGLE_TOL,
    )


def _face_geometry(face, centre: tuple[float, float, float], scale: float) -> FaceGeometry:
    quantum = _metric_tolerance(scale)
    area_quantum = (scale + quantum) ** 2 - scale**2
    area = float(face.area)
    if not math.isfinite(area) or area <= area_quantum:
        raise UnsupportedBodyGeometry("face area is degenerate")
    adaptor = BRepAdaptor_Surface(face.wrapped)
    parameters: tuple[float, ...]
    if face.geom_type == GeomType.PLANE:
        plane = adaptor.Plane()
        raw_axis = _vector(plane.Axis().Direction())
        axis, sign = _canonical_axis(raw_axis)
        location = plane.Location()
        offset = sign * sum(
            axis_component * (component - origin)
            for axis_component, component, origin in zip(
                axis, _finite(location.X(), location.Y(), location.Z()), centre, strict=True
            )
        )
        parameters = (*_qaxis(axis), _snap(offset, quantum))
        normal = face.normal_at(face.center())
        material_side = 1 if sum(
            component * normal_component
            for component, normal_component in zip(
                axis, (normal.X, normal.Y, normal.Z), strict=True
            )
        ) >= 0.0 else -1
        kind = "PLANE"
    elif face.geom_type == GeomType.CYLINDER:
        cylinder = adaptor.Cylinder()
        raw_axis = _vector(cylinder.Axis().Direction())
        axis, _ = _canonical_axis(raw_axis)
        location = cylinder.Location()
        loc = _finite(location.X(), location.Y(), location.Z())
        delta = tuple(component - origin for component, origin in zip(loc, centre, strict=True))
        along = sum(component * direction for component, direction in zip(delta, axis, strict=True))
        closest = tuple(
            component - along * direction
            for component, direction in zip(delta, axis, strict=True)
        )
        parameters = (
            *_qaxis(axis),
            *(_snap(component, quantum) for component in closest),
            _snap(float(cylinder.Radius()), quantum),
        )
        sample = face.center()
        radial = tuple(
            component - origin - along * direction
            for component, origin, direction in zip(
                (sample.X, sample.Y, sample.Z), loc, axis, strict=True
            )
        )
        normal = face.normal_at(sample)
        material_side = 1 if sum(
            component * normal_component
            for component, normal_component in zip(
                radial, (normal.X, normal.Y, normal.Z), strict=True
            )
        ) >= 0.0 else -1
        kind = "CYLINDER"
    else:
        raise UnsupportedBodyGeometry(f"unsupported body face surface {face.geom_type}")

    outer = face.outer_wire()
    wires: list[WireGeometry] = []
    for wire in face.wires():
        occurrences = tuple(
            (
                _edge_geometry(edge, centre, quantum),
                -1
                if edge.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED
                else 1,
            )
            for edge in wire.edges()
        )
        role = "outer" if wire == outer else "inner"
        wires.append(
            WireGeometry(
                role,
                material_side * (1 if role == "outer" else -1),
                _canonical_cycle(occurrences),
            )
        )
    wires.sort()
    face_centre = face.center()
    return FaceGeometry(
        kind,
        tuple(parameters),
        _snap(area, area_quantum),
        _point(face_centre, centre, quantum),
        material_side,
        tuple(wires),
    )


def _canonical_topology(
    raw_faces: tuple,
    face_geometry: tuple[FaceGeometry, ...],
    centre: tuple[float, float, float],
    scale: float,
) -> tuple[
    tuple[FaceGeometry, ...],
    tuple[tuple[EdgeGeometry, tuple[tuple[int, str], ...]], ...],
    bool,
]:
    """Canonicalize the complete labelled face/edge incidence graph."""

    by_label: dict[FaceGeometry, list[int]] = {}
    for index, label in enumerate(face_geometry):
        by_label.setdefault(label, []).append(index)
    classes = tuple(tuple(indices) for _label, indices in sorted(by_label.items()))
    choices = 1
    for entries in classes:
        choices *= math.factorial(len(entries))
        if choices > CANONICAL_SERIALIZATION_BUDGET:
            raise UnsupportedBodyGeometry("body topology canonicalization budget is exhausted")

    quantum = _metric_tolerance(scale)
    edge_incidence: dict[object, list[tuple[int, str]]] = {}
    edge_labels: dict[object, EdgeGeometry] = {}
    for face_index, face in enumerate(raw_faces):
        outer = face.outer_wire()
        for wire in face.wires():
            role = "outer" if wire == outer else "inner"
            for edge in wire.edges():
                edge_incidence.setdefault(edge, []).append((face_index, role))
                edge_labels.setdefault(edge, _edge_geometry(edge, centre, quantum))

    minimum = None
    minimizing = 0
    variants = product(*(permutations(entries) for entries in classes))
    for generated, class_permutations in enumerate(variants, start=1):
        if generated > CANONICAL_SERIALIZATION_BUDGET:
            raise UnsupportedBodyGeometry("body topology canonicalization budget is exhausted")
        ordered_raw = tuple(index for group in class_permutations for index in group)
        canonical_index = {raw: at for at, raw in enumerate(ordered_raw)}
        ordered_faces = tuple(face_geometry[raw] for raw in ordered_raw)
        incidence = tuple(
            sorted(
                (
                    edge_labels[edge],
                    tuple(
                        sorted(
                            (canonical_index[face_index], role)
                            for face_index, role in occurrences
                        )
                    ),
                )
                for edge, occurrences in edge_incidence.items()
            )
        )
        candidate = (ordered_faces, incidence)
        if minimum is None or candidate < minimum:
            minimum = candidate
            minimizing = 1
        elif candidate == minimum:
            minimizing += 1
    if minimum is None:
        raise UnsupportedBodyGeometry("body topology has no canonical serialization")
    return minimum[0], minimum[1], minimizing > 1


def describe_solid(solid) -> BodyGeometryDescriptor:
    """Build one complete supported descriptor or refuse without a partial value."""

    props = GProp_GProps()
    try:
        BRepGProp.VolumeProperties_s(solid.wrapped, props)
        volume = float(props.Mass())
        centre_point = props.CentreOfMass()
        raw_centre = _finite(centre_point.X(), centre_point.Y(), centre_point.Z())
        centre = (raw_centre[0], raw_centre[1], raw_centre[2])
        surface_props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(solid.wrapped, surface_props)
        surface_area = float(surface_props.Mass())
        moments = tuple(float(value) for value in props.PrincipalProperties().Moments())
    except UnsupportedBodyGeometry:
        raise
    except Exception as error:
        raise UnsupportedBodyGeometry("kernel mass properties are unavailable") from error
    if volume <= 0.0 or surface_area <= 0.0 or not all(
        math.isfinite(value) and value >= 0.0 for value in moments
    ):
        raise UnsupportedBodyGeometry("body mass properties are degenerate")
    scale = max(volume ** (1.0 / 3.0), math.sqrt(surface_area))
    quantum = _metric_tolerance(scale)
    area_quantum = (scale + quantum) ** 2 - scale**2
    volume_quantum = (scale + quantum) ** 3 - scale**3
    moment_quantum = (scale + quantum) ** 5 - scale**5
    raw_faces = tuple(solid.faces())
    raw_geometry = tuple(_face_geometry(face, centre, scale) for face in raw_faces)
    faces, incidence, symmetric = _canonical_topology(
        raw_faces, raw_geometry, centre, scale
    )
    wire_count = sum(len(face.wires) for face in faces)
    edge_count = sum(len(wire.edges) for face in faces for wire in face.wires)
    return BodyGeometryDescriptor(
        BodyIntrinsic(
            _snap(volume, volume_quantum),
            _snap(surface_area, area_quantum),
            tuple(sorted(_snap(value, moment_quantum) for value in moments)),  # type: ignore[arg-type]
        ),
        BodyBoundaryGeometry(
            faces, incidence, len(faces), wire_count, edge_count, symmetric
        ),
        BodyPlacement(centre),
    )
