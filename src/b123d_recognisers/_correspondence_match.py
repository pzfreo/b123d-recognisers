# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Private, issuer-bound correspondence between two accepted RRP inventories."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from itertools import combinations, permutations, product
from typing import cast

from b123d_recognisers._body_geometry import (
    ANGLE_TOL,
    DESCRIPTOR_REL,
    DIRECTION_TOL,
    DescriptorQuantization,
    FaceGeometry,
    MatchingBoundaryGraph,
    MatchingCurve,
    MatchingFace,
    MatchingWire,
)
from b123d_recognisers._correspondence import (
    AcceptedOccurrenceSnapshot,
    CorrespondenceSnapshot,
    CorrespondenceSnapshotError,
    _InventoryProduct,
    _validate_snapshot,
    correspondence_snapshot,
)
from b123d_recognisers._correspondence_partition import (
    _PrismCap,
    _PrismCurve,
    _PrismFact,
    prism_fact,
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
    SPLIT = "split"
    MERGED = "merged"
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


@dataclass(slots=True)
class _MatchBudget:
    attempts: int = 0

    def charge(self) -> None:
        self.attempts += 1
        if self.attempts > MATCH_HYPOTHESIS_BUDGET:
            raise CorrespondenceMatchError("correspondence hypothesis budget is exhausted")


def _rotate(rotation: Rotation, value: Vector3) -> Vector3:
    return cast(
        Vector3,
        tuple(sum(row[column] * value[column] for column in range(3)) for row in rotation),
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
            type(value) is not float or not math.isfinite(value) for value in witness.translation
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
        or result.schema_version != 2
        or result.before_schema != 3
        or result.after_schema != 3
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
        if relation.candidate_witnesses != tuple(
            sorted(set(relation.candidate_witnesses), key=repr)
        ):
            raise CorrespondenceMatchError(
                "correspondence candidate witness roster is not canonical"
            )
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
        if relation.kind is ChangeKind.SPLIT and (
            len(relation.before_refs) != 1
            or len(relation.after_refs) < 2
            or relation.witness is None
            or relation.candidate_witnesses
        ):
            raise CorrespondenceMatchError("split correspondence relation is malformed")
        if relation.kind is ChangeKind.MERGED and (
            len(relation.before_refs) < 2
            or len(relation.after_refs) != 1
            or relation.witness is None
            or relation.candidate_witnesses
        ):
            raise CorrespondenceMatchError("merged correspondence relation is malformed")
        if relation.kind is ChangeKind.AMBIGUOUS and (
            not relation.before_refs or not relation.after_refs or relation.witness is not None
        ):
            raise CorrespondenceMatchError("ambiguous correspondence relation is malformed")
    if sorted(before_positions) != list(range(len(before.occurrences))) or sorted(
        after_positions
    ) != list(range(len(after.occurrences))):
        raise CorrespondenceMatchError("correspondence result does not cover both snapshots once")


def _metric_bound(before: DescriptorQuantization, after: DescriptorQuantization) -> float:
    return 2.0 * (before.metric_quantum + after.metric_quantum)


def _unique_bijection(candidates: tuple[tuple[int, ...], ...]) -> tuple[int, ...] | None:
    """Return one exact bijection only when no competing assignment exists."""

    if any(not row for row in candidates):
        return None
    found: list[tuple[int, ...]] = []

    def visit(at: int, used: frozenset[int], selected: tuple[int, ...]) -> None:
        if len(found) > 1:
            return
        if at == len(candidates):
            found.append(selected)
            return
        for target in candidates[at]:
            if target not in used:
                visit(at + 1, used | {target}, (*selected, target))

    visit(0, frozenset(), ())
    return found[0] if len(found) == 1 else None


def _has_bijection(candidates: tuple[tuple[int, ...], ...]) -> bool:
    def visit(at: int, used: frozenset[int]) -> bool:
        if at == len(candidates):
            return True
        return any(
            target not in used and visit(at + 1, used | {target}) for target in candidates[at]
        )

    return not any(not row for row in candidates) and visit(0, frozenset())


def _unique_exact_relations(
    before: CorrespondenceSnapshot, after: CorrespondenceSnapshot
) -> tuple[CorrespondenceRelation, ...] | None:
    """Fast-path exact values only after proving group and occurrence uniqueness."""

    if before != after:
        return None
    pair_maps: dict[tuple[int, int], tuple[int, ...] | None] = {}
    group_edges: dict[int, tuple[int, ...]] = {}
    for before_group_at, before_group in enumerate(before.body_groups):
        choices: list[int] = []
        for after_group_at, after_group in enumerate(after.body_groups):
            if len(before_group) != len(after_group):
                continue
            occurrence_candidates = tuple(
                tuple(
                    right_at
                    for right_at, right_position in enumerate(after_group)
                    if before.occurrences[left_position] == after.occurrences[right_position]
                )
                for left_position in before_group
            )
            if _has_bijection(occurrence_candidates):
                choices.append(after_group_at)
                pair_maps[(before_group_at, after_group_at)] = _unique_bijection(
                    occurrence_candidates
                )
        group_edges[before_group_at] = tuple(choices)
    relations: list[CorrespondenceRelation] = []
    for lefts, rights in _group_components(
        len(before.body_groups), len(after.body_groups), group_edges
    ):
        if len(lefts) != 1 or len(rights) != 1:
            relations.append(
                CorrespondenceRelation(
                    ChangeKind.AMBIGUOUS,
                    tuple(
                        _ref("before", position, before)
                        for group in lefts
                        for position in before.body_groups[group]
                    ),
                    tuple(
                        _ref("after", position, after)
                        for group in rights
                        for position in after.body_groups[group]
                    ),
                    None,
                    (RigidScaleWitness(IDENTITY_ROTATION, (0.0, 0.0, 0.0), 1.0),),
                )
            )
            continue
        left, right = lefts[0], rights[0]
        mapping = pair_maps[(left, right)]
        if mapping is None:
            relations.append(
                CorrespondenceRelation(
                    ChangeKind.AMBIGUOUS,
                    tuple(
                        _ref("before", position, before) for position in before.body_groups[left]
                    ),
                    tuple(_ref("after", position, after) for position in after.body_groups[right]),
                    None,
                    (RigidScaleWitness(IDENTITY_ROTATION, (0.0, 0.0, 0.0), 1.0),),
                )
            )
            continue
        relations.extend(
            CorrespondenceRelation(
                ChangeKind.UNCHANGED,
                (_ref("before", before.body_groups[left][left_at], before),),
                (_ref("after", after.body_groups[right][right_at], after),),
                None,
            )
            for left_at, right_at in enumerate(mapping)
        )
    return tuple(relations)


def _close(left: float, right: float, bound: float) -> bool:
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= bound


def _scale_is_identity(scale: float) -> bool:
    return math.isfinite(scale) and scale > 0.0 and max(scale, 1.0 / scale) <= 1.0 + SCALE_TOL


def _scaled_point(left: Vector3, scale: float, right: Vector3, bound: float) -> bool:
    residuals = tuple(scale * source - target for source, target in zip(left, right, strict=True))
    return (
        all(math.isfinite(item) for item in residuals)
        and sum(item * item for item in residuals) <= bound * bound
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


def _direction_close(left: Vector3, right: Vector3) -> bool:
    return _scaled_point(left, 1.0, right, 4.0 * DIRECTION_TOL)


def _canonical_axis(value: Vector3) -> tuple[Vector3, int]:
    for component in value:
        if abs(component) > DIRECTION_TOL:
            sign = 1 if component > 0.0 else -1
            return cast(Vector3, tuple(sign * item for item in value)), sign
    raise CorrespondenceMatchError("transformed analytic axis is degenerate")


def _plane_basis(normal: Vector3) -> tuple[Vector3, Vector3]:
    axes: tuple[Vector3, ...] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    reference = min(
        axes,
        key=lambda axis: abs(sum(a * n for a, n in zip(axis, normal, strict=True))),
    )
    projection = tuple(
        axis - sum(a * n for a, n in zip(reference, normal, strict=True)) * component
        for axis, component in zip(reference, normal, strict=True)
    )
    length = math.sqrt(sum(component * component for component in projection))
    if length <= DIRECTION_TOL:
        raise CorrespondenceMatchError("transformed analytic basis is degenerate")
    u = cast(Vector3, tuple(component / length for component in projection))
    v = (
        normal[1] * u[2] - normal[2] * u[1],
        normal[2] * u[0] - normal[0] * u[2],
        normal[0] * u[1] - normal[1] * u[0],
    )
    return u, v


def _enumerate_bijections(
    candidates: tuple[tuple[int, ...], ...], budget: _MatchBudget
) -> tuple[tuple[int, ...], ...]:
    if any(not values for values in candidates):
        return ()
    found: list[tuple[int, ...]] = []

    def visit(at: int, used: frozenset[int], chosen: tuple[int, ...]) -> None:
        if at == len(candidates):
            found.append(chosen)
            return
        for target in candidates[at]:
            budget.charge()
            if target not in used:
                visit(at + 1, used | {target}, (*chosen, target))

    visit(0, frozenset(), ())
    return tuple(found)


def _point_similarity(
    before: Vector3,
    after: Vector3,
    rotation: Rotation,
    scale: float,
    bound: float,
) -> bool:
    return _scaled_point(_rotate(rotation, before), scale, after, bound)


def _curve_similarity(
    before: MatchingCurve,
    after: MatchingCurve,
    vertex_map: tuple[int, ...],
    rotation: Rotation,
    scale: float,
    bound: float,
) -> int | None:
    if before.kind != after.kind or before.full is not after.full:
        return None
    if not _close(scale * before.length, after.length, bound):
        return None
    presentation = 1
    if before.vertices is None:
        if after.vertices is not None:
            return None
    else:
        if after.vertices is None:
            return None
        mapped = (vertex_map[before.vertices[0]], vertex_map[before.vertices[1]])
        if mapped == after.vertices:
            presentation = 1
        elif tuple(reversed(mapped)) == after.vertices:
            presentation = -1
        else:
            return None
    if before.kind == "LINE":
        return presentation if after.kind == "LINE" else None
    if (
        before.centre is None
        or after.centre is None
        or before.axis is None
        or after.axis is None
        or before.radius is None
        or after.radius is None
        or before.sweep is None
        or after.sweep is None
        or not _point_similarity(before.centre, after.centre, rotation, scale, bound)
        or not _close(scale * before.radius, after.radius, bound)
    ):
        return None
    transformed_axis, axis_sign = _canonical_axis(_rotate(rotation, before.axis))
    if not _direction_close(transformed_axis, after.axis):
        return None
    if before.full:
        if not _close(after.sweep, 2.0 * math.pi, 4.0 * ANGLE_TOL):
            return None
        return axis_sign
    expected_sweep = before.sweep * axis_sign * presentation
    if not _close(expected_sweep, after.sweep, 4.0 * ANGLE_TOL):
        return None
    return presentation


def _face_similarity(
    before: MatchingFace,
    after: MatchingFace,
    rotation: Rotation,
    scale: float,
    metric: float,
    area_bound: float,
) -> tuple[int, Vector3] | None:
    if (
        before.kind != after.kind
        or len(before.parameters) != len(after.parameters)
        or not _close(scale**2 * before.area, after.area, area_bound)
        or not _point_similarity(before.centroid, after.centroid, rotation, scale, metric)
        or len(before.wires) != len(after.wires)
    ):
        return None
    transformed_axis, gauge = _canonical_axis(
        _rotate(rotation, cast(Vector3, before.parameters[:3]))
    )
    if not _direction_close(transformed_axis, cast(Vector3, after.parameters[:3])):
        return None
    if before.kind == "PLANE":
        if (
            not _close(gauge * scale * before.parameters[3], after.parameters[3], metric)
            or after.material_side != gauge * before.material_side
        ):
            return None
    elif before.kind == "CYLINDER":
        if (
            not _point_similarity(
                cast(Vector3, before.parameters[3:6]),
                cast(Vector3, after.parameters[3:6]),
                rotation,
                scale,
                metric,
            )
            or not _close(scale * before.parameters[6], after.parameters[6], metric)
            or after.material_side != before.material_side
        ):
            return None
    else:
        return None
    return gauge, transformed_axis


def _parameter_matches(
    vertex: Vector3,
    parameter: tuple[float, float],
    face: MatchingFace,
    metric: float,
) -> bool:
    axis = cast(Vector3, face.parameters[:3])
    u, v = _plane_basis(axis)
    if face.kind == "PLANE":
        origin = cast(Vector3, tuple(face.parameters[3] * item for item in axis))
        delta = cast(
            Vector3,
            tuple(item - offset for item, offset in zip(vertex, origin, strict=True)),
        )
        expected = (
            sum(a * b for a, b in zip(delta, u, strict=True)),
            sum(a * b for a, b in zip(delta, v, strict=True)),
        )
        return all(
            _close(left, right, 4.0 * metric)
            for left, right in zip(expected, parameter, strict=True)
        )
    axis_point = cast(Vector3, face.parameters[3:6])
    relative = cast(
        Vector3,
        tuple(item - offset for item, offset in zip(vertex, axis_point, strict=True)),
    )
    z = sum(a * b for a, b in zip(relative, axis, strict=True))
    radial = cast(
        Vector3,
        tuple(item - z * normal for item, normal in zip(relative, axis, strict=True)),
    )
    theta = math.atan2(
        sum(a * b for a, b in zip(radial, v, strict=True)),
        sum(a * b for a, b in zip(radial, u, strict=True)),
    )
    theta_residual = parameter[0] - theta
    turns = round(theta_residual / (2.0 * math.pi))
    return abs(theta_residual - turns * 2.0 * math.pi) <= 4.0 * ANGLE_TOL and _close(
        z, parameter[1], 4.0 * metric
    )


def _wire_alignments(
    before: MatchingWire,
    after: MatchingWire,
    before_face: MatchingFace,
    after_face: MatchingFace,
    vertex_map: tuple[int, ...],
    curve_map: tuple[int, ...],
    curve_signs: tuple[int, ...],
    after_vertices: tuple[Vector3, ...],
    face_gauge: int,
    metric: float,
    budget: _MatchBudget,
    presentations: tuple[int, ...] = (1, -1),
) -> tuple[tuple[int, ...], ...]:
    if before.role != after.role or len(before.cycle) != len(after.cycle):
        return ()
    size = len(before.cycle)
    results: list[tuple[int, ...]] = []
    for presentation in presentations:
        expected_winding = (
            face_gauge * presentation * before.theta_winding
            if before_face.kind == "CYLINDER"
            else 0
        )
        if after.theta_winding != expected_winding:
            continue
        for shift in range(size):
            budget.charge()
            occurrence_map: list[int] = []
            valid = True
            for before_at, left in enumerate(before.cycle):
                after_at = (shift + presentation * before_at) % size
                right = after.cycle[after_at]
                sign = curve_signs[left.curve] * presentation
                if right.curve != curve_map[left.curve] or right.direction != left.direction * sign:
                    valid = False
                    break
                if left.start is None:
                    if right.start is not None or right.end is not None:
                        valid = False
                        break
                else:
                    if right.start is None or right.end is None or left.end is None:
                        valid = False
                        break
                    source_start = left.start if presentation == 1 else left.end
                    source_end = left.end if presentation == 1 else left.start
                    if (
                        source_start.vertex is None
                        or source_end.vertex is None
                        or right.start.vertex is None
                        or right.end.vertex is None
                    ):
                        valid = False
                        break
                    if (
                        right.start.vertex != vertex_map[source_start.vertex]
                        or right.end.vertex != vertex_map[source_end.vertex]
                    ):
                        valid = False
                        break
                    if not _parameter_matches(
                        after_vertices[right.start.vertex],
                        right.start.parameter,
                        after_face,
                        metric,
                    ) or not _parameter_matches(
                        after_vertices[right.end.vertex],
                        right.end.parameter,
                        after_face,
                        metric,
                    ):
                        valid = False
                        break
                occurrence_map.append(after_at)
            if valid:
                results.append(tuple(occurrence_map))
    return tuple(results)


def _wire_map_candidates(
    before_face: MatchingFace,
    after_face: MatchingFace,
    vertex_map: tuple[int, ...],
    curve_map: tuple[int, ...],
    curve_signs: tuple[int, ...],
    after_vertices: tuple[Vector3, ...],
    face_gauge: int,
    metric: float,
    budget: _MatchBudget,
    presentations: tuple[int, ...],
) -> tuple[tuple[tuple[int, tuple[int, ...]], ...], ...]:
    """Enumerate every target-wire/alignment bijection for one face."""

    choices: list[tuple[tuple[int, tuple[int, ...]], ...]] = []
    for source_wire in before_face.wires:
        row: list[tuple[int, tuple[int, ...]]] = []
        for target_wire_at, target_wire in enumerate(after_face.wires):
            for alignment in _wire_alignments(
                source_wire,
                target_wire,
                before_face,
                after_face,
                vertex_map,
                curve_map,
                curve_signs,
                after_vertices,
                face_gauge,
                metric,
                budget,
                presentations,
            ):
                row.append((target_wire_at, alignment))
        choices.append(tuple(row))

    results: list[tuple[tuple[int, tuple[int, ...]], ...]] = []

    def visit(
        source_wire_at: int, used: frozenset[int], selected: list[tuple[int, tuple[int, ...]]]
    ) -> None:
        budget.charge()
        if source_wire_at == len(choices):
            results.append(tuple(selected))
            return
        for target_wire_at, alignment in choices[source_wire_at]:
            if target_wire_at in used:
                continue
            selected.append((target_wire_at, alignment))
            visit(source_wire_at + 1, used | {target_wire_at}, selected)
            selected.pop()

    visit(0, frozenset(), [])
    return tuple(results)


def _matching_graph_similarity_search(
    before: MatchingBoundaryGraph,
    after: MatchingBoundaryGraph,
    rotation: Rotation,
    scale: float,
    quant_before: DescriptorQuantization,
    quant_after: DescriptorQuantization,
    budget: _MatchBudget,
    presentations: tuple[int, ...],
) -> bool:
    if (
        before.face_count != after.face_count
        or before.wire_count != after.wire_count
        or before.edge_occurrence_count != after.edge_occurrence_count
        or len(before.vertices) != len(after.vertices)
        or len(before.curves) != len(after.curves)
        or len(before.faces) != len(after.faces)
    ):
        return False
    metric = _order_bound(quant_before, quant_after, scale, 1)
    area_bound = _order_bound(quant_before, quant_after, scale, 2)
    transformed_vertices = tuple(_rotate(rotation, source) for source in before.vertices)
    cells: dict[tuple[int, int, int], list[int]] = {}
    for target, value in enumerate(after.vertices):
        key = cast(
            tuple[int, int, int],
            tuple(math.floor(component / metric) for component in value),
        )
        cells.setdefault(key, []).append(target)
    vertex_candidates = tuple(
        tuple(
            target
            for dx, dy, dz in product((-1, 0, 1), repeat=3)
            for target in cells.get(
                (
                    math.floor(scale * source[0] / metric) + dx,
                    math.floor(scale * source[1] / metric) + dy,
                    math.floor(scale * source[2] / metric) + dz,
                ),
                (),
            )
            for value in (after.vertices[target],)
            if _scaled_point(source, scale, value, metric)
        )
        for source in transformed_vertices
    )
    for vertex_map in _enumerate_bijections(vertex_candidates, budget):
        curve_options: list[tuple[tuple[int, int], ...]] = []
        for source in before.curves:
            choices = []
            for target, target_curve_value in enumerate(after.curves):
                sign = _curve_similarity(
                    source,
                    target_curve_value,
                    vertex_map,
                    rotation,
                    scale,
                    metric,
                )
                if sign is not None:
                    choices.append((target, sign))
            curve_options.append(tuple(choices))
        curve_candidates = tuple(tuple(target for target, _sign in row) for row in curve_options)
        for curve_map in _enumerate_bijections(curve_candidates, budget):
            curve_signs = tuple(
                next(sign for target, sign in curve_options[index] if target == curve_map[index])
                for index in range(len(curve_map))
            )
            face_options: list[tuple[tuple[int, int], ...]] = []
            for source_face_value in before.faces:
                choices = []
                for target, target_face_value in enumerate(after.faces):
                    transformed = _face_similarity(
                        source_face_value,
                        target_face_value,
                        rotation,
                        scale,
                        metric,
                        area_bound,
                    )
                    if transformed is not None:
                        choices.append((target, transformed[0]))
                face_options.append(tuple(choices))
            face_candidates = tuple(tuple(target for target, _gauge in row) for row in face_options)
            for face_map in _enumerate_bijections(face_candidates, budget):
                face_gauges = tuple(
                    next(
                        gauge for target, gauge in face_options[index] if target == face_map[index]
                    )
                    for index in range(len(face_map))
                )
                face_wire_maps: list[tuple[tuple[tuple[int, tuple[int, ...]], ...], ...]] = []
                for source_face_at, source_face in enumerate(before.faces):
                    target_face_at = face_map[source_face_at]
                    target_face = after.faces[target_face_at]
                    candidates = _wire_map_candidates(
                        source_face,
                        target_face,
                        vertex_map,
                        curve_map,
                        curve_signs,
                        after.vertices,
                        face_gauges[source_face_at],
                        metric,
                        budget,
                        presentations,
                    )
                    if not candidates:
                        break
                    face_wire_maps.append(candidates)
                if len(face_wire_maps) != len(before.faces):
                    continue
                for selected_by_face in product(*face_wire_maps):
                    budget.charge()
                    target_incidence = dict(after.incidence)
                    valid = True
                    for source_curve, source_occurrences in before.incidence:
                        mapped_occurrences = []
                        for (
                            source_face_index,
                            source_wire_index,
                            source_occurrence,
                        ) in source_occurrences:
                            target_face_index = face_map[source_face_index]
                            target_wire_index, occurrence_map = selected_by_face[source_face_index][
                                source_wire_index
                            ]
                            mapped_occurrences.append(
                                (
                                    target_face_index,
                                    target_wire_index,
                                    occurrence_map[source_occurrence],
                                )
                            )
                        if tuple(sorted(mapped_occurrences)) != target_incidence.get(
                            curve_map[source_curve]
                        ):
                            valid = False
                            break
                    if valid:
                        return True
    return False


def _matching_graph_similarity(
    before: MatchingBoundaryGraph,
    after: MatchingBoundaryGraph,
    rotation: Rotation,
    scale: float,
    quant_before: DescriptorQuantization,
    quant_after: DescriptorQuantization,
    budget: _MatchBudget,
) -> bool:
    return _matching_graph_similarity_search(
        before,
        after,
        rotation,
        scale,
        quant_before,
        quant_after,
        budget,
        (1, -1),
    )


def _body_similarity(
    before: AcceptedOccurrenceSnapshot,
    after: AcceptedOccurrenceSnapshot,
    rotation: Rotation,
    scale: float,
    budget: _MatchBudget,
) -> bool:
    left = before.body
    right = after.body
    qleft, qright = left.quantization, right.quantization
    return (
        left.placement.frame_status == right.placement.frame_status
        and _close(
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
        and _matching_graph_similarity(
            before.matching_boundary,
            after.matching_boundary,
            rotation,
            scale,
            qleft,
            qright,
            budget,
        )
    )


def _defining_face_similarity(
    before: FaceGeometry,
    after: FaceGeometry,
    rotation: Rotation,
    scale: float,
    quant_before: DescriptorQuantization,
    quant_after: DescriptorQuantization,
) -> bool:
    metric = _order_bound(quant_before, quant_after, scale, 1)
    area = _order_bound(quant_before, quant_after, scale, 2)
    if before.kind != after.kind or len(before.parameters) != len(after.parameters):
        return False
    axis, gauge = _canonical_axis(_rotate(rotation, cast(Vector3, before.parameters[:3])))
    if not _direction_close(axis, cast(Vector3, after.parameters[:3])):
        return False
    if before.kind == "PLANE":
        parameters = (
            _close(gauge * scale * before.parameters[3], after.parameters[3], metric)
            and after.material_side == gauge * before.material_side
        )
    elif before.kind == "CYLINDER":
        parameters = (
            _point_similarity(
                cast(Vector3, before.parameters[3:6]),
                cast(Vector3, after.parameters[3:6]),
                rotation,
                scale,
                metric,
            )
            and _close(scale * before.parameters[6], after.parameters[6], metric)
            and after.material_side == before.material_side
        )
    else:
        return False
    return (
        parameters
        and _close(scale**2 * before.area, after.area, area)
        and _point_similarity(before.centroid, after.centroid, rotation, scale, metric)
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


def _similarity_witness(
    before: AcceptedOccurrenceSnapshot,
    after: AcceptedOccurrenceSnapshot,
    rotation: Rotation,
    budget: _MatchBudget,
) -> RigidScaleWitness | None:
    """Prove one complete proper similarity without using canonical tuple position."""

    if (
        before.family != after.family
        or before.record_type != after.record_type
        or before.summary.repeat_count != after.summary.repeat_count
        or before.summary.edge_count != after.summary.edge_count
    ):
        return None
    if before.body.intrinsic.volume <= 0.0 or after.body.intrinsic.volume <= 0.0:
        return None
    # Schema 3 retains the raw-mass-derived characteristic scale precisely so a similarity
    # witness does not amplify error from the already-snapped public mass fact. The complete
    # volume/area/moment values are still independently required below within their stored
    # power-specific contracts.
    scale = (
        after.body.quantization.characteristic_scale / before.body.quantization.characteristic_scale
    )
    if not math.isfinite(scale) or scale <= 0.0:
        return None
    metric = _order_bound(before.body.quantization, after.body.quantization, scale, 1)
    if not _signature_scaled(
        before.summary.sector_signature, after.summary.sector_signature, scale, metric
    ):
        return None
    before_centre = before.body.placement.centre_of_mass
    after_centre = after.body.placement.centre_of_mass
    rotated_centre = _rotate(rotation, before_centre)
    translation = tuple(
        target - scale * source for source, target in zip(rotated_centre, after_centre, strict=True)
    )
    translation = cast(Vector3, translation)
    bound = metric
    if not _scaled_point(
        _affine_point(rotation, translation, scale, before.summary.centre),
        1.0,
        after.summary.centre,
        bound,
    ):
        return None
    source_axis = "xyz".index(before.summary.axis)
    transformed_axis = _rotate(
        rotation,
        cast(Vector3, tuple(1.0 if index == source_axis else 0.0 for index in range(3))),
    )
    target_axis = next(
        (index for index, value in enumerate(transformed_axis) if abs(value) > 0.5), None
    )
    if target_axis is None or after.summary.axis != "xyz"[target_axis]:
        return None
    source_endpoints = []
    for at in before.summary.span:
        point = list(before.summary.centre)
        point[source_axis] = at
        source_endpoints.append(
            _affine_point(rotation, translation, scale, cast(Vector3, tuple(point)))
        )
    transformed_span = tuple(sorted(point[target_axis] for point in source_endpoints))
    if any(
        not _close(source, target, bound)
        for source, target in zip(transformed_span, after.summary.span, strict=True)
    ):
        return None
    defining_candidates = tuple(
        tuple(
            target
            for target, right in enumerate(after.summary.defining)
            if _defining_face_similarity(
                left,
                right,
                rotation,
                scale,
                before.body.quantization,
                after.body.quantization,
            )
        )
        for left in before.summary.defining
    )
    if not _enumerate_bijections(defining_candidates, budget) or not _body_similarity(
        before, after, rotation, scale, budget
    ):
        return None
    return RigidScaleWitness(rotation, translation, scale)


def _similarity_witnesses(
    before: AcceptedOccurrenceSnapshot,
    after: AcceptedOccurrenceSnapshot,
    budget: _MatchBudget,
) -> tuple[RigidScaleWitness, ...]:
    # Exact values establish an identity witness without reinterpreting their
    # already-issued schema-3 graph. Group and occurrence assignment uniqueness is
    # still proved by the global matcher below.
    if before == after:
        return (RigidScaleWitness(IDENTITY_ROTATION, (0.0, 0.0, 0.0), 1.0),)
    identity = _similarity_witness(before, after, IDENTITY_ROTATION, budget)
    if identity is not None:
        metric = _order_bound(before.body.quantization, after.body.quantization, identity.scale, 1)
        if max(identity.scale, 1.0 / identity.scale) - 1.0 <= SCALE_TOL and _scaled_point(
            identity.translation, 1.0, (0.0, 0.0, 0.0), metric
        ):
            return (identity,)
    found = []
    if identity is not None:
        found.append(identity)
    for rotation in PROPER_ROTATIONS:
        if rotation == IDENTITY_ROTATION:
            continue
        witness = _similarity_witness(before, after, rotation, budget)
        if witness is not None and witness not in found:
            found.append(witness)
    return tuple(found)


def _maximum_matchings(
    left_count: int,
    right_count: int,
    edges: dict[int, tuple[int, ...]],
    budget: _MatchBudget | None = None,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Enumerate every maximum-cardinality assignment without a first-win tie break."""

    complete: list[tuple[tuple[int, int], ...]] = []
    generated = 0

    def visit(left: int, used: frozenset[int], chosen: tuple[tuple[int, int], ...]) -> None:
        nonlocal generated
        if left == left_count:
            generated += 1
            if budget is not None:
                budget.charge()
            elif generated > MATCH_HYPOTHESIS_BUDGET:
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


def _maximum_weight_matchings(
    lefts: tuple[int, ...],
    rights: tuple[int, ...],
    edges: dict[int, tuple[int, ...]],
    weights: dict[tuple[int, int], int],
    budget: _MatchBudget,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    complete: list[tuple[tuple[int, int], ...]] = []

    def visit(at: int, used: frozenset[int], chosen: tuple[tuple[int, int], ...]) -> None:
        budget.charge()
        if at == len(lefts):
            complete.append(chosen)
            return
        left = lefts[at]
        visit(at + 1, used, chosen)
        for right in edges.get(left, ()):
            if right in rights and right not in used:
                visit(at + 1, used | {right}, (*chosen, (left, right)))

    visit(0, frozenset(), ())
    maximum = max((sum(weights[edge] for edge in matching) for matching in complete), default=0)
    return tuple(
        matching for matching in complete if sum(weights[edge] for edge in matching) == maximum
    )


def _group_components(
    before_count: int,
    after_count: int,
    edges: dict[int, tuple[int, ...]],
) -> tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]:
    left_neighbours = {left: set(values) for left, values in edges.items()}
    right_neighbours: dict[int, set[int]] = {right: set() for right in range(after_count)}
    for left, neighbour_rights in left_neighbours.items():
        for right in neighbour_rights:
            right_neighbours[right].add(left)
    pending_left = set(range(before_count))
    pending_right = set(range(after_count))
    components = []
    while pending_left or pending_right:
        if pending_left:
            seed_side, seed = "left", min(pending_left)
        else:
            seed_side, seed = "right", min(pending_right)
        lefts: set[int] = set()
        rights: set[int] = set()
        frontier = [(seed_side, seed)]
        while frontier:
            side, value = frontier.pop()
            if side == "left":
                if value in lefts:
                    continue
                lefts.add(value)
                frontier.extend(("right", item) for item in left_neighbours[value])
            else:
                if value in rights:
                    continue
                rights.add(value)
                frontier.extend(("left", item) for item in right_neighbours[value])
        pending_left.difference_update(lefts)
        pending_right.difference_update(rights)
        components.append((tuple(sorted(lefts)), tuple(sorted(rights))))
    return tuple(components)


_GroupHypothesis = tuple[tuple[tuple[int, int], ...], RigidScaleWitness]


def _group_similarity_hypotheses(
    before: CorrespondenceSnapshot,
    after: CorrespondenceSnapshot,
    budget: _MatchBudget,
) -> tuple[
    dict[int, tuple[int, ...]],
    dict[tuple[int, int], tuple[_GroupHypothesis, ...]],
    dict[tuple[int, int], int],
]:
    """Build the complete reusable F6b1 body-group hypothesis authority."""

    group_edges: dict[int, tuple[int, ...]] = {}
    group_hypotheses: dict[tuple[int, int], tuple[_GroupHypothesis, ...]] = {}
    weights: dict[tuple[int, int], int] = {}
    witness_cache: list[
        tuple[
            AcceptedOccurrenceSnapshot,
            AcceptedOccurrenceSnapshot,
            tuple[RigidScaleWitness, ...],
        ]
    ] = []
    for before_group_at, before_group in enumerate(before.body_groups):
        compatible_groups: list[int] = []
        for after_group_at, after_group in enumerate(after.body_groups):
            occurrence_edges: dict[int, tuple[int, ...]] = {}
            witnesses: dict[tuple[int, int], tuple[RigidScaleWitness, ...]] = {}
            for left_at, left_position in enumerate(before_group):
                right_choices: list[int] = []
                for right_at, right_position in enumerate(after_group):
                    pair = (
                        before.occurrences[left_position],
                        after.occurrences[right_position],
                    )
                    pair_witnesses = next(
                        (
                            cached
                            for cached_before, cached_after, cached in witness_cache
                            if cached_before == pair[0] and cached_after == pair[1]
                        ),
                        None,
                    )
                    if pair_witnesses is None:
                        pair_witnesses = _similarity_witnesses(*pair, budget)
                        witness_cache.append((*pair, pair_witnesses))
                    if pair_witnesses:
                        right_choices.append(right_at)
                        witnesses[(left_at, right_at)] = pair_witnesses
                occurrence_edges[left_at] = tuple(right_choices)
            matchings = _maximum_matchings(
                len(before_group), len(after_group), occurrence_edges, budget
            )
            semantic_hypotheses: list[_GroupHypothesis] = []
            maximum = max((len(matching) for matching in matchings), default=0)
            for matching in matchings:
                if not matching:
                    continue
                shared = set(witnesses[matching[0]])
                for edge in matching[1:]:
                    shared.intersection_update(witnesses[edge])
                semantic_hypotheses.extend((matching, witness) for witness in shared)
            if semantic_hypotheses:
                compatible_groups.append(after_group_at)
                group_hypotheses[(before_group_at, after_group_at)] = tuple(semantic_hypotheses)
                weights[(before_group_at, after_group_at)] = maximum
        group_edges[before_group_at] = tuple(compatible_groups)
    return group_edges, group_hypotheses, weights


def _similarity_relations(
    before: CorrespondenceSnapshot,
    after: CorrespondenceSnapshot,
    budget: _MatchBudget,
) -> tuple[CorrespondenceRelation, ...] | None:
    """Stage group-first proper-similarity relations under one shared witness per body."""

    group_edges, group_hypotheses, weights = _group_similarity_hypotheses(before, after, budget)
    relations: list[CorrespondenceRelation] = []

    def ambiguity(lefts: tuple[int, ...], rights: tuple[int, ...]) -> CorrespondenceRelation:
        candidate_witnesses = tuple(
            sorted(
                {
                    witness
                    for edge in weights
                    if edge[0] in lefts and edge[1] in rights
                    for _matching, witness in group_hypotheses[edge]
                },
                key=repr,
            )
        )
        return CorrespondenceRelation(
            ChangeKind.AMBIGUOUS,
            tuple(
                _ref("before", position, before)
                for group in lefts
                for position in before.body_groups[group]
            ),
            tuple(
                _ref("after", position, after)
                for group in rights
                for position in after.body_groups[group]
            ),
            None,
            candidate_witnesses,
        )

    for lefts, component_rights in _group_components(
        len(before.body_groups), len(after.body_groups), group_edges
    ):
        if not component_rights:
            relations.extend(
                CorrespondenceRelation(
                    ChangeKind.REMOVED,
                    (_ref("before", position, before),),
                    (),
                    None,
                )
                for group in lefts
                for position in before.body_groups[group]
            )
            continue
        if not lefts:
            relations.extend(
                CorrespondenceRelation(
                    ChangeKind.ADDED,
                    (),
                    (_ref("after", position, after),),
                    None,
                )
                for group in component_rights
                for position in after.body_groups[group]
            )
            continue
        # F6b1 never distributes one body group across several alternatives. Any
        # competing group edge makes the complete connected component ambiguous,
        # irrespective of occurrence-count weight.
        right_degrees = {
            right: sum(right in group_edges[left] for left in lefts) for right in component_rights
        }
        if any(
            sum(right in component_rights for right in group_edges[left]) > 1 for left in lefts
        ) or any(degree > 1 for degree in right_degrees.values()):
            relations.append(ambiguity(lefts, component_rights))
            continue
        group_matchings = _maximum_weight_matchings(
            lefts, component_rights, group_edges, weights, budget
        )
        semantic_solutions = []
        for group_matching in group_matchings:
            choices = tuple(group_hypotheses[edge] for edge in group_matching)
            for selected in product(*choices):
                budget.charge()
                semantic_solutions.append((group_matching, selected))
        if len(semantic_solutions) != 1:
            relations.append(ambiguity(lefts, component_rights))
            continue
        group_matching, selected = semantic_solutions[0]
        selected_by_edge = dict(zip(group_matching, selected, strict=True))
        matched_before: set[int] = set()
        matched_after: set[int] = set()
        for before_group_at, after_group_at in group_matching:
            occurrence_matching, witness = selected_by_edge[(before_group_at, after_group_at)]
            before_group = before.body_groups[before_group_at]
            after_group = after.body_groups[after_group_at]
            metric = _order_bound(
                before.occurrences[before_group[0]].body.quantization,
                after.occurrences[after_group[0]].body.quantization,
                witness.scale,
                1,
            )
            scale_identity = _scale_is_identity(witness.scale)
            placement_identity = witness.rotation == IDENTITY_ROTATION and _scaled_point(
                witness.translation, 1.0, (0.0, 0.0, 0.0), metric
            )
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
        component_before = {position for group in lefts for position in before.body_groups[group]}
        component_after = {
            position for group in component_rights for position in after.body_groups[group]
        }
        relations.extend(
            CorrespondenceRelation(
                ChangeKind.REMOVED, (_ref("before", position, before),), (), None
            )
            for position in sorted(component_before - matched_before)
        )
        relations.extend(
            CorrespondenceRelation(ChangeKind.ADDED, (), (_ref("after", position, after),), None)
            for position in sorted(component_after - matched_after)
        )
    return tuple(sorted(relations, key=_relation_key))


def _axis_vector(axis: str) -> Vector3:
    at = "xyz".index(axis)
    return cast(Vector3, tuple(1.0 if index == at else 0.0 for index in range(3)))


def _normalize_partition_translation(translation: Vector3, bound: float) -> Vector3:
    """Canonicalize only a whole translation proven observationally zero."""

    return (
        (0.0, 0.0, 0.0) if sum(value * value for value in translation) <= bound**2 else translation
    )


def _prism_curve_similarity(
    before: _PrismCurve,
    after: _PrismCurve,
    before_face: MatchingFace,
    after_face: MatchingFace,
    rotation: Rotation,
    scale: float,
    target_axis_at: int,
    metric: float,
    presentation: int,
    material_factor: int,
) -> bool:
    if (
        before.kind != after.kind
        or before.full != after.full
        or not _close(scale * before.length, after.length, metric)
        or (before.radius is None) != (after.radius is None)
        or (
            before.radius is not None
            and after.radius is not None
            and not _close(scale * before.radius, after.radius, metric)
        )
    ):
        return False
    transverse = tuple(at for at in range(3) if at != target_axis_at)

    def parameters_match(curve: _PrismCurve, face: MatchingFace) -> bool:
        if curve.start is None or curve.end is None:
            return curve.start_parameter is None and curve.end_parameter is None
        if curve.start_parameter is None or curve.end_parameter is None:
            return False
        return _parameter_matches(
            curve.start, curve.start_parameter, face, metric
        ) and _parameter_matches(
            curve.end,
            curve.end_parameter,
            face,
            metric,
        )

    if not parameters_match(before, before_face) or not parameters_match(after, after_face):
        return False

    def point_matches(left: Vector3 | None, right: Vector3 | None) -> bool:
        if left is None or right is None:
            return left is right
        transformed = _rotate(rotation, left)
        return sum((scale * transformed[at] - right[at]) ** 2 for at in transverse) <= metric**2

    expected_start, expected_end = (
        (before.start, before.end) if presentation == 1 else (before.end, before.start)
    )
    if not point_matches(expected_start, after.start) or not point_matches(expected_end, after.end):
        return False
    curve_presentation = 1
    if before.start is not None and before.end is not None:
        before_curve_start, before_curve_end = (
            (before.start, before.end) if before.direction == 1 else (before.end, before.start)
        )
        after_curve_start, after_curve_end = (
            (after.start, after.end) if after.direction == 1 else (after.end, after.start)
        )
        if point_matches(before_curve_start, after_curve_start) and point_matches(
            before_curve_end, after_curve_end
        ):
            curve_presentation = 1
        elif point_matches(before_curve_start, after_curve_end) and point_matches(
            before_curve_end, after_curve_start
        ):
            curve_presentation = -1
        else:
            return False
    if not point_matches(before.centre, after.centre):
        return False
    if before.axis is None or after.axis is None:
        if (before.axis is None) != (after.axis is None):
            return False
        axis_sign = 1
    else:
        transformed_axis, axis_sign = _canonical_axis(_rotate(rotation, before.axis))
        if not _direction_close(transformed_axis, after.axis):
            return False
    if before.sweep is None or after.sweep is None:
        if before.sweep is not after.sweep:
            return False
    elif before.full:
        if not _close(after.sweep, 2.0 * math.pi, 4.0 * ANGLE_TOL):
            return False
    elif not _close(
        before.sweep * axis_sign * curve_presentation,
        after.sweep,
        4.0 * ANGLE_TOL,
    ):
        return False
    expected_direction = before.direction * presentation * curve_presentation
    if before.full:
        expected_direction *= axis_sign
    return after.direction == expected_direction


def _prism_cap_similarity(
    before: _PrismCap,
    after: _PrismCap,
    rotation: Rotation,
    scale: float,
    target_axis_at: int,
    metric: float,
    area_bound: float,
    budget: _MatchBudget,
    *,
    material_factor: int = 1,
) -> bool:
    transformed_normal, gauge = _canonical_axis(
        _rotate(rotation, cast(Vector3, before.face.parameters[:3]))
    )
    if (
        after.face.kind != "PLANE"
        or not _direction_close(transformed_normal, cast(Vector3, after.face.parameters[:3]))
        or after.face.material_side != material_factor * gauge * before.face.material_side
        or not _close(scale**2 * before.face.area, after.face.area, area_bound)
        or len(before.section_curves) != len(after.section_curves)
    ):
        return False
    size = len(before.section_curves)
    for presentation in (1, -1):
        if after.theta_winding != before.theta_winding * presentation * gauge:
            continue
        source = (
            before.section_curves if presentation == 1 else tuple(reversed(before.section_curves))
        )
        for shift in range(size):
            budget.charge()
            rotated = source[shift:] + source[:shift]
            if all(
                _prism_curve_similarity(
                    left,
                    right,
                    before.face,
                    after.face,
                    rotation,
                    scale,
                    target_axis_at,
                    metric,
                    presentation,
                    material_factor,
                )
                for left, right in zip(rotated, after.section_curves, strict=True)
            ):
                return True
    return False


def _canonicalize_partition_witnesses(
    witnesses: tuple[RigidScaleWitness, ...],
    equivalence_bound: float,
    budget: _MatchBudget,
) -> tuple[RigidScaleWitness, ...]:
    """Collapse only complete observational cliques to their convex barycentre."""

    canonical: list[RigidScaleWitness] = []
    for rotation in PROPER_ROTATIONS:
        roster = [witness for witness in witnesses if witness.rotation == rotation]
        if not roster:
            continue
        pairwise_equivalent = True
        for left, right in combinations(roster, 2):
            budget.charge()
            if math.dist(left.translation, right.translation) > equivalence_bound:
                pairwise_equivalent = False
        if pairwise_equivalent:
            translation = cast(
                Vector3,
                tuple(
                    math.fsum(witness.translation[at] for witness in roster) / len(roster)
                    for at in range(3)
                ),
            )
            canonical.append(
                RigidScaleWitness(
                    rotation,
                    translation,
                    roster[0].scale,
                )
            )
        else:
            canonical.extend(roster)
    return tuple(canonical)


def _partition_witnesses(
    parent_occurrence: AcceptedOccurrenceSnapshot,
    parent: _PrismFact,
    child_occurrences: tuple[AcceptedOccurrenceSnapshot, ...],
    children: tuple[_PrismFact, ...],
    budget: _MatchBudget,
) -> tuple[RigidScaleWitness, ...]:
    """Enumerate common proper-similarity witnesses for one complete axial partition."""

    if len(children) < 2 or any(
        child.repeat_count != parent.repeat_count or child.edge_count != parent.edge_count
        for child in children
    ):
        return ()
    order_candidates = []
    items = tuple(zip(child_occurrences, children, strict=True))
    for candidate in permutations(items):
        budget.charge()
        valid = True
        for (_left_occurrence, left), (_right_occurrence, right) in zip(
            candidate, candidate[1:], strict=False
        ):
            join_bound = 2.0 * (
                left.quantization.metric_quantum + right.quantization.metric_quantum
            )
            if (
                abs(left.interval[1] - right.interval[0]) > join_bound
                or left.interval[1] > right.interval[0] + join_bound
            ):
                valid = False
                break
        if valid:
            order_candidates.append(candidate)
    if len(order_candidates) != 1:
        return ()
    ordered = order_candidates[0]
    intervals = [child.interval for _occurrence, child in ordered]
    if any(hi <= lo for lo, hi in intervals):
        return ()
    target_lo, target_hi = intervals[0][0], intervals[-1][1]
    parent_span = parent.interval[1] - parent.interval[0]
    scale = (target_hi - target_lo) / parent_span
    if not math.isfinite(scale) or scale <= 0.0:
        return ()
    found: list[RigidScaleWitness] = []
    parent_axis = _axis_vector(parent_occurrence.summary.axis)
    for rotation in PROPER_ROTATIONS:
        budget.charge()
        transformed_axis = _rotate(rotation, parent_axis)
        axis_at = next((at for at, value in enumerate(transformed_axis) if abs(value) > 0.5), None)
        if axis_at is None or any(
            item.summary.axis != "xyz"[axis_at] for item in child_occurrences
        ):
            continue
        if any(
            not _close(
                scale**2 * parent.low_cap.face.area,
                child.low_cap.face.area,
                _order_bound(parent.quantization, child.quantization, scale, 2),
            )
            for child in children
        ):
            continue
        source_low, source_high = (
            (parent.low_cap, parent.high_cap)
            if transformed_axis[axis_at] > 0.0
            else (parent.high_cap, parent.low_cap)
        )
        transverse_axes = tuple(at for at in range(3) if at != axis_at)
        transformed_section = tuple(_rotate(rotation, point) for point in parent.section_points)
        section_ok = True
        for child in children:
            child_metric = 2.0 * (
                scale * parent.quantization.metric_quantum + child.quantization.metric_quantum
            )
            child_area = _order_bound(parent.quantization, child.quantization, scale, 2)
            if not _prism_cap_similarity(
                source_low,
                child.low_cap,
                rotation,
                scale,
                axis_at,
                child_metric,
                child_area,
                budget,
            ) or not _prism_cap_similarity(
                source_high,
                child.high_cap,
                rotation,
                scale,
                axis_at,
                child_metric,
                child_area,
                budget,
            ):
                section_ok = False
                break
            rows = tuple(
                tuple(
                    right_at
                    for right_at, right in enumerate(child.section_points)
                    if sum((scale * left[at] - right[at]) ** 2 for at in transverse_axes)
                    <= child_metric**2
                )
                for left in transformed_section
            )
            if len(rows) != len(child.section_points) or not _enumerate_bijections(rows, budget):
                section_ok = False
                break
        if not section_ok:
            continue
        extrema_metric = 2.0 * (
            scale * parent.quantization.metric_quantum
            + max(
                ordered[0][1].quantization.metric_quantum,
                ordered[-1][1].quantization.metric_quantum,
            )
        )
        if (
            abs((target_hi - target_lo) - scale * (parent.interval[1] - parent.interval[0]))
            > extrema_metric
        ):
            continue
        rotated_parent_centre = _rotate(rotation, parent_occurrence.summary.centre)
        target_centres: list[Vector3] = []
        for occurrence in child_occurrences:
            budget.charge()
            target = list(occurrence.summary.centre)
            target[axis_at] = (target_lo + target_hi) / 2.0
            centre_candidate = cast(Vector3, tuple(target))
            if centre_candidate not in target_centres:
                target_centres.append(centre_candidate)
        for target_centre in target_centres:
            translation = cast(
                Vector3,
                tuple(
                    target - scale * source
                    for source, target in zip(rotated_parent_centre, target_centre, strict=True)
                ),
            )
            zero_bound = 2.0 * (
                scale * parent.quantization.metric_quantum
                + min(child.quantization.metric_quantum for child in children)
            )
            translation = _normalize_partition_translation(translation, zero_bound)
            transformed_parent_centre = _affine_point(
                rotation, translation, scale, parent_occurrence.summary.centre
            )
            if any(
                sum(
                    (occurrence.summary.centre[at] - transformed_parent_centre[at]) ** 2
                    for at in range(3)
                    if at != axis_at
                )
                > (
                    2.0
                    * (
                        scale * parent.quantization.metric_quantum
                        + child.quantization.metric_quantum
                    )
                )
                ** 2
                for occurrence, child in zip(child_occurrences, children, strict=True)
            ):
                continue
            # Every internal cap cancels once with opposed material side.
            if any(
                not _prism_cap_similarity(
                    left.high_cap,
                    right.low_cap,
                    IDENTITY_ROTATION,
                    1.0,
                    axis_at,
                    2.0 * (left.quantization.metric_quantum + right.quantization.metric_quantum),
                    2.0 * (left.quantization.area_quantum + right.quantization.area_quantum),
                    budget,
                    material_factor=-1,
                )
                for (_left_occurrence, left), (_right_occurrence, right) in zip(
                    ordered, ordered[1:], strict=False
                )
            ):
                continue
            volume_bound = 2.0 * (
                scale**3 * parent.quantization.volume_quantum
                + sum(child.quantization.volume_quantum for child in children)
            )
            child_volume = sum(child.volume for child in children)
            if abs(scale**3 * parent.volume - child_volume) > volume_bound:
                continue
            errors = tuple(2.0 * child.quantization.volume_quantum for child in children)
            if (
                sum(child.volume - error for child, error in zip(children, errors, strict=True))
                <= 0.0
            ):
                continue
            parent_com = _affine_point(rotation, translation, scale, parent.centre_of_mass)
            residual = [0.0, 0.0, 0.0]
            first_moment_bound = 0.0
            parent_centre_error = 2.0 * scale * parent.quantization.metric_quantum
            child_volume_upper = 0.0
            for child, volume_error in zip(children, errors, strict=True):
                displacement = tuple(
                    value - anchor
                    for value, anchor in zip(child.centre_of_mass, parent_com, strict=True)
                )
                for at in range(3):
                    residual[at] += child.volume * displacement[at]
                metric_error = 2.0 * child.quantization.metric_quantum
                volume_upper = abs(child.volume) + volume_error
                child_volume_upper += volume_upper
                first_moment_bound += volume_upper * metric_error + volume_error * math.dist(
                    child.centre_of_mass, parent_com
                )
            first_moment_bound += child_volume_upper * parent_centre_error
            if sum(value * value for value in residual) > first_moment_bound**2:
                continue
            witness = RigidScaleWitness(rotation, translation, scale)
            if witness not in found:
                found.append(witness)
    # Independently rebuilt kernels can place the same section centre a few ulps
    # apart.  Those candidates prove one observational witness, not competing
    # placement semantics.  Collapse only a complete pairwise-equivalent roster;
    # a bridge/non-clique roster remains distinct and therefore ambiguous.
    equivalence_bound = 4.0 * (
        scale * parent.quantization.metric_quantum
        + min(child.quantization.metric_quantum for child in children)
    )
    return _canonicalize_partition_witnesses(tuple(found), equivalence_bound, budget)


@dataclass(frozen=True, slots=True)
class _PartitionHyperedge:
    before_groups: tuple[int, ...]
    after_groups: tuple[int, ...]
    witness: RigidScaleWitness
    kind: ChangeKind
    occurrence_pairs: tuple[tuple[int, int], ...] = ()


def _partition_hypergraph_relations(
    before: CorrespondenceSnapshot,
    after: CorrespondenceSnapshot,
    budget: _MatchBudget,
) -> tuple[CorrespondenceRelation, ...] | None:
    """Jointly cover singleton and geometric-partition hypotheses."""

    def occurrence_prism(occurrence: AcceptedOccurrenceSnapshot) -> _PrismFact | None:
        return prism_fact(
            occurrence.matching_boundary,
            axis_name=occurrence.summary.axis,
            span=occurrence.summary.span,
            profile_centre=occurrence.summary.centre,
            section_signature=occurrence.summary.sector_signature,
            defining=occurrence.summary.defining,
            repeat_count=occurrence.summary.repeat_count,
            edge_count=occurrence.summary.edge_count,
            volume=occurrence.body.intrinsic.volume,
            centre_of_mass=occurrence.body.placement.centre_of_mass,
            quantization=occurrence.body.quantization,
            charge=budget.charge,
        )

    before_facts = {
        group_at: fact
        for group_at, group in enumerate(before.body_groups)
        if len(group) == 1
        if (fact := occurrence_prism(before.occurrences[group[0]])) is not None
    }
    after_facts = {
        group_at: fact
        for group_at, group in enumerate(after.body_groups)
        if len(group) == 1
        if (fact := occurrence_prism(after.occurrences[group[0]])) is not None
    }
    edges: list[_PartitionHyperedge] = []
    for parent_group, parent_fact in before_facts.items():
        parent_position = before.body_groups[parent_group][0]
        for size in range(2, len(after_facts) + 1):
            for child_groups in combinations(tuple(after_facts), size):
                budget.charge()
                child_positions = tuple(after.body_groups[group][0] for group in child_groups)
                witnesses = _partition_witnesses(
                    before.occurrences[parent_position],
                    parent_fact,
                    tuple(after.occurrences[position] for position in child_positions),
                    tuple(after_facts[group] for group in child_groups),
                    budget,
                )
                edges.extend(
                    _PartitionHyperedge((parent_group,), child_groups, witness, ChangeKind.SPLIT)
                    for witness in witnesses
                )
    for parent_group, parent_fact in after_facts.items():
        parent_position = after.body_groups[parent_group][0]
        for size in range(2, len(before_facts) + 1):
            for child_groups in combinations(tuple(before_facts), size):
                budget.charge()
                child_positions = tuple(before.body_groups[group][0] for group in child_groups)
                witnesses = _partition_witnesses(
                    after.occurrences[parent_position],
                    parent_fact,
                    tuple(before.occurrences[position] for position in child_positions),
                    tuple(before_facts[group] for group in child_groups),
                    budget,
                )
                edges.extend(
                    _PartitionHyperedge(
                        child_groups,
                        (parent_group,),
                        _inverse_witness(witness),
                        ChangeKind.MERGED,
                    )
                    for witness in witnesses
                )
    if not edges:
        return None

    # Reuse the complete F6b1 body-group hypothesis authority before classification.
    _group_edges, group_hypotheses, _weights = _group_similarity_hypotheses(before, after, budget)
    for (before_group, after_group), hypotheses in group_hypotheses.items():
        before_positions = before.body_groups[before_group]
        after_positions = after.body_groups[after_group]
        edges.extend(
            _PartitionHyperedge(
                (before_group,),
                (after_group,),
                witness,
                ChangeKind.MOVED,
                tuple(
                    (before_positions[left_at], after_positions[right_at])
                    for left_at, right_at in matching
                ),
            )
            for matching, witness in hypotheses
        )

    edges = list(dict.fromkeys(edges))
    all_vertices = {
        *(("before", at) for at in range(len(before.body_groups))),
        *(("after", at) for at in range(len(after.body_groups))),
    }
    edge_vertices = tuple(
        frozenset(
            (
                *(("before", item) for item in edge.before_groups),
                *(("after", item) for item in edge.after_groups),
            )
        )
        for edge in edges
    )
    incident = {
        vertex: tuple(at for at, values in enumerate(edge_vertices) if vertex in values)
        for vertex in all_vertices
    }
    active = {vertex for vertex, roster in incident.items() if roster}
    relations: list[CorrespondenceRelation] = []
    pending = set(active)
    while pending:
        seed = min(pending)
        component = {seed}
        frontier = [seed]
        component_edges: set[int] = set()
        while frontier:
            vertex = frontier.pop()
            for edge_at in incident[vertex]:
                if edge_at in component_edges:
                    continue
                component_edges.add(edge_at)
                for neighbour in edge_vertices[edge_at]:
                    if neighbour not in component:
                        component.add(neighbour)
                        frontier.append(neighbour)
        pending.difference_update(component)
        ordered_edges = tuple(sorted(component_edges))
        covers: list[tuple[int, ...]] = []

        def cover(
            uncovered: frozenset[tuple[str, int]],
            selected: tuple[int, ...],
            result: list[tuple[int, ...]] = covers,
        ) -> None:
            budget.charge()
            if not uncovered:
                result.append(selected)
                return
            vertex = min(uncovered)
            for edge_at in incident[vertex]:
                values = edge_vertices[edge_at]
                budget.charge()
                if values <= uncovered:
                    cover(uncovered - values, (*selected, edge_at))

        cover(frozenset(component), ())
        semantic_covers = tuple(sorted(set(tuple(sorted(item)) for item in covers)))
        if len(semantic_covers) != 1:
            witnessed_edges = (
                ordered_edges
                if not semantic_covers
                else tuple(
                    sorted({edge_at for cover_edges in semantic_covers for edge_at in cover_edges})
                )
            )
            witnesses = tuple(
                sorted({edges[edge_at].witness for edge_at in witnessed_edges}, key=repr)
            )
            relations.append(
                CorrespondenceRelation(
                    ChangeKind.AMBIGUOUS,
                    tuple(
                        _ref("before", position, before)
                        for side, group in sorted(component)
                        if side == "before"
                        for position in before.body_groups[group]
                    ),
                    tuple(
                        _ref("after", position, after)
                        for side, group in sorted(component)
                        if side == "after"
                        for position in after.body_groups[group]
                    ),
                    None,
                    witnesses,
                )
            )
            continue
        for edge_at in semantic_covers[0]:
            edge = edges[edge_at]
            before_positions = tuple(
                position for group in edge.before_groups for position in before.body_groups[group]
            )
            after_positions = tuple(
                position for group in edge.after_groups for position in after.body_groups[group]
            )
            kind = edge.kind
            witness: RigidScaleWitness | None = edge.witness
            if kind is ChangeKind.MOVED:
                metric = _order_bound(
                    before.occurrences[before_positions[0]].body.quantization,
                    after.occurrences[after_positions[0]].body.quantization,
                    edge.witness.scale,
                    1,
                )
                scale_identity = _scale_is_identity(edge.witness.scale)
                placement_identity = edge.witness.rotation == IDENTITY_ROTATION and _scaled_point(
                    edge.witness.translation, 1.0, (0.0, 0.0, 0.0), metric
                )
                kind = (
                    ChangeKind.UNCHANGED
                    if scale_identity and placement_identity
                    else ChangeKind.MOVED
                    if scale_identity
                    else ChangeKind.RESIZED
                )
                if kind is ChangeKind.UNCHANGED:
                    witness = None
            if edge.kind is ChangeKind.MOVED:
                matched_before = {left for left, _right in edge.occurrence_pairs}
                matched_after = {right for _left, right in edge.occurrence_pairs}
                relations.extend(
                    CorrespondenceRelation(
                        kind,
                        (_ref("before", left, before),),
                        (_ref("after", right, after),),
                        witness,
                    )
                    for left, right in edge.occurrence_pairs
                )
                relations.extend(
                    CorrespondenceRelation(
                        ChangeKind.REMOVED,
                        (_ref("before", position, before),),
                        (),
                        None,
                    )
                    for position in before_positions
                    if position not in matched_before
                )
                relations.extend(
                    CorrespondenceRelation(
                        ChangeKind.ADDED,
                        (),
                        (_ref("after", position, after),),
                        None,
                    )
                    for position in after_positions
                    if position not in matched_after
                )
            else:
                relations.append(
                    CorrespondenceRelation(
                        kind,
                        tuple(_ref("before", position, before) for position in before_positions),
                        tuple(_ref("after", position, after) for position in after_positions),
                        witness,
                    )
                )

    for side, group in sorted(all_vertices - active):
        snapshot = before if side == "before" else after
        for position in snapshot.body_groups[group]:
            relations.append(
                CorrespondenceRelation(
                    ChangeKind.REMOVED if side == "before" else ChangeKind.ADDED,
                    (_ref("before", position, before),) if side == "before" else (),
                    (_ref("after", position, after),) if side == "after" else (),
                    None,
                )
            )
    return tuple(sorted(relations, key=_relation_key))


def _compare_snapshots(
    before: CorrespondenceSnapshot,
    after: CorrespondenceSnapshot,
    *,
    _issuer_validated: bool = False,
) -> CorrespondenceResult:
    if not _issuer_validated:
        try:
            _validate_snapshot(before)
            _validate_snapshot(after)
        except CorrespondenceSnapshotError as error:
            raise CorrespondenceMatchError("correspondence input snapshot is invalid") from error
    if before.schema_version != 3 or after.schema_version != 3:
        raise CorrespondenceMatchError("correspondence requires snapshot schema 3")

    budget = _MatchBudget()
    partition = _partition_hypergraph_relations(before, after, budget)
    exact = _unique_exact_relations(before, after) if partition is None else None
    if partition is not None:
        relations = partition
    elif exact is not None:
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
        matched = _similarity_relations(before, after, budget)
        if matched is None:
            raise CorrespondenceMatchError("non-rigid correspondence matching is not staged")
        relations = matched

    result = CorrespondenceResult(2, before.schema_version, after.schema_version, relations)
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
    return _compare_snapshots(before_snapshot, after_snapshot, _issuer_validated=True)
