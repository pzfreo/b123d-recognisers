# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Experimental ADR-0019 vertical slice for closed obround section recesses.

This module is intentionally absent from the package root and capability manifest.  It proves the
new JSON value and one producer-to-consumer path before the specialised production records are
replaced.  Nothing here is a compatibility API.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder

from b123d_recognisers._adjacency import FaceGraph, FaceNode, frame_points_outward
from b123d_recognisers._geometry import length_tol
from b123d_recognisers._recess_obround import _END_RADIUS_FRAC
from b123d_recognisers._record import Record
from b123d_recognisers._section_passages import _end_slab, _material_fraction, _probe_prism
from b123d_recognisers._sections import (
    BodyRefIssuer,
    LocalFrame,
    PlanarSection,
    SectionEnds,
    SectionOccurrence,
    SectionVertex,
    occurrence_geometry_dict,
)
from b123d_recognisers._typing import Part
from b123d_recognisers.passages import PassageFrame, PassageSection, PassageSectionVertex

_DIRECTION_TOL = 1e-6
_SEMICIRCLE_TOL = 1e-4
_FEATURE_KINDS = frozenset({"pocket"})
_SECTION_SHAPES = frozenset(
    {
        "rectangular",
        "circular",
        "obround",
        "triangular",
        "hexagonal",
        "polygonal",
        "general",
    }
)
Vector2 = tuple[float, float]
Vector3 = tuple[float, float, float]


def _numbers(value: object, size: int, *, name: str) -> tuple[float, ...]:
    if (
        not isinstance(value, tuple)
        or len(value) != size
        or any(isinstance(item, bool) or not isinstance(item, int | float) for item in value)
    ):
        raise ValueError(f"{name} must contain {size} finite numbers")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} must contain {size} finite numbers")
    return result


@dataclass(frozen=True, order=True, slots=True)
class ClosedSectionProfile(Record):
    """One canonical physical closed line/arc boundary."""

    closure: str
    boundary: tuple[PassageSectionVertex, ...]

    def __post_init__(self) -> None:
        if self.closure != "closed":
            raise ValueError("closed section profile closure must be 'closed'")
        PassageSection(self.boundary)


@dataclass(frozen=True, order=True, slots=True)
class SectionEnd(Record):
    """One physical end condition in the section frame."""

    condition: str
    gradient: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.condition not in {"open", "capped"}:
            raise ValueError("section end condition must be 'open' or 'capped'")
        gradient = cast(tuple[float, float], _numbers(self.gradient, 2, name="gradient"))
        if any(round(value, 6) != value for value in gradient):
            raise ValueError("section end gradient must serialize at six decimal places")
        object.__setattr__(self, "gradient", gradient)


@dataclass(frozen=True, order=True, slots=True)
class SectionRecessEnds(Record):
    low: SectionEnd
    high: SectionEnd

    def __post_init__(self) -> None:
        if not isinstance(self.low, SectionEnd) or not isinstance(self.high, SectionEnd):
            raise ValueError("section recess ends must contain SectionEnd values")
        if (self.low.condition == "capped") == (self.high.condition == "capped"):
            raise ValueError("prototype pocket requires exactly one capped end")


@dataclass(frozen=True, order=True, slots=True)
class SectionRecessGeometry(Record):
    """The reconstructible constant-section geometry selected by ADR 0019."""

    type: str
    frame: PassageFrame
    run_interval: tuple[float, float]
    profile: ClosedSectionProfile
    ends: SectionRecessEnds

    def __post_init__(self) -> None:
        if self.type != "section_recess":
            raise ValueError("geometry type must be 'section_recess'")
        if not isinstance(self.frame, PassageFrame):
            raise ValueError("section recess requires a PassageFrame")
        interval = cast(tuple[float, float], _numbers(self.run_interval, 2, name="run_interval"))
        if interval[1] - interval[0] <= 1e-9 or any(round(value, 3) != value for value in interval):
            raise ValueError("run_interval must increase and serialize at three decimals")
        if not isinstance(self.profile, ClosedSectionProfile):
            raise ValueError("prototype requires a closed section profile")
        if not isinstance(self.ends, SectionRecessEnds):
            raise ValueError("section recess requires explicit ends")
        object.__setattr__(self, "run_interval", interval)


