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
from typing import Any, TypeAlias

from build123d import GeomType
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Standard import Standard_Failure
from OCP.TopAbs import TopAbs_Orientation, TopAbs_SOLID

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
class _WireBuild:
    geometry: WireGeometry
    occurrences: tuple[tuple[tuple[object, int], ...], ...]


@dataclass(frozen=True, slots=True)
class _FaceBuild:
    geometry: FaceGeometry
    wires: tuple[_WireBuild, ...]


@dataclass(frozen=True, slots=True)
class BodyBoundaryGeometry:
    faces: tuple[FaceGeometry, ...]
    incidence: tuple[tuple[EdgeGeometry, tuple[tuple[int, int, int, int], ...]], ...]
    face_count: int
    wire_count: int
    edge_occurrence_count: int
    symmetric: bool


@dataclass(frozen=True, slots=True)
class BodyGeometryDescriptor:
    intrinsic: BodyIntrinsic
    boundary: BodyBoundaryGeometry
    placement: BodyPlacement


@dataclass(frozen=True, slots=True)
class _DescribedBody:
    descriptor: BodyGeometryDescriptor
    faces: tuple[Any, ...]
    face_geometry: tuple[FaceGeometry, ...]


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


def _snap_checked(value: float, quantum: float, *, name: str) -> float:
    """Quantize one scalar and prove the frozen reconstruction ceiling."""

    snapped = _snap(value, quantum)
    if abs(snapped - value) > 2.0 * quantum:
        raise UnsupportedBodyGeometry(f"{name} exceeds the reconstruction bound")
    return snapped


def _positive_fact(value: float, quantum: float, *, name: str) -> float:
    if not math.isfinite(value) or value < quantum:
        raise UnsupportedBodyGeometry(f"{name} is degenerate")
    snapped = _snap_checked(value, quantum, name=name)
    if snapped <= 0.0:
        raise UnsupportedBodyGeometry(f"{name} collapses during quantization")
    return snapped


def _point(value, centre: tuple[float, float, float], quantum: float) -> QPoint:
    raw = tuple(
        component - origin
        for component, origin in zip(_finite(value.X, value.Y, value.Z), centre, strict=True)
    )
    snapped = tuple(_snap(component, quantum) for component in raw)
    displacement = math.sqrt(
        sum((after - before) ** 2 for before, after in zip(raw, snapped, strict=True))
    )
    if displacement > 2.0 * quantum:
        raise UnsupportedBodyGeometry("point exceeds the reconstruction bound")
    return snapped  # type: ignore[return-value]


def _vector(value) -> tuple[float, float, float]:
    raw = _finite(value.X(), value.Y(), value.Z())
    norm = math.sqrt(sum(component * component for component in raw))
    if norm <= DIRECTION_TOL or abs(norm - 1.0) > DIRECTION_TOL:
        raise UnsupportedBodyGeometry("analytic direction is not a supported unit vector")
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
    snapped = tuple(_snap(component, DIRECTION_TOL) for component in canonical)
    norm = math.sqrt(sum(component * component for component in snapped))
    if abs(norm - 1.0) > DIRECTION_TOL:
        raise UnsupportedBodyGeometry("quantized analytic direction is not unit length")
    if (
        math.sqrt(
            sum((after - before) ** 2 for before, after in zip(canonical, snapped, strict=True))
        )
        > 2.0 * DIRECTION_TOL
    ):
        raise UnsupportedBodyGeometry("analytic direction exceeds the reconstruction bound")
    return snapped  # type: ignore[return-value]


def _plane_parameters(
    raw_axis: tuple[float, float, float],
    location: tuple[float, float, float],
    centre: tuple[float, float, float],
    quantum: float,
) -> tuple[float, ...]:
    axis, _ = _canonical_axis(raw_axis)
    offset = sum(
        axis_component * (component - origin)
        for axis_component, component, origin in zip(axis, location, centre, strict=True)
    )
    return (*_qaxis(axis), _snap_checked(offset, quantum, name="plane offset"))


def _reverse_edge(item: tuple[EdgeGeometry, int]) -> tuple[EdgeGeometry, int]:
    edge, direction = item
    return edge, -direction


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


