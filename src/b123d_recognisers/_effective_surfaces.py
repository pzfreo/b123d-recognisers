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

from b123d_recognisers._adjacency import FaceGraph, FaceNode, GraphRunToken
from b123d_recognisers._analytic_surfaces import (
    SurfaceKind,
    native_primitive,
    validated_parameters,
)
from b123d_recognisers._geometry import COORD_FLOOR

_RECOVERY_REL = 1e-6
_SUPPORTED_OCCT_CERTIFICATE_VERSIONS = frozenset({"7.9.3.1"})
_CERTIFICATE_AUTHORITY = "OCCT ShapeAnalysis_CanonicalRecognition face maximum-distance contract"


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
    "_body_geometry": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "private F6 descriptor serializes graph-authorized original analytic boundaries",
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
    "_section_passages": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F4b neutral line-wall ring and planar membership grammar",
    ),
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
    "experimental_geometry": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F7 spike facade owns its bounded trimmed-surface anchor projection",
    ),
    "_experimental_frame": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "private issue 274 spike measures original analytic direction evidence for frame inference",
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

# Function/role/ordinal identities freeze every decision without depending on source line numbers.
# Every site has its own disposition and rationale, including mixed modules whose reads cannot be
# truthfully covered by one module-level label.
SURFACE_READER_SITES: dict[str, tuple[SurfaceReaderDisposition, str]] = {
    "_adjacency:surface:adaptor:1": (SurfaceReaderDisposition.RAW_TOPOLOGY, "base surface cache"),
    "_adjacency:is_planar:graph_surface:1": (SurfaceReaderDisposition.RAW_TOPOLOGY, "base query"),
    "_adjacency:_normal_at:adaptor:1": (SurfaceReaderDisposition.RAW_TOPOLOGY, "base normal"),
    "_adjacency:_native_continuation:adaptor:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F2 original native analytic continuation fact",
    ),
    "_adjacency:_native_continuation:adaptor:2": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F2 paired original native analytic continuation fact",
    ),
    "_adjacency:_normal_curvature:adaptor:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F2 original-surface second fundamental form",
    ),
    "_adjacency:frame_points_outward:adaptor:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "original-face material-side query waits for F2",
    ),
    "_adjacency:axis_aligned_axis:adaptor:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "primitive-axis query",
    ),
    "_body_geometry:_edge_geometry:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 bounded analytic edge-kind label",
    ),
    "_body_geometry:_edge_geometry:geom_type:2": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 bounded line grammar gate",
    ),
    "_body_geometry:_edge_geometry:geom_type:3": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 bounded circle grammar gate",
    ),
    "_body_geometry:_edge_geometry:geom_type:4": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 circle-radius projection gate",
    ),
    "_body_geometry:matching_boundary_for_solid:adaptor:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 schema-three canonical cylinder pcurve gauge",
    ),
    "_body_geometry:_face_geometry:adaptor:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 graph-authorized plane/cylinder parameter projection",
    ),
    "_body_geometry:_face_geometry:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 bounded plane grammar gate",
    ),
    "_body_geometry:_face_geometry:geom_type:2": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 bounded cylinder grammar gate",
    ),
    "_body_geometry:_face_geometry:geom_type:3": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F6 unsupported-surface refusal label",
    ),
    "_section_passages:_canonical_run:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F4b bounded straight junction-edge grammar",
    ),
    "_section_passages:section_ring_proposals:is_planar:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "F4b original planar wall-cycle membership",
    ),
    "experimental_geometry:surface_anchor:adaptor:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "bounded facade anchor over the same graph-owned original face",
    ),
    "experimental_geometry:is_planar:is_planar:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "facade projection of the graph-owned planar query",
    ),
    "_experimental_frame:infer_part_frame:adaptor:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "private issue 274 frame inference reads original plane and cylinder direction evidence",
    ),
    "_bevel:classify_bevel:adaptor:1": (SurfaceReaderDisposition.PENDING_MIGRATION, "plane gate"),
    "_cylinder_substrate:analyse_cylinders:adaptor:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cylinder geometry plus material side waits for F2",
    ),
    "_hole_features:_classify_end_uncached:adaptor:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "end plane/sphere/cylinder classification uses oriented topology",
    ),
    "_hole_features:_classify_end_uncached:adaptor:2": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "neighbour plane/cylinder classification uses oriented topology",
    ),
    "_hole_features:_shared_transition:adaptor:1": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "cone-or-torus transition rule includes unsupported torus",
    ),
    "_recess_core:_uninterrupted_long_span:is_planar:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar recess boundary gate",
    ),
    "_recess_core:_bounds_one_void:is_planar:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar recess boundary gate",
    ),
    "_recess_faces:_is_wall:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "edge curve kind, not a face surface",
    ),
    "_recess_faces:_planar_faces:is_planar:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "planar wall normal participates in material-side geometry",
    ),
    "_recess_faces:_cylinder_faces:adaptor:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "cylindrical recess boundary gate",
    ),
    "_rings:rings:is_planar:1": (SurfaceReaderDisposition.PENDING_MIGRATION, "planar ring gate"),
    "angled_steps:_effective_linear_sides:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "edge curve kind, not a face surface",
    ),
    "chamfers:recognise_chamfers:adaptor:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cone family gate uses oriented neighbours",
    ),
    "chamfers:recognise_chamfers:adaptor:2": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cone parameter read uses oriented frame",
    ),
    "chamfers:recognise_chamfers:adaptor:3": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "neighbour plane direction uses oriented frame",
    ),
    "countersinks:cone_rims:adaptor:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cone rim direction uses oriented frame",
    ),
    "countersinks:_discover_countersinks:adaptor:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cylinder direction uses oriented frame",
    ),
    "fillets:_discover_fillets:adaptor:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "analytic anchor uses oriented frame",
    ),
    "fillets:_discover_fillets:adaptor:2": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "torus family gate",
    ),
    "fillets:_discover_fillets:adaptor:3": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "torus parameter read",
    ),
    "fillets:_discover_fillets:adaptor:4": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "neighbour plane/sphere rule uses oriented topology",
    ),
    "flats:_discover_flats:adaptor:1": (SurfaceReaderDisposition.PENDING_MIGRATION, "plane gate"),
    "grooves:_cone_joins:adaptor:1": (
        SurfaceReaderDisposition.ORIENTATION_DEFERRED,
        "cone-axis join uses oriented frame",
    ),
    "grooves:transition:adaptor:1": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "torus transition parameter read",
    ),
    "grooves:_torus_joined:adaptor:1": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "torus adjacency family gate",
    ),
    "grooves:recognise_grooves:geom_type:1": (
        SurfaceReaderDisposition.TORUS_DEFERRED,
        "torus family applicability gate",
    ),
    "levels:recognise_face_levels:adaptor:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar face-level gate",
    ),
    "levels:recognise_risers:adaptor:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar riser gate",
    ),
    "pads:_recognise_rectangular_pads_one:adaptor:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar cap gate",
    ),
    "pads:_recognise_rectangular_pads_one:adaptor:2": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar wall gate",
    ),
    "plates:_discover_plates:adaptor:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar plate inventory gate",
    ),
    "plates:_discover_plates:adaptor:2": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "plate normal/offset read",
    ),
    "polygonal_bosses:_cap_z:is_planar:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar cap gate",
    ),
    "polygonal_bosses:_vertical_side_faces:is_planar:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar side gate",
    ),
    "profiled_bores:principal_boundary_plane:geom_type:1": (
        SurfaceReaderDisposition.PENDING_MIGRATION,
        "planar profile face gate",
    ),
    "profiled_bores:lateral:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "Double-D lateral wall component plane/cylinder gate",
    ),
    "profiled_bores:lateral:adaptor:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "Double-D lateral wall role geometry",
    ),
    "profiled_bores:lateral:geom_type:2": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "Double-D planar chord-wall branch",
    ),
    "profiled_bores:support:adaptor:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "Double-D logical wall support identity",
    ),
    "profiled_bores:support:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "Double-D plane/cylinder support branch",
    ),
    "profiled_bores:double_d_profile:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "line boundary edge gate",
    ),
    "profiled_bores:double_d_profile:geom_type:2": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "circle boundary edge gate",
    ),
    "repeating_profiles:_sample_wire:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "edge curve kind extraction",
    ),
    "repeating_profiles:_sample_wire:geom_type:2": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "edge curve kind fallback",
    ),
    "repeating_profiles:_common_circle_centre:geom_type:1": (
        SurfaceReaderDisposition.RAW_TOPOLOGY,
        "circular boundary edge proof",
    ),
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
    @property
    def run_token(self) -> GraphRunToken: ...

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

    @property
    def run_token(self) -> GraphRunToken:
        return self._graph.run_token

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
        try:
            adaptor = BRepAdaptor_Surface(face.wrapped)
            kind = adaptor.GetType()
        except (Standard_Failure, RuntimeError, ValueError):
            return RefusedSurfaceFact(node, SurfaceRefusalReason.INVALID_INPUT)
        native = _NATIVE_KINDS.get(kind)
        if native is not None:
            try:
                parameters = validated_parameters(native, native_primitive(adaptor, native))
            except (AttributeError, Standard_Failure, RuntimeError, ValueError):
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
                parameters = validated_parameters(analytic_kind, primitive)
            except (AttributeError, Standard_Failure, RuntimeError, ValueError):
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
