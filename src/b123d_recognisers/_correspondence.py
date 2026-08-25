# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Private accepted-occurrence snapshots for later cross-run correspondence.

F6a records facts from one completed inventory only.  It intentionally contains no matcher or
edit classification and exports nothing from the package public surface.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from build123d import GeomType

from b123d_recognisers._adjacency import BodyGeometryAuthorityError, FaceGraph, FaceNode
from b123d_recognisers._body_geometry import (
    BodyGeometryDescriptor,
    UnsupportedBodyGeometry,
)
from b123d_recognisers._candidates import Candidate, FamilyId
from b123d_recognisers.repeating_profiles import RepeatingRadialProfile

if TYPE_CHECKING:
    from b123d_recognisers.result import InventoryProduct

CORRESPONDENCE_FAMILIES = (FamilyId.REPEATING_RADIAL_PROFILES,)

FrozenValue: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | tuple["FrozenValue", ...]
    | tuple[tuple[str, "FrozenValue"], ...]
)


class CorrespondenceSnapshotError(ValueError):
    """A completed product cannot produce one complete accepted snapshot."""


@dataclass(frozen=True, order=True, slots=True)
class DefiningFaceGeometry:
    surface_kind: str
    area: float
    centroid_offset: tuple[float, float, float]
    normal_axis: tuple[float, float, float]
    boundary: tuple[tuple[str, float, float | None], ...]


@dataclass(frozen=True, slots=True)
class RepeatingProfileGeometrySummary:
    repeat_count: int
    edge_count: int
    sector_signature: FrozenValue
    defining: tuple[DefiningFaceGeometry, DefiningFaceGeometry]
    axis: str
    centre: tuple[float, float, float]
    span: tuple[float, float]


@dataclass(frozen=True, slots=True)
class AcceptedOccurrenceSnapshot:
    family: str
    record_type: str
    record_value: FrozenValue
    body: BodyGeometryDescriptor
    summary: RepeatingProfileGeometrySummary


@dataclass(frozen=True, slots=True)
class CorrespondenceSnapshot:
    schema_version: int
    occurrences: tuple[AcceptedOccurrenceSnapshot, ...]


def _freeze(value: object) -> FrozenValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CorrespondenceSnapshotError("record value contains a non-finite number")
        return 0.0 if value == 0.0 else value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CorrespondenceSnapshotError("record value mapping has a non-string key")
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    raise CorrespondenceSnapshotError(
        f"record value contains unsupported {type(value).__name__} state"
    )


def _face_summary(
    graph: FaceGraph,
    node: FaceNode,
    centre: tuple[float, float, float],
) -> DefiningFaceGeometry:
    face = graph.face(node)
    if face.geom_type != GeomType.PLANE:
        raise CorrespondenceSnapshotError("RRP defining evidence contains a non-planar face")
    face_centre = face.center()
    offset = (
        float(face_centre.X) - centre[0],
        float(face_centre.Y) - centre[1],
        float(face_centre.Z) - centre[2],
    )
    normal = face.normal_at(face_centre)
    normal_axis = (float(normal.X), float(normal.Y), float(normal.Z))
    for component in normal_axis:
        if abs(component) >= 1e-10:
            if component < 0.0:
                normal_axis = tuple(-value for value in normal_axis)  # type: ignore[assignment]
            break
    boundary: list[tuple[str, float, float | None]] = []
    try:
        for wire in face.wires():
            boundary.extend(
                (
                    getattr(edge.geom_type, "name", str(edge.geom_type)),
                    float(edge.length),
                    float(edge.radius) if edge.geom_type == GeomType.CIRCLE else None,
                )
                for edge in wire.edges()
            )
    except (AttributeError, RuntimeError, ValueError) as error:
        raise CorrespondenceSnapshotError("RRP defining boundary is unavailable") from error
    if not boundary or not math.isfinite(float(face.area)) or not all(
        math.isfinite(length)
        and (radius is None or math.isfinite(radius))
        for _, length, radius in boundary
    ):
        raise CorrespondenceSnapshotError("RRP defining boundary is malformed")
    return DefiningFaceGeometry(
        "PLANE", float(face.area), offset, normal_axis, tuple(sorted(boundary))
    )