def _canonical_cycle_with_tokens(
    items: tuple[tuple[EdgeGeometry, int, object], ...],
    raw_orientation: int,
) -> tuple[
    tuple[tuple[EdgeGeometry, int], ...],
    tuple[tuple[tuple[object, int], ...], ...],
    int,
]:
    """Canonical semantic presentation and every tied physical alignment."""

    if not items:
        raise UnsupportedBodyGeometry("body wire has no supported edge occurrences")
    candidates = []
    for reversed_presentation, source in (
        (False, items),
        (True, tuple((edge, -direction, token) for edge, direction, token in reversed(items))),
    ):
        for index in range(len(source)):
            rotated = source[index:] + source[:index]
            label = tuple((edge, direction) for edge, direction, _token in rotated)
            tokens = tuple((token, direction) for _edge, direction, token in rotated)
            semantic_winding = raw_orientation * (-1 if reversed_presentation else 1)
            candidates.append((semantic_winding, label, tokens))
    label = min(candidate for _semantic, candidate, _tokens in candidates)
    matching = tuple(item for item in candidates if item[1] == label)
    semantics = {semantic for semantic, _candidate, _tokens in matching}
    if len(semantics) != 1:
        raise UnsupportedBodyGeometry("wire semantic winding is ambiguous")
    semantic_winding = semantics.pop()
    alignments = tuple(
        {
            tokens
            for semantic, candidate, tokens in matching
            if semantic == semantic_winding and candidate == label
        }
    )
    return label, alignments, semantic_winding


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
    qlength = _positive_fact(length, quantum, name="edge length")
    if edge.geom_type == GeomType.LINE:
        return EdgeGeometry("LINE", min(start, end), max(start, end), qlength)
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
        qlength,
        _point(edge.arc_center, centre, quantum),
        _qaxis(axis),
        _positive_fact(float(edge.radius), quantum, name="circle radius"),
        canonical_sweep,
        abs(abs(sweep) - 2.0 * math.pi) <= ANGLE_TOL,
    )


def _face_geometry(face, centre: tuple[float, float, float], scale: float) -> _FaceBuild:
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
        location = plane.Location()
        location_values = _finite(location.X(), location.Y(), location.Z())
        location_tuple = (location_values[0], location_values[1], location_values[2])
        axis, _ = _canonical_axis(raw_axis)
        parameters = _plane_parameters(raw_axis, location_tuple, centre, quantum)
        normal = face.normal_at(face.center())
        material_side = (
            1
            if sum(
                component * normal_component
                for component, normal_component in zip(
                    axis, (normal.X, normal.Y, normal.Z), strict=True
                )
            )
            >= 0.0
            else -1
        )
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
            component - along * direction for component, direction in zip(delta, axis, strict=True)
        )
        parameters = (
            *_qaxis(axis),
            *(
                _snap_checked(component, quantum, name="cylinder axis point")
                for component in closest
            ),
            _positive_fact(float(cylinder.Radius()), quantum, name="cylinder radius"),
        )
        sample = face.center()
        sample_delta = tuple(
            component - origin
            for component, origin in zip((sample.X, sample.Y, sample.Z), loc, strict=True)
        )
        sample_along = sum(
            component * direction for component, direction in zip(sample_delta, axis, strict=True)
        )
        radial = tuple(
            component - sample_along * direction
            for component, direction in zip(sample_delta, axis, strict=True)
        )
        normal = face.normal_at(sample)
        material_side = (
            1
            if sum(
                component * normal_component
                for component, normal_component in zip(
                    radial, (normal.X, normal.Y, normal.Z), strict=True
                )
            )
            >= 0.0
            else -1
        )
        kind = "CYLINDER"
    else:
        raise UnsupportedBodyGeometry(f"unsupported body face surface {face.geom_type}")

    outer = face.outer_wire()
    wire_builds: list[_WireBuild] = []
    for wire in face.wires():
        occurrences = tuple(
            (
                _edge_geometry(edge, centre, quantum),
                -1 if edge.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED else 1,
                edge,
            )
            for edge in wire.edges()
        )
        role = "outer" if wire == outer else "inner"
        raw_orientation = (
            -1 if wire.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED else 1
        )
        canonical, alignments, semantic_winding = _canonical_cycle_with_tokens(
            occurrences, raw_orientation
        )
        wire_builds.append(_WireBuild(WireGeometry(role, semantic_winding, canonical), alignments))
    wire_builds.sort(key=lambda item: item.geometry)
    face_centre = face.center()
    geometry = FaceGeometry(
        kind,
        tuple(parameters),
        _positive_fact(area, area_quantum, name="face area"),
        _point(face_centre, centre, quantum),
        material_side,
        tuple(item.geometry for item in wire_builds),
    )
    return _FaceBuild(geometry, tuple(wire_builds))


