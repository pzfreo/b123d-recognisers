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

from b123d_recognisers._body_geometry import (
    ANGLE_TOL,
    DESCRIPTOR_REL,
    DIRECTION_TOL,
    DescriptorQuantization,
    EdgeGeometry,
    FaceGeometry,
    WireGeometry,
)
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


def _rotate(rotation: Rotation, value: Vector3) -> Vector3:
    return cast(
        Vector3,
        tuple(
            sum(row[column] * value[column] for column in range(3)) for row in rotation
        ),
    )


def _transpose(rotation: Rotation) -> Rotation:
    return cast(
        Rotation,
        tuple(tuple(rotation[column][row] for column in range(3)) for row in range(3)),
    )


def _affine_point(
    rotation: Rotation,
    translation: Vector3,
    scale: float,
    value: Vector3,
) -> Vector3:
    rotated = _rotate(rotation, value)
    return cast(
        Vector3,
        tuple(
            scale * component + offset
            for component, offset in zip(rotated, translation, strict=True)
        ),
    )


def _inverse_witness(witness: RigidScaleWitness) -> RigidScaleWitness:
    _validate_witness(witness)
    inverse_rotation = _transpose(witness.rotation)
    inverse_scale = 1.0 / witness.scale
    inverse_translation = _rotate(inverse_rotation, witness.translation)
    inverse_translation = cast(
        Vector3,
        tuple(-inverse_scale * component for component in inverse_translation),
    )
    return RigidScaleWitness(inverse_rotation, inverse_translation, inverse_scale)


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
    def occurrence_key(reference: SnapshotOccurrenceRef) -> tuple[object, ...]:
        occurrence = reference.occurrence
        return (
            occurrence.family,
            occurrence.record_type,
            repr(occurrence.record_value),
            repr(occurrence.body),
            repr(occurrence.summary),
            reference.position,
        )

    return (
        relation.kind.value,
        tuple(occurrence_key(item) for item in relation.before_refs),
        tuple(occurrence_key(item) for item in relation.after_refs),
        relation.witness or RigidScaleWitness(IDENTITY_ROTATION, (0.0, 0.0, 0.0), 1.0),
    )


def _validate_witness(witness: RigidScaleWitness) -> None:
    if (
        type(witness) is not RigidScaleWitness
        or witness.rotation not in PROPER_ROTATIONS
        or type(witness.translation) is not tuple
        or len(witness.translation) != 3
        or any(
            type(value) is not float or not math.isfinite(value)
            for value in witness.translation
        )
        or type(witness.scale) is not float
        or not math.isfinite(witness.scale)
        or witness.scale <= 0.0
    ):
        raise CorrespondenceMatchError("correspondence transform witness is malformed")


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
        if (
            type(relation) is not CorrespondenceRelation
            or type(relation.kind) is not ChangeKind
            or type(relation.before_refs) is not tuple
            or type(relation.after_refs) is not tuple
            or type(relation.candidate_witnesses) is not tuple
        ):
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
        if relation.witness is not None:
            _validate_witness(relation.witness)
        for candidate_witness in relation.candidate_witnesses:
            _validate_witness(candidate_witness)
        if relation.kind is ChangeKind.ADDED and (
            relation.before_refs
            or not relation.after_refs
            or relation.witness is not None
            or relation.candidate_witnesses
        ):
            raise CorrespondenceMatchError("added correspondence relation is malformed")
        if relation.kind is ChangeKind.REMOVED and (
            not relation.before_refs
            or relation.after_refs
            or relation.witness is not None
            or relation.candidate_witnesses
        ):
            raise CorrespondenceMatchError("removed correspondence relation is malformed")
        if relation.kind is ChangeKind.UNCHANGED and (
            len(relation.before_refs) != 1
            or len(relation.after_refs) != 1
            or relation.witness is not None
            or relation.candidate_witnesses
        ):
            raise CorrespondenceMatchError("unchanged correspondence relation is malformed")
        if relation.kind in {ChangeKind.MOVED, ChangeKind.RESIZED} and (
            len(relation.before_refs) != 1
            or len(relation.after_refs) != 1
            or relation.witness is None
            or relation.candidate_witnesses
        ):
            raise CorrespondenceMatchError("transformed correspondence relation is malformed")
        if relation.kind is ChangeKind.AMBIGUOUS and (
            not relation.before_refs or not relation.after_refs or relation.witness is not None
        ):
            raise CorrespondenceMatchError("ambiguous correspondence relation is malformed")
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


def _scaled_point(left: Vector3, scale: float, right: Vector3, bound: float) -> bool:
    return all(
        _close(scale * source, target, bound) for source, target in zip(left, right, strict=True)
    )