def _occurrence(
    graph: FaceGraph,
    evidence,
    candidate: Candidate[object],
) -> AcceptedOccurrenceSnapshot:
    record = candidate.record
    if not isinstance(record, RepeatingRadialProfile):
        raise CorrespondenceSnapshotError("RRP inventory contains the wrong record type")
    defining = evidence.defining_of(candidate)
    if len(defining) != 2 or any(not graph.owns(node) for node in defining):
        raise CorrespondenceSnapshotError("RRP snapshot requires exactly two original faces")
    solid = graph.common_valid_solid(defining)
    if solid is None:
        raise CorrespondenceSnapshotError("RRP defining faces do not prove one valid solid")
    try:
        body_fact = graph.body_geometry(solid)
    except (BodyGeometryAuthorityError, UnsupportedBodyGeometry) as error:
        raise CorrespondenceSnapshotError("RRP body geometry is unavailable") from error
    if body_fact._solid is not solid:
        raise CorrespondenceSnapshotError("RRP body fact lost its graph-issued solid")
    centre = body_fact.descriptor.placement.centre_of_mass
    defining_summary = tuple(
        sorted(_face_summary(graph, node, centre) for node in defining)
    )
    if len(defining_summary) != 2:
        raise CorrespondenceSnapshotError("RRP defining summary is incomplete")
    summary = RepeatingProfileGeometrySummary(
        record.repeat_count,
        record.edge_count,
        _freeze(record.sector_signature),
        defining_summary,
        record.axis,
        record.centre,
        record.span,
    )
    return AcceptedOccurrenceSnapshot(
        FamilyId.REPEATING_RADIAL_PROFILES.value,
        type(record).__qualname__,
        _freeze(record.to_dict()),
        body_fact.descriptor,
        summary,
    )


class _CorrespondenceSnapshotAuthority:
    """Issuer-bound optional sidecar capability for exactly one InventoryProduct."""

    __slots__ = (
        "_product",
        "_context",
        "_graph",
        "_run_token",
        "_evidence",
        "_physical",
        "_reconciliation",
        "_snapshot",
    )

    def __init__(self) -> None:
        self._product: InventoryProduct | None = None
        self._context: object | None = None
        self._graph: object | None = None
        self._run_token: object | None = None
        self._evidence: object | None = None
        self._physical: object | None = None
        self._reconciliation: object | None = None
        self._snapshot: CorrespondenceSnapshot | None = None

    def bind(self, product: InventoryProduct) -> None:
        if self._product is not None:
            raise CorrespondenceSnapshotError("snapshot authority is already bound")
        self._product = product
        self._context = product.context
        self._graph = product.context.graph
        self._run_token = product.context.graph.run_token
        self._evidence = product.evidence
        self._physical = product.physical
        self._reconciliation = product.reconciliation

    def snapshot(self, product: InventoryProduct) -> CorrespondenceSnapshot:
        if (
            self._product is not product
            or self._context is not product.context
            or self._graph is not product.context.graph
            or self._run_token is not product.context.graph.run_token
            or self._evidence is not product.evidence
            or self._physical is not product.physical
            or self._reconciliation is not product.reconciliation
        ):
            raise CorrespondenceSnapshotError("inventory product is not this authority's product")
        graph = product.context.graph
        try:
            product.evidence._validate_graph(graph)
            source = product.physical.candidate_set(FamilyId.REPEATING_RADIAL_PROFILES)
            product.evidence.validate_candidate_set(source)
            accepted = product.reconciliation.accepted_set(source)
        except ValueError as error:
            raise CorrespondenceSnapshotError(
                "inventory product authority is stale or mixed"
            ) from error
        if len(accepted.candidates) != len(source.candidates) or any(
            left is not right
            for left, right in zip(accepted.candidates, source.candidates, strict=True)
        ):
            raise CorrespondenceSnapshotError(
                "current RRP roster must equal its accepted reconciliation set"
            )
        if self._snapshot is not None:
            return self._snapshot
        staged = tuple(_occurrence(graph, product.evidence, item) for item in accepted.candidates)
        snapshot = CorrespondenceSnapshot(1, staged)
        self._snapshot = snapshot
        return snapshot


def correspondence_snapshot(product: InventoryProduct) -> CorrespondenceSnapshot:
    """Return the optional accepted RRP snapshot issued with *product*."""

    authority = product._correspondence_authority
    if not isinstance(authority, _CorrespondenceSnapshotAuthority):
        raise CorrespondenceSnapshotError("inventory product has no snapshot authority")
    return authority.snapshot(product)
