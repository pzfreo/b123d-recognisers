# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Run-owned effective analytic facts without replacing original topology.

This is the neutral F1 seam from epic 0004.  Every lookup is keyed by the exact
``FaceNode`` issued by one ``FaceGraph`` and every returned value retains that node.
The original face remains authoritative for topology, orientation and evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, TypeAlias

import OCP
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import (
    GeomAbs_BezierSurface,
    GeomAbs_BSplineSurface,
    GeomAbs_Cone,
    GeomAbs_Cylinder,
    GeomAbs_Plane,
    GeomAbs_Sphere,
    GeomAbs_Torus,
)
from OCP.gp import gp_Cone, gp_Cylinder, gp_Pln, gp_Sphere
from OCP.ShapeAnalysis import ShapeAnalysis_CanonicalRecognition
from OCP.Standard import Standard_Failure

from b123d_recognisers._adjacency import FaceGraph, FaceNode
from b123d_recognisers._geometry import COORD_FLOOR

_RECOVERY_REL = 1e-6
_SUPPORTED_OCCT_CERTIFICATE_VERSIONS = frozenset({"7.9.3.1"})
_CERTIFICATE_AUTHORITY = "OCCT ShapeAnalysis_CanonicalRecognition face maximum-distance contract"


class SurfaceKind(Enum):
    PLANE = "plane"
    CYLINDER = "cylinder"
    CONE = "cone"
    SPHERE = "sphere"


class SurfaceProvenance(Enum):
    NATIVE = "native"
    RECOVERED = "recovered"


class OrientationCapability(Enum):
    NATIVE_ORIENTED = "native-oriented"
    RECOVERED_UNORIENTED = "recovered-unoriented"


class SurfaceRefusalReason(Enum):
    UNSUPPORTED_KIND = "unsupported-kind"
    UNSUPPORTED_TORUS_RECOVERY = "unsupported-torus-recovery"
    FIT_UNAVAILABLE = "fit-unavailable"
    INVALID_INPUT = "invalid-input"
    INVALID_RESULT = "invalid-result"
    RESIDUAL_EXCEEDED = "residual-exceeded"
    AMBIGUOUS_PRIMITIVE = "ambiguous-primitive"
    UNSUPPORTED_OCCT_CONTRACT = "unsupported-occt-contract"


class SurfaceReaderDisposition(Enum):
    RAW_TOPOLOGY = "raw-topology"
    PENDING_MIGRATION = "pending-migration"
    ORIENTATION_DEFERRED = "orientation-deferred"
    TORUS_DEFERRED = "torus-deferred"


# Complete baseline roster of modules making face-surface classification decisions. Tests derive
# the source-side set independently so adding another raw reader fails visibly. The rationale is
# mandatory; a disposition is not permission to leave an undocumented acceptance path forever.
SURFACE_READER_ROSTER: dict[str, tuple[SurfaceReaderDisposition, str]] = {
    "_adjacency": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "base graph caches original surface/topology facts; it cannot import this layer",
    ),
    "angled_steps": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "edge geom_type validates a split terminal boundary, not a face surface",
    ),
    "_bevel": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar bevel family gate"),
    "_cylinder_substrate": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cylinder kind can migrate, but external/bore material side waits for F2",
    ),
    "_hole_features": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "hole termination distinguishes cones and toroidal blends",
    ),
    "_recess_core": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar recess boundary gate"),
    "_recess_faces": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "planar wall normals participate in material-side geometry",
    ),
    "_rings": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar ring membership gate"),
    "chamfers": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cone and neighbouring-plane directions participate in the family predicate",
    ),
    "countersinks": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cone/cylinder axes and opening direction participate in the family predicate",
    ),
    "fillets": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "toroidal fillets are outside the four-primitive F1 seam",
    ),
    "flats": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar flat family gate"),
    "grooves": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "groove evidence includes conical and toroidal surfaces",
    ),
    "levels": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar level and step gates"),
    "pads": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar pad family gate"),
    "plates": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar plate family gate"),
    "polygonal_bosses": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar polygonal-side membership gate",
    ),
    "profiled_bores": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar profile-face gate"),
    "repeating_profiles": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "edge geom_type classifies profile boundary curves, not face surfaces",
    ),
}