def _order_bound(
    before: DescriptorQuantization,
    after: DescriptorQuantization,
    scale: float,
    order: int,
) -> float:
    quantum_before = {
        1: before.metric_quantum,
        2: before.area_quantum,
        3: before.volume_quantum,
        5: before.moment_quantum,
    }[order]
    quantum_after = {
        1: after.metric_quantum,
        2: after.area_quantum,
        3: after.volume_quantum,
        5: after.moment_quantum,
    }[order]
    return 2.0 * (scale**order * quantum_before + quantum_after)


def _edge_scaled(
    before: EdgeGeometry,
    after: EdgeGeometry,
    scale: float,
    quant_before: DescriptorQuantization,
    quant_after: DescriptorQuantization,
) -> bool:
    metric = _order_bound(quant_before, quant_after, scale, 1)
    return (
        before.kind == after.kind
        and _scaled_point(before.start, scale, after.start, metric)
        and _scaled_point(before.end, scale, after.end, metric)
        and _close(scale * before.length, after.length, metric)
        and ((before.centre is None) == (after.centre is None))
        and (
            before.centre is None
            or _scaled_point(before.centre, scale, cast(Vector3, after.centre), metric)
        )
        and ((before.axis is None) == (after.axis is None))
        and (
            before.axis is None
            or all(
                _close(source, target, 4.0 * DIRECTION_TOL)
                for source, target in zip(before.axis, cast(Vector3, after.axis), strict=True)
            )
        )
        and ((before.radius is None) == (after.radius is None))
        and (
            before.radius is None
            or _close(scale * before.radius, cast(float, after.radius), metric)
        )
        and ((before.sweep is None) == (after.sweep is None))
        and (
            before.sweep is None or _close(before.sweep, cast(float, after.sweep), 4.0 * ANGLE_TOL)
        )
        and before.full is after.full
    )


def _wire_scaled(
    before: WireGeometry,
    after: WireGeometry,
    scale: float,
    quant_before: DescriptorQuantization,
    quant_after: DescriptorQuantization,
) -> bool:
    return (
        before.role == after.role
        and before.semantic_winding == after.semantic_winding
        and len(before.edges) == len(after.edges)
        and all(
            left_direction == right_direction
            and _edge_scaled(left, right, scale, quant_before, quant_after)
            for (left, left_direction), (right, right_direction) in zip(
                before.edges, after.edges, strict=True
            )
        )
    )


def _face_scaled(
    before: FaceGeometry,
    after: FaceGeometry,
    scale: float,
    quant_before: DescriptorQuantization,
    quant_after: DescriptorQuantization,
) -> bool:
    metric = _order_bound(quant_before, quant_after, scale, 1)
    area = _order_bound(quant_before, quant_after, scale, 2)
    if before.kind != after.kind or len(before.parameters) != len(after.parameters):
        return False
    if before.kind == "PLANE":
        parameters = all(
            _close(source, target, 4.0 * DIRECTION_TOL)
            for source, target in zip(before.parameters[:3], after.parameters[:3], strict=True)
        ) and _close(scale * before.parameters[3], after.parameters[3], metric)
    elif before.kind == "CYLINDER":
        parameters = (
            all(
                _close(source, target, 4.0 * DIRECTION_TOL)
                for source, target in zip(before.parameters[:3], after.parameters[:3], strict=True)
            )
            and all(
                _close(scale * source, target, metric)
                for source, target in zip(
                    before.parameters[3:6], after.parameters[3:6], strict=True
                )
            )
            and _close(scale * before.parameters[6], after.parameters[6], metric)
        )
    else:
        return False
    return (
        parameters
        and _close(scale**2 * before.area, after.area, area)
        and _scaled_point(before.centroid, scale, after.centroid, metric)
        and before.material_side == after.material_side
        and len(before.wires) == len(after.wires)
        and all(
            _wire_scaled(left, right, scale, quant_before, quant_after)
            for left, right in zip(before.wires, after.wires, strict=True)
        )
    )


def _body_scaled(
    before: AcceptedOccurrenceSnapshot,
    after: AcceptedOccurrenceSnapshot,
    scale: float,
) -> bool:
    left = before.body
    right = after.body
    qleft, qright = left.quantization, right.quantization
    if (
        left.placement.frame_status != right.placement.frame_status
        or left.boundary.face_count != right.boundary.face_count
        or left.boundary.wire_count != right.boundary.wire_count
        or left.boundary.edge_occurrence_count != right.boundary.edge_occurrence_count
        or left.boundary.symmetric is not right.boundary.symmetric
        or len(left.boundary.faces) != len(right.boundary.faces)
        or len(left.boundary.incidence) != len(right.boundary.incidence)
    ):
        return False
    if not (
        _close(
            scale**3 * left.intrinsic.volume,
            right.intrinsic.volume,
            _order_bound(qleft, qright, scale, 3),
        )
        and _close(
            scale**2 * left.intrinsic.surface_area,
            right.intrinsic.surface_area,
            _order_bound(qleft, qright, scale, 2),
        )
        and all(
            _close(scale**5 * source, target, _order_bound(qleft, qright, scale, 5))
            for source, target in zip(
                left.intrinsic.principal_moments,
                right.intrinsic.principal_moments,
                strict=True,
            )
        )
        and all(
            _face_scaled(source, target, scale, qleft, qright)
            for source, target in zip(left.boundary.faces, right.boundary.faces, strict=True)
        )
    ):
        return False
    return all(
        source_occurrences == target_occurrences
        and _edge_scaled(source_edge, target_edge, scale, qleft, qright)
        for (source_edge, source_occurrences), (target_edge, target_occurrences) in zip(
            left.boundary.incidence, right.boundary.incidence, strict=True
        )
    )


