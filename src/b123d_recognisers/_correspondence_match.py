# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Private, issuer-bound correspondence between two accepted RRP inventories.

F6b1 proves only one-to-one relations.  Split and merge remain deliberately unreachable until
the separately reviewed geometric-partition grammar exists.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from itertools import permutations, product
from typing import cast

from b123d_recognisers._body_geometry import DESCRIPTOR_REL, DescriptorQuantization
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
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
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


def _metric_bound(before: DescriptorQuantization, after: DescriptorQuantization) -> float:
    return 2.0 * (before.metric_quantum + after.metric_quantum)


def _close(left: float, right: float, bound: float) -> bool:
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= bound


def _translated_point(left: Vector3, translation: Vector3, right: Vector3, bound: float) -> bool:
    return all(
        _close(source + delta, target, bound)
        for source, delta, target in zip(left, translation, right, strict=True)
    )


def _translation_witness(
    before: AcceptedOccurrenceSnapshot, after: AcceptedOccurrenceSnapshot
) -> RigidScaleWitness | None:
    """Prove the bounded scale-one/identity-rotation relation without rematching by placement."""

    if (
        before.family != after.family
        or before.record_type != after.record_type
        or before.body.intrinsic != after.body.intrinsic
        or before.body.boundary != after.body.boundary
        or before.body.quantization != after.body.quantization
        or before.summary.repeat_count != after.summary.repeat_count
        or before.summary.edge_count != after.summary.edge_count
        or before.summary.sector_signature != after.summary.sector_signature
        or before.summary.defining != after.summary.defining
        or before.summary.axis != after.summary.axis
    ):
        return None
    before_centre = before.body.placement.centre_of_mass
    after_centre = after.body.placement.centre_of_mass
    translation = tuple(
        target - source for source, target in zip(before_centre, after_centre, strict=True)
    )
    translation = cast(Vector3, translation)
    bound = _metric_bound(before.body.quantization, after.body.quantization)
    if not _translated_point(before.summary.centre, translation, after.summary.centre, bound):
        return None
    axis = "xyz".index(before.summary.axis)
    if any(
        not _close(source + translation[axis], target, bound)
        for source, target in zip(before.summary.span, after.summary.span, strict=True)
    ):
        return None
    return RigidScaleWitness(IDENTITY_ROTATION, translation, 1.0)


def _maximum_matchings(
    left_count: int,
    right_count: int,
    edges: dict[int, tuple[int, ...]],
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Enumerate every maximum-cardinality assignment without a first-win tie break."""

    complete: list[tuple[tuple[int, int], ...]] = []
    generated = 0

    def visit(left: int, used: frozenset[int], chosen: tuple[tuple[int, int], ...]) -> None:
        nonlocal generated
        if left == left_count:
            generated += 1
            if generated > MATCH_HYPOTHESIS_BUDGET:
                raise CorrespondenceMatchError("correspondence hypothesis budget is exhausted")
            complete.append(chosen)
            return
        visit(left + 1, used, chosen)
        for right in edges.get(left, ()):
            if right not in used:
                visit(left + 1, used | {right}, (*chosen, (left, right)))

    visit(0, frozenset(), ())
    maximum = max((len(item) for item in complete), default=0)
    return tuple(item for item in complete if len(item) == maximum)


def _translation_relations(
    before: CorrespondenceSnapshot, after: CorrespondenceSnapshot
) -> tuple[CorrespondenceRelation, ...] | None:
    """Stage group-first scale-one relations; other similarity hypotheses follow separately."""

    group_edges: dict[int, tuple[int, ...]] = {}
    internal: dict[tuple[int, int], tuple[tuple[tuple[int, int], ...], RigidScaleWitness]] = {}
    for before_group_at, before_group in enumerate(before.body_groups):
        compatible_groups: list[int] = []
        for after_group_at, after_group in enumerate(after.body_groups):
            occurrence_edges: dict[int, tuple[int, ...]] = {}
            witnesses: dict[tuple[int, int], RigidScaleWitness] = {}
            for left_at, left_position in enumerate(before_group):
                rights: list[int] = []
                for right_at, right_position in enumerate(after_group):
                    witness = _translation_witness(
                        before.occurrences[left_position], after.occurrences[right_position]
                    )
                    if witness is not None:
                        rights.append(right_at)
                        witnesses[(left_at, right_at)] = witness
                occurrence_edges[left_at] = tuple(rights)
            matchings = _maximum_matchings(len(before_group), len(after_group), occurrence_edges)
            if (
                len(before_group) == len(after_group)
                and len(matchings) == 1
                and len(matchings[0]) == len(before_group)
            ):
                matching = matchings[0]
                used_witnesses = tuple(witnesses[edge] for edge in matching)
                if used_witnesses and all(item == used_witnesses[0] for item in used_witnesses):
                    compatible_groups.append(after_group_at)
                    internal[(before_group_at, after_group_at)] = (matching, used_witnesses[0])
            elif any(matching for matching in matchings):
                # A nonunique internal assignment is a real connected alternative, never a
                # reason to distribute a body's occurrences among independent groups.
                compatible_groups.append(after_group_at)
        group_edges[before_group_at] = tuple(compatible_groups)

    matchings = _maximum_matchings(len(before.body_groups), len(after.body_groups), group_edges)
    if len(matchings) != 1:
        before_refs = tuple(_ref("before", at, before) for at in range(len(before.occurrences)))
        after_refs = tuple(_ref("after", at, after) for at in range(len(after.occurrences)))
        return (CorrespondenceRelation(ChangeKind.AMBIGUOUS, before_refs, after_refs, None, ()),)
    group_matching = matchings[0]
    if any(edge not in internal for edge in group_matching):
        return None

    relations: list[CorrespondenceRelation] = []
    matched_before: set[int] = set()
    matched_after: set[int] = set()
    for before_group_at, after_group_at in group_matching:
        occurrence_matching, witness = internal[(before_group_at, after_group_at)]
        before_group = before.body_groups[before_group_at]
        after_group = after.body_groups[after_group_at]
        identity = all(
            abs(item)
            <= _metric_bound(
                before.occurrences[before_group[0]].body.quantization,
                after.occurrences[after_group[0]].body.quantization,
            )
            for item in witness.translation
        )
        for left_at, right_at in occurrence_matching:
            left = before_group[left_at]
            right = after_group[right_at]
            matched_before.add(left)
            matched_after.add(right)
            relations.append(
                CorrespondenceRelation(
                    ChangeKind.UNCHANGED if identity else ChangeKind.MOVED,
                    (_ref("before", left, before),),
                    (_ref("after", right, after),),
                    None if identity else witness,
                )
            )
    relations.extend(
        CorrespondenceRelation(ChangeKind.REMOVED, (_ref("before", at, before),), (), None)
        for at in range(len(before.occurrences))
        if at not in matched_before
    )
    relations.extend(
        CorrespondenceRelation(ChangeKind.ADDED, (), (_ref("after", at, after),), None)
        for at in range(len(after.occurrences))
        if at not in matched_after
    )
    return tuple(sorted(relations, key=_relation_key))


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
            CorrespondenceRelation(ChangeKind.ADDED, (), (_ref("after", position, after),), None)
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
        translated = _translation_relations(before, after)
        if translated is None:
            raise CorrespondenceMatchError("non-rigid correspondence matching is not staged")
        relations = translated

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