@dataclass(frozen=True, order=True, slots=True)
class SectionRecessClassification(Record):
    feature_kind: str
    section_shape: str

    def __post_init__(self) -> None:
        if self.feature_kind not in _FEATURE_KINDS:
            raise ValueError("unsupported prototype feature_kind")
        if self.section_shape not in _SECTION_SHAPES:
            raise ValueError("unsupported prototype section_shape")


@dataclass(frozen=True, order=True, slots=True)
class SectionRecessEvidence(Record):
    defining_faces: tuple[int, ...]
    constituent_faces: tuple[int, ...]

    def __post_init__(self) -> None:
        for name, values in (
            ("defining_faces", self.defining_faces),
            ("constituent_faces", self.constituent_faces),
        ):
            if (
                not isinstance(values, tuple)
                or any(type(value) is not int or value < 0 for value in values)
                or tuple(sorted(set(values))) != values
            ):
                raise ValueError(f"{name} must be sorted unique non-negative indices")
        if not set(self.defining_faces) <= set(self.constituent_faces):
            raise ValueError("defining faces must be constituent faces")


@dataclass(frozen=True, order=True, slots=True)
class PrototypeBodyEntry(Record):
    index: int

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise ValueError("body index must be a non-negative integer")


@dataclass(frozen=True, order=True, slots=True)
class PrototypeFaceEntry(Record):
    index: int

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise ValueError("face index must be a non-negative integer")


@dataclass(frozen=True, order=True, slots=True)
class SectionRecessOccurrence(Record):
    index: int
    body: int
    geometry: SectionRecessGeometry
    classification: SectionRecessClassification
    evidence: SectionRecessEvidence

    def __post_init__(self) -> None:
        if type(self.index) is not int or self.index < 0:
            raise ValueError("occurrence index must be a non-negative integer")
        if type(self.body) is not int or self.body < 0:
            raise ValueError("occurrence body must be a non-negative integer")
        if not isinstance(self.geometry, SectionRecessGeometry):
            raise ValueError("occurrence requires section recess geometry")
        if not isinstance(self.classification, SectionRecessClassification):
            raise ValueError("occurrence requires authoritative classification")
        if not isinstance(self.evidence, SectionRecessEvidence):
            raise ValueError("occurrence requires face evidence")