def _canonical_topology(
    face_builds: tuple[_FaceBuild, ...],
) -> tuple[
    tuple[FaceGeometry, ...],
    tuple[tuple[EdgeGeometry, tuple[tuple[int, int, int, int], ...]], ...],
    bool,
]:
    """Canonicalize the complete labelled face/wire/edge-occurrence graph."""

    by_label: dict[FaceGeometry, list[int]] = {}
    for index, build in enumerate(face_builds):
        by_label.setdefault(build.geometry, []).append(index)
    classes = tuple(tuple(indices) for _label, indices in sorted(by_label.items()))
    choices = 1
    for entries in classes:
        choices *= math.factorial(len(entries))
        if choices > CANONICAL_SERIALIZATION_BUDGET:
            raise UnsupportedBodyGeometry("body topology canonicalization budget is exhausted")

    wire_variants: dict[
        int,
        tuple[tuple[tuple[int, ...], tuple[tuple[tuple[object, int], ...], ...]], ...],
    ] = {}
    for face_index, build in enumerate(face_builds):
        wire_classes: list[tuple[int, ...]] = []
        by_wire: dict[WireGeometry, list[int]] = {}
        for wire_index, wire in enumerate(build.wires):
            by_wire.setdefault(wire.geometry, []).append(wire_index)
        for _label, wire_entries in sorted(by_wire.items()):
            wire_classes.append(tuple(wire_entries))
            choices *= math.factorial(len(wire_entries))
            if choices > CANONICAL_SERIALIZATION_BUDGET:
                raise UnsupportedBodyGeometry("body topology canonicalization budget is exhausted")
        variants = []
        for groups in product(*(permutations(entries) for entries in wire_classes)):
            order = tuple(index for group in groups for index in group)
            for alignments in product(*(build.wires[index].occurrences for index in order)):
                variants.append((order, alignments))
                if len(variants) * choices > CANONICAL_SERIALIZATION_BUDGET:
                    raise UnsupportedBodyGeometry(
                        "body topology canonicalization budget is exhausted"
                    )
        wire_variants[face_index] = tuple(variants)

    minimum = None
    minimizing = 0
    face_variants = product(*(permutations(entries) for entries in classes))
    generated = 0
    for class_permutations in face_variants:
        ordered_raw = tuple(index for group in class_permutations for index in group)
        for selected_faces in product(*(wire_variants[index] for index in ordered_raw)):
            generated += 1
            if generated > CANONICAL_SERIALIZATION_BUDGET:
                raise UnsupportedBodyGeometry("body topology canonicalization budget is exhausted")
            ordered_faces: list[FaceGeometry] = []
            occurrence_map: dict[object, list[tuple[int, int, int, int]]] = {}
            edge_labels: dict[object, EdgeGeometry] = {}
            for canonical_face, (raw_face, selected_face) in enumerate(
                zip(ordered_raw, selected_faces, strict=True)
            ):
                wire_order, selected_alignments = selected_face
                build = face_builds[raw_face]
                ordered_wire_geometry = tuple(build.wires[index].geometry for index in wire_order)
                ordered_faces.append(
                    FaceGeometry(
                        build.geometry.kind,
                        build.geometry.parameters,
                        build.geometry.area,
                        build.geometry.centroid,
                        build.geometry.material_side,
                        ordered_wire_geometry,
                    )
                )
                for canonical_wire, (raw_wire, selected_alignment) in enumerate(
                    zip(wire_order, selected_alignments, strict=True)
                ):
                    wire = build.wires[raw_wire]
                    for occurrence, ((edge, _), (token, direction)) in enumerate(
                        zip(wire.geometry.edges, selected_alignment, strict=True)
                    ):
                        edge_labels.setdefault(token, edge)
                        occurrence_map.setdefault(token, []).append(
                            (
                                canonical_face,
                                canonical_wire,
                                occurrence,
                                direction,
                            )
                        )
            incidence = tuple(
                sorted(
                    (
                        edge_labels[token],
                        tuple(sorted(occurrences)),
                    )
                    for token, occurrences in occurrence_map.items()
                )
            )
            candidate = (tuple(ordered_faces), incidence)
            if minimum is None or candidate < minimum:
                minimum = candidate
                minimizing = 1
            elif candidate == minimum:
                minimizing += 1
    if minimum is None:
        raise UnsupportedBodyGeometry("body topology has no canonical serialization")
    return minimum[0], minimum[1], minimizing > 1


def describe_solid(solid) -> _DescribedBody:
    """Build one complete supported descriptor or refuse without a partial value."""

    if solid.wrapped.ShapeType() != TopAbs_SOLID or not BRepCheck_Analyzer(solid.wrapped).IsValid():
        raise UnsupportedBodyGeometry("body is not one valid closed solid")
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
    except (RuntimeError, Standard_Failure) as error:
        raise UnsupportedBodyGeometry("kernel mass properties are unavailable") from error
    if (
        volume <= 0.0
        or surface_area <= 0.0
        or not all(math.isfinite(value) and value >= 0.0 for value in moments)
    ):
        raise UnsupportedBodyGeometry("body mass properties are degenerate")
    scale = max(volume ** (1.0 / 3.0), math.sqrt(surface_area))
    quantum = _metric_tolerance(scale)
    area_quantum = (scale + quantum) ** 2 - scale**2
    volume_quantum = (scale + quantum) ** 3 - scale**3
    moment_quantum = (scale + quantum) ** 5 - scale**5
    raw_faces = tuple(solid.faces())
    raw_geometry = tuple(_face_geometry(face, centre, scale) for face in raw_faces)
    faces, incidence, symmetric = _canonical_topology(raw_geometry)
    wire_count = sum(len(face.wires) for face in faces)
    edge_count = sum(len(wire.edges) for face in faces for wire in face.wires)
    descriptor = BodyGeometryDescriptor(
        BodyIntrinsic(
            _positive_fact(volume, volume_quantum, name="body volume"),
            _positive_fact(surface_area, area_quantum, name="body surface area"),
            tuple(
                sorted(
                    _positive_fact(value, moment_quantum, name="principal moment")
                    for value in moments
                )
            ),  # type: ignore[arg-type]
        ),
        BodyBoundaryGeometry(faces, incidence, len(faces), wire_count, edge_count, symmetric),
        BodyPlacement(centre),
    )
    return _DescribedBody(
        descriptor,
        raw_faces,
        tuple(build.geometry for build in raw_geometry),
    )
