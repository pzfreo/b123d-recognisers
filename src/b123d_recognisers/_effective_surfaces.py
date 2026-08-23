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
from typing import Protocol, TypeAlias

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import (
    GeomAbs_Cone,
    GeomAbs_Cylinder,
    GeomAbs_Plane,
    GeomAbs_Sphere,
    GeomAbs_Torus,
)

from b123d_recognisers._adjacency import FaceGraph, FaceNode
from b123d_recognisers._geometry import COORD_FLOOR

_RECOVERY_REL = 1e-6


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
    RESIDUAL_EXCEEDED = "residual-exceeded"
    AMBIGUOUS_PRIMITIVE = "ambiguous-primitive"


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
}


@dataclass(frozen=True, slots=True)
class AnalyticSurfaceFact:
    node: FaceNode
    kind: SurfaceKind
    provenance: SurfaceProvenance
    orientation: OrientationCapability
    requested_tolerance: float
    kernel_reported_gap: float


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
        kind = BRepAdaptor_Surface(face.wrapped).GetType()
        native = _NATIVE_KINDS.get(kind)
        if native is not None:
            return AnalyticSurfaceFact(
                node=node,
                kind=native,
                provenance=SurfaceProvenance.NATIVE,
                orientation=OrientationCapability.NATIVE_ORIENTED,
                requested_tolerance=0.0,
                kernel_reported_gap=0.0,
            )
        if kind == GeomAbs_Torus:
            return RefusedSurfaceFact(node, SurfaceRefusalReason.UNSUPPORTED_TORUS_RECOVERY)
        return RefusedSurfaceFact(node, SurfaceRefusalReason.UNSUPPORTED_KIND)