# AST-derived occurrence counts freeze every raw classification site without depending on line
# numbers. A new alias, variable spelling, or additional call changes this independent inventory.
SURFACE_READER_COUNTS: dict[str, dict[str, int]] = {
    "_adjacency": {"adaptor": 4, "graph_surface": 1},
    "_bevel": {"adaptor": 1},
    "_cylinder_substrate": {"adaptor": 1},
    "_hole_features": {"adaptor": 3},
    "_recess_core": {"is_planar": 2},
    "_recess_faces": {"adaptor": 1, "is_planar": 1, "geom_type": 1},
    "_rings": {"is_planar": 1},
    "angled_steps": {"geom_type": 1},
    "chamfers": {"adaptor": 3},
    "countersinks": {"adaptor": 2},
    "fillets": {"adaptor": 4},
    "flats": {"adaptor": 1},
    "grooves": {"adaptor": 3, "geom_type": 1},
    "levels": {"adaptor": 2},
    "pads": {"adaptor": 2},
    "plates": {"adaptor": 2},
    "polygonal_bosses": {"is_planar": 2},
    "profiled_bores": {"geom_type": 3},
    "repeating_profiles": {"geom_type": 3},
}


@dataclass(frozen=True, slots=True)
class RecoveryCertificate:
    occt_version: str
    authority: str
    maximum_distance_bound: float


@dataclass(frozen=True, slots=True)
class AnalyticSurfaceFact:
    node: FaceNode
    kind: SurfaceKind
    provenance: SurfaceProvenance
    orientation: OrientationCapability
    parameters: tuple[float, ...]
    requested_tolerance: float
    kernel_reported_gap: float
    certificate: RecoveryCertificate | None


@dataclass(frozen=True, slots=True)
class RefusedSurfaceFact:
    node: FaceNode
    reason: SurfaceRefusalReason


EffectiveSurfaceFact: TypeAlias = AnalyticSurfaceFact | RefusedSurfaceFact


class EffectiveSurfaceQuery(Protocol):
    def fact(self, node: FaceNode) -> EffectiveSurfaceFact: ...


def _physical_boundary_length(face) -> float:
    """Physical trim perimeter, excluding seams and degenerate representation edges."""

    return math.fsum(
        edge.length
        for edge in face.edges()
        if not BRep_Tool.IsClosed_s(edge.wrapped, face.wrapped)
        and not BRep_Tool.Degenerated_s(edge.wrapped)
    )


def recovery_nominal(face) -> float:
    """Rigid-transform and seam-invariant controlling length for one trimmed face."""

    area = float(face.area)
    perimeter = float(_physical_boundary_length(face))
    if not math.isfinite(area) or area <= 0.0:
        raise ValueError("analytic recovery requires a finite positive trimmed-face area")
    if not math.isfinite(perimeter) or perimeter < 0.0:
        raise ValueError("analytic recovery requires a finite nonnegative trim perimeter")
    area_scale = math.sqrt(area)
    return min(area_scale, 2.0 * area / perimeter) if perimeter > 0.0 else area_scale


def recovery_tolerance(face) -> float:
    """ADR 0008 F1 same-geometry tolerance, fixed before corpus measurement."""

    return _RECOVERY_REL * recovery_nominal(face) + COORD_FLOOR


_NATIVE_KINDS = {
    GeomAbs_Plane: SurfaceKind.PLANE,
    GeomAbs_Cylinder: SurfaceKind.CYLINDER,
    GeomAbs_Cone: SurfaceKind.CONE,
    GeomAbs_Sphere: SurfaceKind.SPHERE,
}