def _signature_scaled(before: object, after: object, scale: float, bound: float) -> bool:
    """Compare the explicit RRP `(kind, length, ((radius, angle), ...))` schema."""

    if type(before) is not tuple or type(after) is not tuple or len(before) != len(after):
        return False
    for left, right in zip(before, after, strict=True):
        if type(left) is not tuple or type(right) is not tuple or len(left) != 3 or len(right) != 3:
            return False
        if left[0] != right[0] or not _close(scale * left[1], right[1], bound):
            return False
        if (
            type(left[2]) is not tuple
            or type(right[2]) is not tuple
            or len(left[2]) != len(right[2])
        ):
            return False
        if any(
            not _close(scale * source[0], target[0], bound)
            or not _close(source[1], target[1], 4.0 * ANGLE_TOL)
            for source, target in zip(left[2], right[2], strict=True)
        ):
            return False
    return True


def _translation_witness(
    before: AcceptedOccurrenceSnapshot, after: AcceptedOccurrenceSnapshot
) -> RigidScaleWitness | None:
    """Prove the bounded scale-one/identity-rotation relation without rematching by placement."""

    if (
        before.family != after.family
        or before.record_type != after.record_type
        or before.summary.repeat_count != after.summary.repeat_count
        or before.summary.edge_count != after.summary.edge_count
        or before.summary.axis != after.summary.axis
    ):
        return None
    if before.body.intrinsic.volume <= 0.0 or after.body.intrinsic.volume <= 0.0:
        return None
    # Schema 2 retains the raw-mass-derived characteristic scale precisely so a similarity
    # witness does not amplify error from the already-snapped public mass fact. The complete
    # volume/area/moment values are still independently required below within their stored
    # power-specific contracts.
    scale = (
        after.body.quantization.characteristic_scale / before.body.quantization.characteristic_scale
    )
    if not math.isfinite(scale) or scale <= 0.0 or not _body_scaled(before, after, scale):
        return None
    metric = _order_bound(before.body.quantization, after.body.quantization, scale, 1)
    if not _signature_scaled(
        before.summary.sector_signature, after.summary.sector_signature, scale, metric
    ) or not all(
        _face_scaled(left, right, scale, before.body.quantization, after.body.quantization)
        for left, right in zip(before.summary.defining, after.summary.defining, strict=True)
    ):
        return None
    before_centre = before.body.placement.centre_of_mass
    after_centre = after.body.placement.centre_of_mass
    translation = tuple(
        target - scale * source for source, target in zip(before_centre, after_centre, strict=True)
    )
    translation = cast(Vector3, translation)
    bound = metric
    if not all(
        _close(scale * source + delta, target, bound)
        for source, delta, target in zip(
            before.summary.centre, translation, after.summary.centre, strict=True
        )
    ):
        return None
    axis = "xyz".index(before.summary.axis)
    if any(
        not _close(scale * source + translation[axis], target, bound)
        for source, target in zip(before.summary.span, after.summary.span, strict=True)
    ):
        return None
    return RigidScaleWitness(IDENTITY_ROTATION, translation, scale)


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
        metric = _order_bound(
            before.occurrences[before_group[0]].body.quantization,
            after.occurrences[after_group[0]].body.quantization,
            witness.scale,
            1,
        )
        scale_identity = max(witness.scale, 1.0 / witness.scale) - 1.0 <= SCALE_TOL
        placement_identity = all(abs(item) <= metric for item in witness.translation)
        for left_at, right_at in occurrence_matching:
            left = before_group[left_at]
            right = after_group[right_at]
            matched_before.add(left)
            matched_after.add(right)
            relations.append(
                CorrespondenceRelation(
                    (
                        ChangeKind.UNCHANGED
                        if scale_identity and placement_identity
                        else ChangeKind.MOVED
                        if scale_identity
                        else ChangeKind.RESIZED
                    ),
                    (_ref("before", left, before),),
                    (_ref("after", right, after),),
                    None if scale_identity and placement_identity else witness,
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