@dataclass(frozen=True, slots=True)
class SectionRecessPrototypeDocument(Record):
    schema_version: int
    reference_scope: str
    bodies: tuple[PrototypeBodyEntry, ...]
    faces: tuple[PrototypeFaceEntry, ...]
    occurrences: tuple[SectionRecessOccurrence, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1 or self.reference_scope != "result":
            raise ValueError("unsupported section-recess prototype document")
        if tuple(item.index for item in self.bodies) != tuple(range(len(self.bodies))):
            raise ValueError("body roster must be dense and ordered")
        if tuple(item.index for item in self.faces) != tuple(range(len(self.faces))):
            raise ValueError("face roster must be dense and ordered")
        if tuple(item.index for item in self.occurrences) != tuple(range(len(self.occurrences))):
            raise ValueError("occurrence roster must be dense and ordered")
        for occurrence in self.occurrences:
            if occurrence.body >= len(self.bodies):
                raise ValueError("occurrence body index is outside the document roster")
            if any(
                face >= len(self.faces)
                for face in (
                    *occurrence.evidence.defining_faces,
                    *occurrence.evidence.constituent_faces,
                )
            ):
                raise ValueError("occurrence face index is outside the document roster")


@dataclass(frozen=True, slots=True)
class _Candidate:
    defining_faces: tuple[int, ...]
    constituent_faces: tuple[int, ...]
    mouth: int
    body: int
    geometry: SectionRecessGeometry
    section_shape: str


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return cast(Vector3, tuple(a - b for a, b in zip(left, right, strict=True)))


def _scale(vector: Vector3, factor: float) -> Vector3:
    return cast(Vector3, tuple(value * factor for value in vector))


def _unit(vector: Vector3) -> Vector3 | None:
    norm = math.sqrt(_dot(vector, vector))
    return None if norm <= 1e-12 else cast(Vector3, tuple(value / norm for value in vector))


def _canonical(vector: Vector3) -> Vector3:
    normalized = _unit(vector)
    if normalized is None:
        raise ValueError("direction must be nonzero")
    value = normalized
    pivot = max(range(3), key=lambda axis: (abs(value[axis]), axis))
    if value[pivot] < 0:
        value = _scale(value, -1.0)
    return cast(Vector3, tuple(0.0 if abs(item) < 5e-13 else item for item in value))


def _parallel(left: Vector3, right: Vector3) -> bool:
    return abs(abs(_dot(left, right)) - 1.0) <= _DIRECTION_TOL


def _point(value: object) -> Vector3:
    return cast(Vector3, tuple(float(item) for item in value.Coord()))  # type: ignore[attr-defined]


def _cylinder(graph: FaceGraph, node: FaceNode) -> tuple[float, Vector3, Vector3] | None:
    surface = BRepAdaptor_Surface(graph.face(node).wrapped)
    if surface.GetType() != GeomAbs_Cylinder:
        return None
    cylinder = surface.Cylinder()
    return (
        float(cylinder.Radius()),
        _canonical(_point(cylinder.Axis().Direction())),
        _point(cylinder.Axis().Location()),
    )


def _edge_sweep(
    graph: FaceGraph, floor: FaceNode, cylinder: FaceNode, radius: float
) -> float | None:
    occurrences = graph.shared_occurrences(floor, cylinder)
    if not occurrences or any(item.edge.geom_type.name != "CIRCLE" for item in occurrences):
        return None
    return sum(float(item.edge.length) for item in occurrences) / radius


def _node_interval(
    graph: FaceGraph, node: FaceNode, direction: Vector3
) -> tuple[float, float] | None:
    values = []
    try:
        for vertex in graph.face(node).vertices():
            position = vertex.center()
            point = (float(position.X), float(position.Y), float(position.Z))
            values.append(_dot(point, direction))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return (min(values), max(values)) if values else None


def _project(point: Vector3, frame: LocalFrame) -> Vector2:
    relative = _subtract(point, frame.origin)
    return (_dot(relative, frame.u), _dot(relative, frame.v))


def _polygonal_section(
    graph: FaceGraph, floor: FaceNode, frame: LocalFrame
) -> PlanarSection | None:
    """Read one physical straight-edged floor wire into the free section frame."""

    try:
        wires = tuple(graph.face(floor).wires())
        if len(wires) != 1:
            return None
        edges = tuple(wires[0].edges())
        if len(edges) < 3 or any(edge.geom_type.name != "LINE" for edge in edges):
            return None
        points = []
        for index, edge in enumerate(edges):
            shared = tuple(
                left
                for left in edges[index - 1].vertices()
                for right in edge.vertices()
                if left == right
            )
            if len(shared) != 1:
                return None
            point = shared[0]
            points.append(_project((float(point.X), float(point.Y), float(point.Z)), frame))
        raw = PlanarSection(tuple(SectionVertex(point) for point in points))
        centre = raw.centroid
        return PlanarSection(
            tuple(
                SectionVertex((vertex.point[0] - centre[0], vertex.point[1] - centre[1]))
                for vertex in raw.boundary
            )
        )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _public_geometry(
    *,
    depth: Vector3,
    first_center: Vector3,
    second_center: Vector3,
    radius: float,
    run_interval: tuple[float, float],
    floor_at: float,
) -> SectionRecessGeometry:
    centroid = cast(
        Vector3,
        tuple(
            (left + right) / 2.0 for left, right in zip(first_center, second_center, strict=True)
        ),
    )
    frame = LocalFrame.canonical(depth, centroid)
    first = _project(first_center, frame)
    second = _project(second_center, frame)
    long = (second[0] - first[0], second[1] - first[1])
    length = math.hypot(*long)
    if length <= 1e-12:
        raise ValueError("obround cap centres must be distinct")
    direction = (long[0] / length, long[1] / length)
    width = (-direction[1], direction[0])
    points = (
        (first[0] - radius * width[0], first[1] - radius * width[1]),
        (second[0] - radius * width[0], second[1] - radius * width[1]),
        (second[0] + radius * width[0], second[1] + radius * width[1]),
        (first[0] + radius * width[0], first[1] + radius * width[1]),
    )
    section = PlanarSection(
        tuple(
            SectionVertex(point, 1.0 if index in (1, 3) else 0.0)
            for index, point in enumerate(points)
        )
    )
    issuer = BodyRefIssuer()
    occurrence = SectionOccurrence(
        issuer.issue(),
        frame,
        run_interval,
        section,
        SectionEnds(
            low_capped=abs(floor_at - run_interval[0]) <= abs(floor_at - run_interval[1]),
            high_capped=abs(floor_at - run_interval[1]) < abs(floor_at - run_interval[0]),
        ),
    )
    return project_section_recess_geometry(occurrence, body_refs=issuer)


def project_section_recess_geometry(
    occurrence: SectionOccurrence, *, body_refs: BodyRefIssuer
) -> SectionRecessGeometry:
    """Project any closed private section occurrence into the experimental JSON geometry."""

    projected = occurrence_geometry_dict(occurrence, body_refs=body_refs)
    frame_value = cast(dict[str, list[float]], projected["frame"])
    section_value = cast(dict[str, list[dict[str, object]]], projected["section"])
    ends_value = cast(dict[str, bool], projected["ends"])
    return SectionRecessGeometry(
        "section_recess",
        PassageFrame(
            cast(Vector3, tuple(frame_value["origin"])),
            cast(Vector3, tuple(frame_value["run"])),
            cast(Vector3, tuple(frame_value["u"])),
            cast(Vector3, tuple(frame_value["v"])),
        ),
        cast(tuple[float, float], tuple(projected["run_interval"])),  # type: ignore[arg-type]
        ClosedSectionProfile(
            "closed",
            tuple(
                PassageSectionVertex(
                    cast(Vector2, tuple(cast(list[float], vertex["point"]))),
                    cast(float, vertex["bulge"]),
                )
                for vertex in section_value["boundary"]
            ),
        ),
        SectionRecessEnds(
            SectionEnd("capped" if ends_value["low_capped"] else "open"),
            SectionEnd("capped" if ends_value["high_capped"] else "open"),
        ),
    )


def _one_obround_candidate(graph: FaceGraph, floor: FaceNode) -> _Candidate | None:
    floor_normal = graph.normal(floor)
    if floor_normal is None:
        return None
    depth = _canonical(floor_normal)
    concave = tuple(node for node in graph.neighbours(floor) if graph.arc(floor, node) == "concave")
    cylinders = tuple(node for node in concave if graph.surface(node) == GeomAbs_Cylinder)
    sides = tuple(node for node in concave if graph.is_planar(node))
    if len(cylinders) != 2 or len(sides) != 2 or len(concave) != 4:
        return None
    if any(frame_points_outward(graph.face(node)) is not False for node in cylinders):
        return None
    cylinder_data = tuple(_cylinder(graph, node) for node in cylinders)
    if any(item is None for item in cylinder_data):
        return None
    first, second = (item for item in cylinder_data if item is not None)
    radius = first[0]
    if (
        abs(first[0] - second[0]) > length_tol(radius, rel=_END_RADIUS_FRAC)
        or not _parallel(first[1], second[1])
        or not _parallel(first[1], depth)
    ):
        return None
    long = _subtract(second[2], first[2])
    long = _subtract(long, _scale(depth, _dot(long, depth)))
    long_direction = _unit(long)
    if long_direction is None:
        return None
    width_direction = _canonical(
        (
            depth[1] * long_direction[2] - depth[2] * long_direction[1],
            depth[2] * long_direction[0] - depth[0] * long_direction[2],
            depth[0] * long_direction[1] - depth[1] * long_direction[0],
        )
    )
    side_normals = tuple(graph.normal(node) for node in sides)
    if any(normal is None for normal in side_normals):
        return None
    normals = tuple(_canonical(normal) for normal in side_normals if normal is not None)
    if (
        not _parallel(normals[0], normals[1])
        or any(not _parallel(normal, width_direction) for normal in normals)
        or any(abs(_dot(normal, depth)) > _DIRECTION_TOL for normal in normals)
    ):
        return None
    if not all(graph.arc(cylinder, side) == "smooth" for cylinder in cylinders for side in sides):
        return None
    sweeps = tuple(_edge_sweep(graph, floor, cylinder, radius) for cylinder in cylinders)
    if any(sweep is None or abs(sweep - math.pi) > _SEMICIRCLE_TOL for sweep in sweeps):
        return None
    intervals = tuple(_node_interval(graph, node, depth) for node in (*cylinders, *sides))
    if any(interval is None for interval in intervals):
        return None
    spans = tuple(interval for interval in intervals if interval is not None)
    low = min(interval[0] for interval in spans)
    high = max(interval[1] for interval in spans)
    tolerance = length_tol(high - low, rel=_END_RADIUS_FRAC)
    if high - low <= tolerance or any(
        abs(interval[0] - low) > tolerance or abs(interval[1] - high) > tolerance
        for interval in spans
    ):
        return None
    floor_interval = _node_interval(graph, floor, depth)
    if floor_interval is None:
        return None
    floor_at = sum(floor_interval) / 2
    if min(abs(floor_at - low), abs(floor_at - high)) > tolerance:
        return None
    mouth_at = high if abs(floor_at - low) <= tolerance else low
    context = set(graph.neighbours(cylinders[0]))
    for node in (*cylinders[1:], *sides):
        context &= set(graph.neighbours(node))
    mouths = []
    for node in context - {floor}:
        normal = graph.normal(node) if graph.is_planar(node) else None
        interval = _node_interval(graph, node, depth)
        if (
            normal is not None
            and _parallel(_canonical(normal), depth)
            and interval is not None
            and abs(sum(interval) / 2 - mouth_at) <= tolerance
            and all(
                graph.arc(node, support) in ("convex", "smooth") for support in (*cylinders, *sides)
            )
        ):
            mouths.append(node)
    owner = graph.common_valid_solid((*cylinders, *sides, floor))
    if len(mouths) != 1 or owner is None:
        return None
    try:
        geometry = _public_geometry(
            depth=depth,
            first_center=first[2],
            second_center=second[2],
            radius=radius,
            run_interval=(low, high),
            floor_at=floor_at,
        )
    except ValueError:
        return None
    return _Candidate(
        tuple(sorted(node.index for node in (*cylinders, *sides))),
        tuple(sorted((floor.index, *(node.index for node in (*cylinders, *sides))))),
        mouths[0].index,
        owner.ordinal,
        geometry,
        "obround",
    )


def _one_polygonal_candidate(graph: FaceGraph, floor: FaceNode) -> _Candidate | None:
    normal = graph.normal(floor)
    if normal is None:
        return None
    depth = _canonical(normal)
    walls = tuple(
        node
        for node in graph.neighbours(floor)
        if graph.arc(floor, node) == "concave" and graph.is_planar(node)
    )
    if len(walls) < 3 or any(
        (wall_normal := graph.normal(wall)) is None
        or abs(_dot(wall_normal, depth)) > _DIRECTION_TOL
        for wall in walls
    ):
        return None
    intervals = tuple(_node_interval(graph, wall, depth) for wall in walls)
    if any(interval is None for interval in intervals):
        return None
    spans = tuple(interval for interval in intervals if interval is not None)
    low = min(interval[0] for interval in spans)
    high = max(interval[1] for interval in spans)
    tolerance = length_tol(high - low, rel=_END_RADIUS_FRAC)
    if high - low <= tolerance or any(
        abs(interval[0] - low) > tolerance or abs(interval[1] - high) > tolerance
        for interval in spans
    ):
        return None
    floor_interval = _node_interval(graph, floor, depth)
    if floor_interval is None:
        return None
    floor_at = sum(floor_interval) / 2.0
    if min(abs(floor_at - low), abs(floor_at - high)) > tolerance:
        return None
    mouth_at = high if abs(floor_at - low) <= tolerance else low
    context = set(graph.neighbours(walls[0]))
    for wall in walls[1:]:
        context &= set(graph.neighbours(wall))
    mouths = []
    for node in context - {floor}:
        mouth_normal = graph.normal(node) if graph.is_planar(node) else None
        interval = _node_interval(graph, node, depth)
        if (
            mouth_normal is not None
            and _parallel(_canonical(mouth_normal), depth)
            and interval is not None
            and abs(sum(interval) / 2.0 - mouth_at) <= tolerance
            and all(graph.arc(node, wall) in ("convex", "smooth") for wall in walls)
        ):
            mouths.append(node)
    owner = graph.common_valid_solid((*walls, floor))
    if len(mouths) != 1 or owner is None:
        return None
    centre = graph.face(floor).center()
    frame = LocalFrame.canonical(depth, (float(centre.X), float(centre.Y), float(centre.Z)))
    section = _polygonal_section(graph, floor, frame)
    if section is None or len(section.boundary) != len(walls):
        return None
    try:
        solid = graph.solid_shape(owner)
        scale = max(1.0, high - low)
        radius = max(math.hypot(*vertex.point) for vertex in section.boundary)
        thickness = max(2e-5, scale * 1e-4, radius * 1e-4)
        floor_sign = -1.0 if abs(floor_at - low) <= tolerance else 1.0
        mouth_sign = -floor_sign
        if (
            _material_fraction(solid, _probe_prism(frame, (low, high), section)) > 1e-9
            or _material_fraction(solid, _end_slab(frame, mouth_at, mouth_sign, thickness, section))
            > 1e-9
            or _material_fraction(solid, _end_slab(frame, floor_at, floor_sign, thickness, section))
            < 1.0 - 1e-9
        ):
            return None
    except (RuntimeError, TypeError, ValueError, ZeroDivisionError):
        return None
    issuer = BodyRefIssuer()
    occurrence = SectionOccurrence(
        issuer.issue(),
        frame,
        (low, high),
        section,
        SectionEnds(
            low_capped=abs(floor_at - low) <= abs(floor_at - high),
            high_capped=abs(floor_at - high) < abs(floor_at - low),
        ),
    )
    try:
        geometry = project_section_recess_geometry(occurrence, body_refs=issuer)
    except ValueError:
        return None
    sides = len(section.boundary)
    shape = {3: "triangular", 4: "rectangular", 6: "hexagonal"}.get(sides, "polygonal")
    defining = tuple(sorted(node.index for node in walls))
    return _Candidate(
        defining,
        tuple(sorted((floor.index, *defining))),
        mouths[0].index,
        owner.ordinal,
        geometry,
        shape,
    )


def _candidates(graph: FaceGraph) -> tuple[_Candidate, ...]:
    found = {
        candidate
        for node in graph.nodes
        if graph.is_planar(node)
        for recogniser in (_one_obround_candidate, _one_polygonal_candidate)
        if (candidate := recogniser(graph, node)) is not None
    }
    return tuple(
        sorted(found, key=lambda item: (item.constituent_faces, item.section_shape, item.mouth))
    )


def build_section_recess_prototype(part: Part) -> SectionRecessPrototypeDocument:
    """Build one deterministic, JSON-safe obround vertical-slice document for *part*."""

    graph = FaceGraph(part)
    candidates = _candidates(graph)
    body_indices = {candidate.body for candidate in candidates}
    body_remap = {source: index for index, source in enumerate(sorted(body_indices))}
    occurrences = tuple(
        SectionRecessOccurrence(
            index,
            body_remap[candidate.body],
            candidate.geometry,
            SectionRecessClassification("pocket", candidate.section_shape),
            SectionRecessEvidence(candidate.defining_faces, candidate.constituent_faces),
        )
        for index, candidate in enumerate(candidates)
    )
    return SectionRecessPrototypeDocument(
        1,
        "result",
        tuple(PrototypeBodyEntry(index) for index in range(len(body_indices))),
        tuple(PrototypeFaceEntry(index) for index, _ in enumerate(part.faces())),
        occurrences,
    )


__all__ = [
    "ClosedSectionProfile",
    "PrototypeBodyEntry",
    "PrototypeFaceEntry",
    "SectionEnd",
    "SectionRecessClassification",
    "SectionRecessEvidence",
    "SectionRecessEnds",
    "SectionRecessGeometry",
    "SectionRecessOccurrence",
    "SectionRecessPrototypeDocument",
    "build_section_recess_prototype",
    "project_section_recess_geometry",
]