class EffectiveSurfaceIndex:
    """Lazy one-fact-per-original-node analytic view for one graph."""

    def __init__(self, graph: FaceGraph) -> None:
        self._graph = graph
        self._facts: dict[FaceNode, EffectiveSurfaceFact] = {}

    def fact(self, node: FaceNode) -> EffectiveSurfaceFact:
        if not self._graph.owns(node):
            raise ValueError(f"{node!r} was not issued by this effective surface graph")
        found = self._facts.get(node)
        if found is None:
            found = self._derive(node)
            self._facts[node] = found
        return found

    def oriented_fact(self, node: FaceNode) -> AnalyticSurfaceFact:
        found = self.fact(node)
        if not isinstance(found, AnalyticSurfaceFact):
            raise ValueError(f"surface is unavailable: {found.reason.value}")
        if found.orientation is OrientationCapability.RECOVERED_UNORIENTED:
            raise ValueError("ORIENTATION_UNPROVEN")
        return found

    def _derive(self, node: FaceNode) -> EffectiveSurfaceFact:
        face = self._graph.face(node)
        adaptor = BRepAdaptor_Surface(face.wrapped)
        kind = adaptor.GetType()
        native = _NATIVE_KINDS.get(kind)
        if native is not None:
            try:
                parameters = _validated_parameters(native, _native_primitive(adaptor, native))
            except (AttributeError, RuntimeError, ValueError):
                return RefusedSurfaceFact(node, SurfaceRefusalReason.INVALID_RESULT)
            return AnalyticSurfaceFact(
                node=node,
                kind=native,
                provenance=SurfaceProvenance.NATIVE,
                orientation=OrientationCapability.NATIVE_ORIENTED,
                parameters=parameters,
                requested_tolerance=0.0,
                kernel_reported_gap=0.0,
                certificate=None,
            )
        if kind == GeomAbs_Torus:
            return RefusedSurfaceFact(node, SurfaceRefusalReason.UNSUPPORTED_TORUS_RECOVERY)
        if kind in (GeomAbs_BSplineSurface, GeomAbs_BezierSurface):
            return self._recover(node, face)
        return RefusedSurfaceFact(node, SurfaceRefusalReason.UNSUPPORTED_KIND)

    def _recover(self, node: FaceNode, face) -> EffectiveSurfaceFact:
        occt_version = getattr(OCP, "__version__", "")
        if occt_version not in _SUPPORTED_OCCT_CERTIFICATE_VERSIONS:
            return RefusedSurfaceFact(node, SurfaceRefusalReason.UNSUPPORTED_OCCT_CONTRACT)
        try:
            tolerance = recovery_tolerance(face)
        except ValueError:
            return RefusedSurfaceFact(node, SurfaceRefusalReason.INVALID_INPUT)

        attempts = (
            (SurfaceKind.PLANE, "IsPlane", gp_Pln()),
            (SurfaceKind.CYLINDER, "IsCylinder", gp_Cylinder()),
            (SurfaceKind.CONE, "IsCone", gp_Cone()),
            (SurfaceKind.SPHERE, "IsSphere", gp_Sphere()),
        )
        passed: list[tuple[SurfaceKind, tuple[float, ...], float]] = []
        unavailable = False
        invalid = False
        exceeded = False
        for analytic_kind, method, primitive in attempts:
            try:
                recogniser = ShapeAnalysis_CanonicalRecognition(face.wrapped)
                accepted = bool(getattr(recogniser, method)(tolerance, primitive))
                status = recogniser.GetStatus()
                gap = float(recogniser.GetGap())
            except (Standard_Failure, RuntimeError, ValueError):
                unavailable = True
                continue
            if not accepted:
                continue
            if status != 0 or not math.isfinite(gap) or gap < 0.0:
                invalid = True
                continue
            if gap > tolerance:
                exceeded = True
                continue
            try:
                parameters = _validated_parameters(analytic_kind, primitive)
            except (AttributeError, RuntimeError, ValueError):
                invalid = True
                continue
            passed.append((analytic_kind, parameters, gap))

        if len(passed) != 1:
            if len(passed) > 1:
                return RefusedSurfaceFact(node, SurfaceRefusalReason.AMBIGUOUS_PRIMITIVE)
            if invalid:
                return RefusedSurfaceFact(node, SurfaceRefusalReason.INVALID_RESULT)
            if exceeded:
                return RefusedSurfaceFact(node, SurfaceRefusalReason.RESIDUAL_EXCEEDED)
            return RefusedSurfaceFact(node, SurfaceRefusalReason.FIT_UNAVAILABLE)
        if unavailable or invalid:
            return RefusedSurfaceFact(
                node,
                SurfaceRefusalReason.INVALID_RESULT
                if invalid
                else SurfaceRefusalReason.FIT_UNAVAILABLE,
            )
        analytic_kind, parameters, gap = passed[0]
        return AnalyticSurfaceFact(
            node=node,
            kind=analytic_kind,
            provenance=SurfaceProvenance.RECOVERED,
            orientation=OrientationCapability.RECOVERED_UNORIENTED,
            parameters=parameters,
            requested_tolerance=tolerance,
            kernel_reported_gap=gap,
            certificate=RecoveryCertificate(
                occt_version=occt_version,
                authority=_CERTIFICATE_AUTHORITY,
                maximum_distance_bound=tolerance,
            ),
        )


