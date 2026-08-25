# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Private, issuer-bound correspondence between two accepted RRP inventories.

F6b1 proves only one-to-one relations.  Split and merge remain deliberately unreachable until
the separately reviewed geometric-partition grammar exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import permutations, product
from typing import cast

from b123d_recognisers._body_geometry import DESCRIPTOR_REL
from b123d_recognisers._correspondence import (
    AcceptedOccurrenceSnapshot,
    CorrespondenceSnapshot,
    CorrespondenceSnapshotError,
    _InventoryProduct,
    _validate_snapshot,
    correspondence_snapshot,
)

MATCH_HYPOTHESIS_BUDGET = 100_000
SCALE_TOL = 4.0 * DESCRIPTOR_REL

Rotation = tuple[
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
]
Vector3 = tuple[float, float, float]


class CorrespondenceMatchError(ValueError):
    """Two products cannot produce one complete closed correspondence result."""


class ChangeKind(str, Enum):
    UNCHANGED = "unchanged"
    MOVED = "moved"
    RESIZED = "resized"
    ADDED = "added"
    REMOVED = "removed"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class SnapshotOccurrenceRef:
    side: str
    position: int
    occurrence: AcceptedOccurrenceSnapshot


@dataclass(frozen=True, slots=True)
class RigidScaleWitness:
    rotation: Rotation
    translation: Vector3
    scale: float


@dataclass(frozen=True, slots=True)
class CorrespondenceRelation:
    kind: ChangeKind
    before_refs: tuple[SnapshotOccurrenceRef, ...]
    after_refs: tuple[SnapshotOccurrenceRef, ...]
    witness: RigidScaleWitness | None
    candidate_witnesses: tuple[RigidScaleWitness, ...] = ()


@dataclass(frozen=True, slots=True)
class CorrespondenceResult:
    schema_version: int
    before_schema: int
    after_schema: int
    relations: tuple[CorrespondenceRelation, ...]


def _determinant(rotation: Rotation) -> int:
    return (
        rotation[0][0]
        * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1]
        * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2]
        * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
    )


def _proper_rotations() -> tuple[Rotation, ...]:
    found: list[Rotation] = []
    for axes in permutations(range(3)):
        for signs in product((-1, 1), repeat=3):
            rows = tuple(
                tuple(signs[row] if column == axes[row] else 0 for column in range(3))
                for row in range(3)
            )
            rotation = cast(Rotation, rows)
            if _determinant(rotation) == 1:
                found.append(rotation)
    return tuple(sorted(found))


PROPER_ROTATIONS = _proper_rotations()
IDENTITY_ROTATION: Rotation = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def _ref(side: str, position: int, snapshot: CorrespondenceSnapshot) -> SnapshotOccurrenceRef:
    if side not in ("before", "after") or type(position) is not int:
        raise CorrespondenceMatchError("correspondence occurrence reference is malformed")
    if not 0 <= position < len(snapshot.occurrences):
        raise CorrespondenceMatchError("correspondence occurrence reference is out of range")
    return SnapshotOccurrenceRef(side, position, snapshot.occurrences[position])


def _validate_ref(reference: SnapshotOccurrenceRef, snapshot: CorrespondenceSnapshot) -> None:
    if (
        type(reference) is not SnapshotOccurrenceRef
        or type(reference.position) is not int
        or not 0 <= reference.position < len(snapshot.occurrences)
        or snapshot.occurrences[reference.position] != reference.occurrence
    ):
        raise CorrespondenceMatchError("correspondence occurrence reference changed")


def _relation_key(relation: CorrespondenceRelation) -> tuple[object, ...]:
    return (
        relation.kind.value,
        tuple((item.occurrence, item.position) for item in relation.before_refs),
        tuple((item.occurrence, item.position) for item in relation.after_refs),
        relation.witness or RigidScaleWitness(IDENTITY_ROTATION, (0.0, 0.0, 0.0), 1.0),
    )


