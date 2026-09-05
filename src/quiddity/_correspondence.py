# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Private accepted-occurrence snapshots for later cross-run correspondence.

F6a records facts from one completed inventory only.  It intentionally contains no matcher or
edit classification and exports nothing from the package public surface.
"""

from __future__ import annotations

import math
import pickle
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

from quiddity._adjacency import BodyGeometryAuthorityError, FaceGraph
from quiddity._body_geometry import (
    BodyBoundaryGeometry,
    BodyGeometryDescriptor,
    BodyIntrinsic,
    BodyPlacement,
    DescriptorQuantization,
    FaceGeometry,
    UnsupportedBodyGeometry,
    validate_descriptor_quantization,
    validate_matching_boundary_graph,
)
from quiddity._body_geometry import MatchingBoundaryGraph as MatchingBoundaryGraph
from quiddity._body_geometry import MatchingCurve as MatchingCurve
from quiddity._body_geometry import MatchingFace as MatchingFace
from quiddity._body_geometry import MatchingHalfEdge as MatchingHalfEdge
from quiddity._body_geometry import MatchingWire as MatchingWire
from quiddity._body_geometry import MatchingWireVertex as MatchingWireVertex
from quiddity._candidates import Candidate, CandidateSet, EvidenceIndex, FamilyId
from quiddity._dispositions import ReconciliationResult
from quiddity._run import RecognitionContext
from quiddity.repeating_profiles import RepeatingRadialProfile


class _InventoryProduct(Protocol):
    @property
    def context(self) -> RecognitionContext: ...

    @property
    def evidence(self) -> EvidenceIndex: ...

    @property
    def physical(self) -> Any: ...

    @property
    def reconciliation(self) -> ReconciliationResult: ...

    @property
    def _correspondence_authority(self) -> object | None: ...


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


@dataclass(frozen=True, slots=True)
class RepeatingProfileGeometrySummary:
    repeat_count: int
    edge_count: int
    sector_signature: FrozenValue
    defining: tuple[FaceGeometry, FaceGeometry]
    axis: str
    centre: tuple[float, float, float]
    span: tuple[float, float]


@dataclass(frozen=True, slots=True)
class AcceptedOccurrenceSnapshot:
    family: str
    record_type: str
    record_value: FrozenValue
    body: BodyGeometryDescriptor
    matching_boundary: MatchingBoundaryGraph
    summary: RepeatingProfileGeometrySummary


@dataclass(frozen=True, slots=True)
class CorrespondenceSnapshot:
    schema_version: int
    occurrences: tuple[AcceptedOccurrenceSnapshot, ...]
    body_groups: tuple[tuple[int, ...], ...]


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


def _authority_value(value: object) -> bytes:
    """Retain the complete issued value as collision-free, run-local bytes."""

    try:
        return pickle.dumps(value, protocol=5)
    except (pickle.PickleError, TypeError, ValueError) as error:
        raise CorrespondenceSnapshotError("authority value cannot be frozen") from error


def _freeze_rrp(record: RepeatingRadialProfile) -> FrozenValue:
    """Freeze the reviewed RRP schema explicitly, never through generic record reflection."""

    return (
        ("axis", _freeze(record.axis)),
        ("centre", _freeze(record.centre)),
        ("span", _freeze(record.span)),
        ("repeat_count", _freeze(record.repeat_count)),
        ("edge_count", _freeze(record.edge_count)),
        ("sector_signature", _freeze(record.sector_signature)),
    )


def _occurrence(
    graph: FaceGraph,
    evidence,
    candidate: Candidate[object],
) -> tuple[AcceptedOccurrenceSnapshot, object]:
    record = candidate.record
    if not isinstance(record, RepeatingRadialProfile):
        raise CorrespondenceSnapshotError("RRP inventory contains the wrong record type")
    defining = tuple(evidence.defining_of(candidate))
    if (
        len(defining) != 2
        or defining[0] is defining[1]
        or any(not graph.owns(node) for node in defining)
    ):
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
    try:
        defining_summary = tuple(sorted(body_fact._defining_face(node) for node in defining))
    except BodyGeometryAuthorityError as error:
        raise CorrespondenceSnapshotError("RRP defining face geometry is unavailable") from error
    if any(face.kind != "PLANE" for face in defining_summary):
        raise CorrespondenceSnapshotError("RRP defining evidence contains a non-planar face")
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
    try:
        validate_descriptor_quantization(body_fact.descriptor.quantization)
    except UnsupportedBodyGeometry as error:
        raise CorrespondenceSnapshotError("RRP descriptor quantization is unavailable") from error
    try:
        matching_boundary = graph.matching_boundary(solid)
    except (BodyGeometryAuthorityError, UnsupportedBodyGeometry) as error:
        raise CorrespondenceSnapshotError("RRP matching boundary is unavailable") from error
    return (
        AcceptedOccurrenceSnapshot(
            FamilyId.REPEATING_RADIAL_PROFILES.value,
            type(record).__qualname__,
            _freeze_rrp(record),
            body_fact.descriptor,
            matching_boundary,
            summary,
        ),
        solid,
    )


def _validate_snapshot(snapshot: CorrespondenceSnapshot) -> None:
    if type(snapshot) is not CorrespondenceSnapshot or type(snapshot.schema_version) is not int:
        raise CorrespondenceSnapshotError("correspondence snapshot schema is malformed")
    if snapshot.schema_version != 3:
        raise CorrespondenceSnapshotError("correspondence snapshot schema is unsupported")
    if type(snapshot.occurrences) is not tuple or type(snapshot.body_groups) is not tuple:
        raise CorrespondenceSnapshotError("correspondence body groups are malformed")
    if any(
        type(occurrence) is not AcceptedOccurrenceSnapshot
        or type(occurrence.body) is not BodyGeometryDescriptor
        or type(occurrence.body.intrinsic) is not BodyIntrinsic
        or type(occurrence.body.boundary) is not BodyBoundaryGeometry
        or type(occurrence.body.placement) is not BodyPlacement
        or type(occurrence.body.quantization) is not DescriptorQuantization
        or type(occurrence.matching_boundary) is not MatchingBoundaryGraph
        or type(occurrence.summary) is not RepeatingProfileGeometrySummary
        for occurrence in snapshot.occurrences
    ):
        raise CorrespondenceSnapshotError("correspondence occurrence schema is malformed")
    if any(
        type(group) is not tuple or any(type(position) is not int for position in group)
        for group in snapshot.body_groups
    ):
        raise CorrespondenceSnapshotError("correspondence body groups are malformed")
    positions = tuple(position for group in snapshot.body_groups for position in group)
    if (
        any(not group or tuple(sorted(group)) != group for group in snapshot.body_groups)
        or tuple(sorted(snapshot.body_groups)) != snapshot.body_groups
        or tuple(sorted(positions)) != tuple(range(len(snapshot.occurrences)))
    ):
        raise CorrespondenceSnapshotError("correspondence body groups are not a complete partition")
    for group in snapshot.body_groups:
        body = snapshot.occurrences[group[0]].body
        if any(snapshot.occurrences[position].body != body for position in group):
            raise CorrespondenceSnapshotError("one correspondence body group has unequal geometry")
    try:
        for occurrence in snapshot.occurrences:
            validate_descriptor_quantization(occurrence.body.quantization)
    except UnsupportedBodyGeometry as error:
        raise CorrespondenceSnapshotError("correspondence quantization is invalid") from error
    try:
        for occurrence in snapshot.occurrences:
            validate_matching_boundary_graph(
                occurrence.matching_boundary,
                occurrence.body.quantization,
            )
    except UnsupportedBodyGeometry as error:
        raise CorrespondenceSnapshotError("correspondence matching boundary is invalid") from error


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
        "_bound_records",
        "_bound_occurrences",
        "_bound_body_groups",
        "_snapshot",
    )

    def __init__(self) -> None:
        self._product: _InventoryProduct | None = None
        self._context: object | None = None
        self._graph: object | None = None
        self._run_token: object | None = None
        self._evidence: object | None = None
        self._physical: object | None = None
        self._reconciliation: object | None = None
        self._bound_records: tuple[tuple[Candidate[object], FrozenValue], ...] = ()
        self._bound_occurrences: object | None = None
        self._bound_body_groups: tuple[tuple[int, ...], ...] | None = None
        self._snapshot: CorrespondenceSnapshot | None = None

    def bind(self, product: _InventoryProduct) -> None:
        if self._product is not None:
            raise CorrespondenceSnapshotError("snapshot authority is already bound")
        self._product = product
        self._context = product.context
        self._graph = product.context.graph
        self._run_token = product.context.graph.run_token
        self._evidence = product.evidence
        self._physical = product.physical
        self._reconciliation = product.reconciliation
        accepted = self._accepted_rrp(product)
        self._bound_records = tuple(
            (candidate, _freeze_rrp(candidate.record))
            for candidate in accepted.candidates
            if isinstance(candidate.record, RepeatingRadialProfile)
        )
        if len(self._bound_records) != len(accepted.candidates):
            raise CorrespondenceSnapshotError("RRP inventory contains the wrong record type")

    @staticmethod
    def _accepted_rrp(product: _InventoryProduct) -> CandidateSet[object]:
        try:
            product.evidence._validate_graph(product.context.graph)
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
        return accepted

    def snapshot(self, product: _InventoryProduct) -> CorrespondenceSnapshot:
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
        accepted = self._accepted_rrp(product)
        current_records = tuple(
            (candidate, _freeze_rrp(candidate.record))
            for candidate in accepted.candidates
            if isinstance(candidate.record, RepeatingRadialProfile)
        )
        if (
            len(current_records) != len(accepted.candidates)
            or len(current_records) != len(self._bound_records)
            or any(
                current_candidate is not bound_candidate or current_value != bound_value
                for (current_candidate, current_value), (bound_candidate, bound_value) in zip(
                    current_records, self._bound_records, strict=True
                )
            )
        ):
            raise CorrespondenceSnapshotError(
                "accepted RRP record identity or value changed after inventory completion"
            )
        if self._snapshot is not None:
            if self._snapshot.body_groups != self._bound_body_groups:
                raise CorrespondenceSnapshotError("correspondence body groups changed after issue")
            try:
                _validate_snapshot(self._snapshot)
            except CorrespondenceSnapshotError as error:
                raise CorrespondenceSnapshotError(
                    "correspondence occurrence values changed after issue"
                ) from error
            try:
                current_occurrences = _authority_value(self._snapshot.occurrences)
            except CorrespondenceSnapshotError as error:
                raise CorrespondenceSnapshotError(
                    "correspondence occurrence values changed after issue"
                ) from error
            if current_occurrences != self._bound_occurrences:
                raise CorrespondenceSnapshotError(
                    "correspondence occurrence values changed after issue"
                )
            return self._snapshot
        staged = tuple(_occurrence(graph, product.evidence, item) for item in accepted.candidates)
        occurrences = tuple(item[0] for item in staged)
        groups: list[list[int]] = []
        owners: list[object] = []
        for position, (_occurrence_value, solid) in enumerate(staged):
            for index, owner in enumerate(owners):
                if solid is owner:
                    groups[index].append(position)
                    break
            else:
                owners.append(solid)
                groups.append([position])
        body_groups = tuple(sorted(tuple(group) for group in groups))
        snapshot = CorrespondenceSnapshot(3, occurrences, body_groups)
        _validate_snapshot(snapshot)
        # The authority retains an independent immutable value, not aliases to the issued
        # dataclass graph. This detects object.__setattr__ mutation of any nested occurrence,
        # descriptor, summary, record value, or quantization field on every cached read.
        self._bound_occurrences = _authority_value(occurrences)
        self._bound_body_groups = body_groups
        self._snapshot = snapshot
        return snapshot


def correspondence_snapshot(product: _InventoryProduct) -> CorrespondenceSnapshot:
    """Return the optional accepted RRP snapshot issued with *product*."""

    authority = product._correspondence_authority
    if not isinstance(authority, _CorrespondenceSnapshotAuthority):
        raise CorrespondenceSnapshotError("inventory product has no snapshot authority")
    return authority.snapshot(product)