def _canonical_direction(direction) -> tuple[float, float, float]:
    return _canonical_direction_and_sign(direction)[0]


def _canonical_direction_and_sign(
    direction,
) -> tuple[tuple[float, float, float], float]:
    values = (float(direction.X()), float(direction.Y()), float(direction.Z()))
    dominant = max(range(3), key=lambda axis: (abs(values[axis]), axis))
    sign = 1.0 if values[dominant] >= 0.0 else -1.0
    return (sign * values[0], sign * values[1], sign * values[2]), sign


def _native_primitive(adaptor: BRepAdaptor_Surface, kind: SurfaceKind) -> Any:
    if kind is SurfaceKind.PLANE:
        return adaptor.Plane()
    if kind is SurfaceKind.CYLINDER:
        return adaptor.Cylinder()
    if kind is SurfaceKind.CONE:
        return adaptor.Cone()
    return adaptor.Sphere()


def _closest_axis_point(
    location, direction: tuple[float, float, float]
) -> tuple[float, float, float]:
    point = (float(location.X()), float(location.Y()), float(location.Z()))
    along = sum(value * axis for value, axis in zip(point, direction, strict=True))
    return (
        point[0] - along * direction[0],
        point[1] - along * direction[1],
        point[2] - along * direction[2],
    )


def _primitive_parameters(kind: SurfaceKind, primitive: Any) -> tuple[float, ...]:
    if kind is SurfaceKind.PLANE:
        plane = primitive
        direction = _canonical_direction(plane.Axis().Direction())
        location = plane.Location()
        offset = sum(
            value * axis
            for value, axis in zip(
                (float(location.X()), float(location.Y()), float(location.Z())),
                direction,
                strict=True,
            )
        )
        return (*direction, offset)
    if kind in (SurfaceKind.CYLINDER, SurfaceKind.CONE):
        conic = primitive
        direction, sign = _canonical_direction_and_sign(conic.Axis().Direction())
        if kind is SurfaceKind.CYLINDER:
            point = _closest_axis_point(conic.Axis().Location(), direction)
            return (*point, *direction, float(conic.Radius()))
        apex = conic.Apex()
        return (
            float(apex.X()),
            float(apex.Y()),
            float(apex.Z()),
            *direction,
            sign * float(conic.SemiAngle()),
        )
    sphere = primitive
    centre = sphere.Location()
    return (float(centre.X()), float(centre.Y()), float(centre.Z()), float(sphere.Radius()))


def _validated_parameters(kind: SurfaceKind, primitive: Any) -> tuple[float, ...]:
    parameters = _primitive_parameters(kind, primitive)
    if not parameters or not all(math.isfinite(value) for value in parameters):
        raise ValueError("analytic primitive parameters must be finite")
    direction = parameters[3:6] if kind in (SurfaceKind.CYLINDER, SurfaceKind.CONE) else None
    if kind is SurfaceKind.PLANE:
        direction = parameters[:3]
    if direction is not None and not math.isclose(
        math.sqrt(sum(value * value for value in direction)), 1.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("analytic primitive axis must be unit length")
    if kind in (SurfaceKind.CYLINDER, SurfaceKind.SPHERE) and parameters[-1] <= 0.0:
        raise ValueError("analytic primitive radius must be positive")
    if kind is SurfaceKind.CONE and not 0.0 < abs(parameters[-1]) < math.pi / 2.0:
        raise ValueError("analytic cone angle must be strictly between zero and pi/2")
    return parameters