def _validate_result(
    result: CorrespondenceResult,
    before: CorrespondenceSnapshot,
    after: CorrespondenceSnapshot,
) -> None:
    if (
        type(result) is not CorrespondenceResult
        or result.schema_version != 1
        or result.before_schema != 2
        or result.after_schema != 2
        or type(result.relations) is not tuple
    ):
        raise CorrespondenceMatchError("correspondence result schema is malformed")
    before_positions: list[int] = []
    after_positions: list[int] = []
    for relation in result.relations:
        if type(relation) is not CorrespondenceRelation or type(relation.kind) is not ChangeKind:
            raise CorrespondenceMatchError("correspondence relation is malformed")
        for reference in relation.before_refs:
            _validate_ref(reference, before)
            if reference.side != "before":
                raise CorrespondenceMatchError("correspondence relation has a wrong-side reference")
            before_positions.append(reference.position)
        for reference in relation.after_refs:
            _validate_ref(reference, after)
            if reference.side != "after":
                raise CorrespondenceMatchError("correspondence relation has a wrong-side reference")
            after_positions.append(reference.position)
        if relation.kind is ChangeKind.ADDED and (relation.before_refs or not relation.after_refs):
            raise CorrespondenceMatchError("added correspondence relation is malformed")
        if relation.kind is ChangeKind.REMOVED and (
            not relation.before_refs or relation.after_refs
        ):
            raise CorrespondenceMatchError("removed correspondence relation is malformed")
        if relation.kind is ChangeKind.UNCHANGED and relation.witness is not None:
            raise CorrespondenceMatchError("unchanged correspondence carries a witness")
    if sorted(before_positions) != list(range(len(before.occurrences))) or sorted(
        after_positions
    ) != list(range(len(after.occurrences))):
        raise CorrespondenceMatchError("correspondence result does not cover both snapshots once")


def _exact_relations(
    before: CorrespondenceSnapshot, after: CorrespondenceSnapshot
) -> tuple[CorrespondenceRelation, ...] | None:
    """Return the unique exact group/occurrence assignment, or ``None`` when not exact."""

    if before.occurrences == after.occurrences and before.body_groups == after.body_groups:
        return tuple(
            CorrespondenceRelation(
                ChangeKind.UNCHANGED,
                (_ref("before", position, before),),
                (_ref("after", position, after),),
                None,
            )
            for position in range(len(before.occurrences))
        )
    return None


def _compare_snapshots(
    before: CorrespondenceSnapshot, after: CorrespondenceSnapshot
) -> CorrespondenceResult:
    try:
        _validate_snapshot(before)
        _validate_snapshot(after)
    except CorrespondenceSnapshotError as error:
        raise CorrespondenceMatchError("correspondence input snapshot is invalid") from error
    if before.schema_version != 2 or after.schema_version != 2:
        raise CorrespondenceMatchError("correspondence requires snapshot schema 2")

    exact = _exact_relations(before, after)
    if exact is not None:
        relations = exact
    elif not before.occurrences:
        relations = tuple(
            CorrespondenceRelation(
                ChangeKind.ADDED, (), (_ref("after", position, after),), None
            )
            for position in range(len(after.occurrences))
        )
    elif not after.occurrences:
        relations = tuple(
            CorrespondenceRelation(
                ChangeKind.REMOVED, (_ref("before", position, before),), (), None
            )
            for position in range(len(before.occurrences))
        )
    else:
        raise CorrespondenceMatchError("non-exact correspondence matching is not staged")

    result = CorrespondenceResult(1, before.schema_version, after.schema_version, relations)
    _validate_result(result, before, after)
    return result


def correspondence_changes(
    before: _InventoryProduct, after: _InventoryProduct
) -> CorrespondenceResult:
    """Compare two exact issuer-owned products without exposing snapshot authority."""

    try:
        before_snapshot = correspondence_snapshot(before)
        after_snapshot = correspondence_snapshot(after)
    except CorrespondenceSnapshotError as error:
        raise CorrespondenceMatchError("correspondence product authority is invalid") from error
    return _compare_snapshots(before_snapshot, after_snapshot)
