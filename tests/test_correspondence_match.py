from __future__ import annotations

import ast
import math
from dataclasses import replace

import pytest
from build123d import Align, Box, Compound, Plane, Pos, export_step, import_step

from b123d_recognisers._body_geometry import ANGLE_TOL, DIRECTION_TOL
from b123d_recognisers._correspondence import correspondence_snapshot
from b123d_recognisers._correspondence_match import (
    IDENTITY_ROTATION,
    PROPER_ROTATIONS,
    ChangeKind,
    CorrespondenceMatchError,
    CorrespondenceRelation,
    CorrespondenceResult,
    RigidScaleWitness,
    _affine_point,
    _body_similarity,
    _compare_snapshots,
    _curve_similarity,
    _determinant,
    _direction_close,
    _face_similarity,
    _inverse_witness,
    _MatchBudget,
    _maximum_matchings,
    _order_bound,
    _scale_is_identity,
    _validate_result,
    _wire_alignments,
    correspondence_changes,
)
from b123d_recognisers.result import _take_inventory
from tests.test_correspondence_snapshot import (
    _line_rrp,
    _proper_signed_permutations,
    _proper_transform,
    _rrp,
    _two_rrp_one_solid,
)


def _asymmetric_rrp():
    return _line_rrp(5) + Pos(18, 0, 5) * Box(
        4, 3, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )


def _chiral_rrp():
    return (
        _line_rrp(5)
        + Pos(18, 0, 3) * Box(4, 3, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        + Pos(0, 18, 7) * Box(2, 5, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    )


def test_empty_products_have_one_successful_empty_correspondence() -> None:
    before = _take_inventory(Box(10, 10, 10))
    after = _take_inventory(Box(20, 10, 10))
    result = correspondence_changes(before, after)
    assert result.schema_version == 1
    assert result.before_schema == result.after_schema == 3
    assert result.relations == ()


def test_exact_occurrences_are_unchanged_without_symmetry_witnesses() -> None:
    before = _take_inventory(_line_rrp(5))
    after = _take_inventory(_line_rrp(5))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.UNCHANGED]
    (relation,) = result.relations
    assert relation.witness is None
    assert relation.candidate_witnesses == ()
    assert relation.before_refs[0].occurrence == correspondence_snapshot(before).occurrences[0]
    assert relation.after_refs[0].occurrence == correspondence_snapshot(after).occurrences[0]


def test_exact_equal_distinct_body_groups_remain_one_ambiguous_component() -> None:
    before = _take_inventory(Compound([_rrp(5), _rrp(5)]))
    after = _take_inventory(Compound([_rrp(5), _rrp(5)]))
    before_snapshot = correspondence_snapshot(before)
    after_snapshot = correspondence_snapshot(after)
    assert before_snapshot.body_groups == after_snapshot.body_groups == ((0,), (1,))
    assert before_snapshot.occurrences[0] == before_snapshot.occurrences[1]

    (relation,) = correspondence_changes(before, after).relations
    assert relation.kind is ChangeKind.AMBIGUOUS
    assert tuple(ref.position for ref in relation.before_refs) == (0, 1)
    assert tuple(ref.position for ref in relation.after_refs) == (0, 1)
    assert relation.witness is None


def test_empty_to_nonempty_and_inverse_preserve_every_occurrence() -> None:
    empty = _take_inventory(Box(10, 10, 10))
    populated = _take_inventory(_line_rrp(5))
    added = correspondence_changes(empty, populated)
    removed = correspondence_changes(populated, empty)
    assert [relation.kind for relation in added.relations] == [ChangeKind.ADDED]
    assert [relation.kind for relation in removed.relations] == [ChangeKind.REMOVED]
    assert (
        added.relations[0].after_refs[0].occurrence
        == removed.relations[0].before_refs[0].occurrence
    )


def test_snapshot_only_leaf_rejects_unsupported_schema() -> None:
    product = _take_inventory(Box(10, 10, 10))
    snapshot = correspondence_snapshot(product)
    with pytest.raises(CorrespondenceMatchError, match="invalid"):
        _compare_snapshots(replace(snapshot, schema_version=1), snapshot)


def test_product_authority_is_required_before_snapshot_matching() -> None:
    product = _take_inventory(_line_rrp(5))
    copied = replace(product)
    with pytest.raises(CorrespondenceMatchError, match="authority"):
        correspondence_changes(copied, product)


def test_one_body_translation_has_one_shared_moved_witness() -> None:
    before = _take_inventory(_asymmetric_rrp())
    after = _take_inventory(Pos(11, -7, 3) * _asymmetric_rrp())
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.MOVED]
    (relation,) = result.relations
    assert relation.witness is not None
    assert relation.witness.scale == 1.0
    assert relation.witness.translation == pytest.approx((11.0, -7.0, 3.0), abs=1e-6)


def test_uniform_scale_precedes_its_placement_change() -> None:
    before = _take_inventory(_asymmetric_rrp())
    after = _take_inventory((Pos(11, -7, 3) * _asymmetric_rrp()).scale(2.0))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.RESIZED]
    (relation,) = result.relations
    assert relation.witness is not None
    assert relation.witness.scale == pytest.approx(2.0, rel=1e-7)


def test_all_24_proper_rotations_produce_the_exact_supported_witness() -> None:
    part = _asymmetric_rrp()
    before = _take_inventory(part)
    for rotation in _proper_signed_permutations():
        relation = correspondence_changes(
            before, _take_inventory(_proper_transform(part, rotation))
        ).relations[0]
        if rotation == IDENTITY_ROTATION:
            assert relation.kind is ChangeKind.UNCHANGED
            assert relation.witness is None
        else:
            assert relation.kind is ChangeKind.MOVED
            assert relation.witness is not None
            assert relation.witness.rotation == rotation
            assert relation.witness.scale == pytest.approx(1.0, rel=1e-12)


def test_proper_rotation_scale_and_translation_share_one_affine_witness() -> None:
    part = _asymmetric_rrp()
    rotation = _proper_signed_permutations()[8]
    transformed = Pos(11, -7, 3) * _proper_transform(part, rotation).scale(2.0)
    relation = correspondence_changes(
        _take_inventory(part), _take_inventory(transformed)
    ).relations[0]
    assert relation.kind is ChangeKind.RESIZED
    assert relation.witness is not None
    assert relation.witness.rotation == rotation
    assert relation.witness.scale == pytest.approx(2.0, rel=1e-7)


def test_symmetric_nonidentity_witnesses_are_one_whole_ambiguity() -> None:
    before = _take_inventory(_line_rrp(5))
    after = _take_inventory(Pos(11, -7, 3) * _line_rrp(5))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.AMBIGUOUS]


def test_chiral_mirror_has_no_invented_proper_similarity() -> None:
    part = _chiral_rrp()
    result = correspondence_changes(_take_inventory(part), _take_inventory(part.mirror(Plane.YZ)))
    assert {relation.kind for relation in result.relations} == {
        ChangeKind.ADDED,
        ChangeKind.REMOVED,
    }


def test_representation_preserving_step_uses_identity_precedence(tmp_path) -> None:
    part = _asymmetric_rrp()
    path = tmp_path / "correspondence.step"
    assert export_step(part, path)
    relation = correspondence_changes(
        _take_inventory(part), _take_inventory(import_step(path))
    ).relations[0]
    assert relation.kind is ChangeKind.UNCHANGED
    assert relation.witness is None


def test_independent_unique_and_ambiguous_components_do_not_contaminate() -> None:
    unique = Pos(60, 0, 0) * _asymmetric_rrp()
    symmetric = Pos(-60, 0, 0) * _line_rrp(5)
    before = _take_inventory(Compound([unique, symmetric]))
    after = _take_inventory(Pos(11, -7, 3) * Compound([unique, symmetric]))
    result = correspondence_changes(before, after)
    assert sorted(relation.kind.value for relation in result.relations) == [
        "ambiguous",
        "moved",
    ]
    ambiguous = next(
        relation for relation in result.relations if relation.kind is ChangeKind.AMBIGUOUS
    )
    assert len(ambiguous.before_refs) == len(ambiguous.after_refs) == 1
    assert len(ambiguous.candidate_witnesses) > 1


def test_discrete_repeat_change_is_added_and_removed_not_resized() -> None:
    result = correspondence_changes(_take_inventory(_line_rrp(5)), _take_inventory(_line_rrp(7)))
    assert {relation.kind for relation in result.relations} == {
        ChangeKind.ADDED,
        ChangeKind.REMOVED,
    }


def test_equal_rrp_record_with_different_host_geometry_does_not_match() -> None:
    left = _line_rrp(5) + Pos(18, 0, 5) * Box(
        4, 3, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )
    right = _line_rrp(5) + Pos(18, 0, 5) * Box(
        7, 2, 3, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )
    before = correspondence_snapshot(_take_inventory(left))
    after = correspondence_snapshot(_take_inventory(right))
    assert before.occurrences[0].record_value == after.occurrences[0].record_value
    result = correspondence_changes(_take_inventory(left), _take_inventory(right))
    assert {relation.kind for relation in result.relations} == {
        ChangeKind.ADDED,
        ChangeKind.REMOVED,
    }


def test_snapshot_tuple_permutation_changes_only_presentation_refs() -> None:
    before_product = _take_inventory(
        Compound([Pos(-60, 0, 0) * _asymmetric_rrp(), Pos(60, 0, 0) * _chiral_rrp()])
    )
    after_product = _take_inventory(
        Pos(11, -7, 3)
        * Compound([Pos(-60, 0, 0) * _asymmetric_rrp(), Pos(60, 0, 0) * _chiral_rrp()])
    )
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    direct = _compare_snapshots(before, after)
    permuted_before = replace(
        before,
        occurrences=tuple(reversed(before.occurrences)),
        body_groups=tuple(
            sorted((len(before.occurrences) - 1 - group[0],) for group in before.body_groups)
        ),
    )
    permuted_after = replace(
        after,
        occurrences=tuple(reversed(after.occurrences)),
        body_groups=tuple(
            sorted((len(after.occurrences) - 1 - group[0],) for group in after.body_groups)
        ),
    )
    permuted = _compare_snapshots(permuted_before, permuted_after)
    assert [relation.kind for relation in direct.relations] == [
        relation.kind for relation in permuted.relations
    ]
    assert [relation.witness for relation in direct.relations] == [
        relation.witness for relation in permuted.relations
    ]


def test_one_group_cannot_distribute_into_two_equal_target_groups() -> None:
    before = _take_inventory(_line_rrp(5))
    after = _take_inventory(Compound([_line_rrp(5), _line_rrp(5)]))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.AMBIGUOUS]
    (relation,) = result.relations
    assert len(relation.before_refs) == 1
    assert len(relation.after_refs) == 2
    assert relation.witness is None


def test_moved_coincident_groups_remain_one_whole_ambiguity_component() -> None:
    before = _take_inventory(Compound([_line_rrp(5), _line_rrp(5)]))
    after = _take_inventory(Pos(11, -7, 3) * Compound([_line_rrp(5), _line_rrp(5)]))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.AMBIGUOUS]
    (relation,) = result.relations
    assert len(relation.before_refs) == len(relation.after_refs) == 2


def test_two_occurrences_on_one_body_share_one_group_witness() -> None:
    before = _take_inventory(_two_rrp_one_solid())
    after = _take_inventory(Pos(11, -7, 3) * _two_rrp_one_solid())
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [
        ChangeKind.MOVED,
        ChangeKind.MOVED,
    ]
    first, second = result.relations
    assert first.witness == second.witness
    assert first.witness is not None
    assert first.witness.translation == pytest.approx((11.0, -7.0, 3.0), abs=1e-6)


def test_two_occurrences_on_one_body_share_one_rotation_witness() -> None:
    part = _two_rrp_one_solid()
    rotation = _proper_signed_permutations()[9]
    result = correspondence_changes(
        _take_inventory(part), _take_inventory(_proper_transform(part, rotation))
    )
    assert [relation.kind for relation in result.relations] == [
        ChangeKind.MOVED,
        ChangeKind.MOVED,
    ]
    assert result.relations[0].witness == result.relations[1].witness
    assert result.relations[0].witness is not None
    assert result.relations[0].witness.rotation == rotation


def test_one_body_group_cannot_split_across_two_target_groups() -> None:
    before_product = _take_inventory(_two_rrp_one_solid())
    after_product = _take_inventory(Pos(11, -7, 3) * _two_rrp_one_solid())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    assert before.body_groups == after.body_groups == ((0, 1),)
    split_after = replace(after, body_groups=((0,), (1,)))
    forward = _compare_snapshots(before, split_after)
    inverse = _compare_snapshots(split_after, before)
    assert [relation.kind for relation in forward.relations] == [ChangeKind.AMBIGUOUS]
    assert [relation.kind for relation in inverse.relations] == [ChangeKind.AMBIGUOUS]
    assert len(forward.relations[0].before_refs) == 2
    assert len(forward.relations[0].after_refs) == 2


def test_unequal_weight_body_group_alternative_is_wholly_ambiguous() -> None:
    before_product = _take_inventory(_two_rrp_one_solid())
    after_product = _take_inventory(Pos(11, -7, 3) * _two_rrp_one_solid())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    expanded_after = replace(
        after,
        occurrences=(*after.occurrences, after.occurrences[0]),
        body_groups=((0, 1), (2,)),
    )
    forward = _compare_snapshots(before, expanded_after)
    inverse = _compare_snapshots(expanded_after, before)
    assert [relation.kind for relation in forward.relations] == [ChangeKind.AMBIGUOUS]
    assert [relation.kind for relation in inverse.relations] == [ChangeKind.AMBIGUOUS]
    assert len(forward.relations[0].before_refs) == 2
    assert len(forward.relations[0].after_refs) == 3


@pytest.mark.parametrize("scale", (1.0, 2.0))
def test_swapping_products_inverts_the_identity_rotation_witness(scale: float) -> None:
    before = _take_inventory(_asymmetric_rrp())
    transformed = (Pos(11, -7, 3) * _asymmetric_rrp()).scale(scale)
    after = _take_inventory(transformed)
    forward = correspondence_changes(before, after).relations[0]
    backward = correspondence_changes(after, before).relations[0]
    assert forward.kind is backward.kind
    assert forward.witness is not None and backward.witness is not None
    assert backward.witness.scale == pytest.approx(1.0 / forward.witness.scale, rel=1e-9)
    assert backward.witness.translation == pytest.approx(
        tuple(-value / forward.witness.scale for value in forward.witness.translation),
        abs=1e-6,
    )


def test_swapping_a_rotated_resize_uses_the_exact_inverse_witness() -> None:
    part = _asymmetric_rrp()
    rotation = _proper_signed_permutations()[8]
    transformed = Pos(11, -7, 3) * _proper_transform(part, rotation).scale(2.0)
    forward = correspondence_changes(_take_inventory(part), _take_inventory(transformed)).relations[
        0
    ]
    backward = correspondence_changes(
        _take_inventory(transformed), _take_inventory(part)
    ).relations[0]
    assert forward.kind is backward.kind is ChangeKind.RESIZED
    assert forward.witness is not None and backward.witness is not None
    assert backward.witness.rotation == _inverse_witness(forward.witness).rotation
    assert backward.witness.scale == pytest.approx(0.5, rel=1e-9)
    assert backward.witness.translation == pytest.approx(
        _inverse_witness(forward.witness).translation, abs=1e-6
    )


def test_hypothesis_budget_is_inclusive_and_never_truncates(monkeypatch) -> None:
    import b123d_recognisers._correspondence_match as module

    edges = {0: (0, 1), 1: (0, 1)}
    monkeypatch.setattr(module, "MATCH_HYPOTHESIS_BUDGET", 7)
    assert _maximum_matchings(2, 2, edges) == (
        ((0, 0), (1, 1)),
        ((0, 1), (1, 0)),
    )
    monkeypatch.setattr(module, "MATCH_HYPOTHESIS_BUDGET", 6)
    with pytest.raises(CorrespondenceMatchError, match="budget"):
        _maximum_matchings(2, 2, edges)


def test_late_global_budget_refusal_returns_no_prefix_or_input_mutation(monkeypatch) -> None:
    import b123d_recognisers._correspondence_match as module

    before_product = _take_inventory(_asymmetric_rrp())
    after_product = _take_inventory(Pos(11, -7, 3) * _asymmetric_rrp())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    monkeypatch.setattr(module, "MATCH_HYPOTHESIS_BUDGET", 1)
    with pytest.raises(CorrespondenceMatchError, match="budget"):
        correspondence_changes(before_product, after_product)
    assert correspondence_snapshot(before_product) == before
    assert correspondence_snapshot(after_product) == after


def test_reciprocal_scale_identity_boundary_is_inclusive_and_swap_stable() -> None:
    from b123d_recognisers._correspondence_match import SCALE_TOL

    upper = 1.0 + SCALE_TOL
    lower = 1.0 / upper
    assert _scale_is_identity(upper)
    assert _scale_is_identity(lower)
    assert not _scale_is_identity(float("nan"))
    assert not _scale_is_identity(0.0)
    assert not _scale_is_identity(float("inf"))
    assert not _scale_is_identity(math.nextafter(upper, math.inf))
    assert not _scale_is_identity(math.nextafter(lower, 0.0))


def test_complete_similarity_numeric_bounds_are_inclusive_and_nextafter_closed() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_asymmetric_rrp())).occurrences[0]
    quantization = occurrence.body.quantization
    metric = _order_bound(quantization, quantization, 1.0, 1)
    area = _order_bound(quantization, quantization, 1.0, 2)
    volume = _order_bound(quantization, quantization, 1.0, 3)
    moment = _order_bound(quantization, quantization, 1.0, 5)
    assert _direction_close((0.0, 0.0, 0.0), (4.0 * DIRECTION_TOL, 0.0, 0.0))
    assert not _direction_close(
        (0.0, 0.0, 0.0),
        (math.nextafter(4.0 * DIRECTION_TOL, math.inf), 0.0, 0.0),
    )
    diagonal = 4.0 * DIRECTION_TOL / math.sqrt(2.0)
    assert _direction_close((0.0, 0.0, 0.0), (diagonal, diagonal, 0.0))
    outside_diagonal = math.nextafter(math.nextafter(diagonal, math.inf), math.inf)
    assert not _direction_close(
        (0.0, 0.0, 0.0),
        (outside_diagonal, outside_diagonal, 0.0),
    )

    line_index = next(
        index
        for index, curve in enumerate(occurrence.matching_boundary.curves)
        if curve.kind == "LINE"
    )
    line = occurrence.matching_boundary.curves[line_index]
    vertex_map = tuple(range(len(occurrence.matching_boundary.vertices)))
    assert (
        _curve_similarity(
            line,
            replace(line, length=line.length + metric),
            vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is not None
    )
    assert (
        _curve_similarity(
            line,
            replace(line, length=math.nextafter(line.length + metric, math.inf)),
            vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is None
    )

    curved_occurrence = correspondence_snapshot(_take_inventory(_rrp(5))).occurrences[0]
    curved_vertex_map = tuple(range(len(curved_occurrence.matching_boundary.vertices)))
    circle = next(
        curve
        for curve in curved_occurrence.matching_boundary.curves
        if curve.kind == "CIRCLE" and not curve.full
    )
    assert circle.sweep is not None
    sweep_inside = math.nextafter(circle.sweep + 4.0 * ANGLE_TOL, circle.sweep)
    assert (
        _curve_similarity(
            circle,
            replace(circle, sweep=sweep_inside),
            curved_vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is not None
    )
    assert (
        _curve_similarity(
            circle,
            replace(
                circle,
                sweep=math.nextafter(circle.sweep + 4.0 * ANGLE_TOL, math.inf),
            ),
            curved_vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is None
    )

    face = occurrence.matching_boundary.faces[0]
    assert (
        _face_similarity(
            face,
            replace(face, area=face.area + area),
            IDENTITY_ROTATION,
            1.0,
            metric,
            area,
        )
        is not None
    )
    assert (
        _face_similarity(
            face,
            replace(face, area=math.nextafter(face.area + area, math.inf)),
            IDENTITY_ROTATION,
            1.0,
            metric,
            area,
        )
        is None
    )

    for field, bound in (("volume", volume), ("surface_area", area)):
        intrinsic = occurrence.body.intrinsic
        changed = replace(intrinsic, **{field: getattr(intrinsic, field) + bound})
        target = replace(occurrence, body=replace(occurrence.body, intrinsic=changed))
        assert _body_similarity(
            occurrence,
            target,
            IDENTITY_ROTATION,
            1.0,
            _MatchBudget(),
        )
        outside = replace(
            intrinsic,
            **{field: math.nextafter(getattr(intrinsic, field) + bound, math.inf)},
        )
        assert not _body_similarity(
            occurrence,
            replace(occurrence, body=replace(occurrence.body, intrinsic=outside)),
            IDENTITY_ROTATION,
            1.0,
            _MatchBudget(),
        )

    intrinsic = occurrence.body.intrinsic
    moments = list(intrinsic.principal_moments)
    moments[0] += moment
    assert _body_similarity(
        occurrence,
        replace(
            occurrence,
            body=replace(
                occurrence.body,
                intrinsic=replace(intrinsic, principal_moments=tuple(moments)),
            ),
        ),
        IDENTITY_ROTATION,
        1.0,
        _MatchBudget(),
    )
    moments[0] = math.nextafter(moments[0], math.inf)
    assert not _body_similarity(
        occurrence,
        replace(
            occurrence,
            body=replace(
                occurrence.body,
                intrinsic=replace(intrinsic, principal_moments=tuple(moments)),
            ),
        ),
        IDENTITY_ROTATION,
        1.0,
        _MatchBudget(),
    )


def test_wire_alignment_enumerates_reversed_whole_wire_presentation() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_asymmetric_rrp())).occurrences[0]
    graph = occurrence.matching_boundary
    face = next(face for face in graph.faces if face.kind == "PLANE" and face.wires)
    wire = face.wires[0]
    reversed_wire = replace(
        wire,
        cycle=tuple(
            replace(edge, start=edge.end, end=edge.start, direction=-edge.direction)
            for edge in reversed(wire.cycle)
        ),
        theta_winding=-wire.theta_winding,
    )
    alignments = _wire_alignments(
        wire,
        reversed_wire,
        face,
        replace(face, wires=(reversed_wire,)),
        tuple(range(len(graph.vertices))),
        tuple(range(len(graph.curves))),
        tuple(1 for _curve in graph.curves),
        graph.vertices,
        1,
        _order_bound(
            occurrence.body.quantization,
            occurrence.body.quantization,
            1.0,
            1,
        ),
        _MatchBudget(),
    )
    assert alignments


def test_proper_rotation_roster_and_affine_inverse_are_exact() -> None:
    assert len(PROPER_ROTATIONS) == 24
    assert len(set(PROPER_ROTATIONS)) == 24
    assert tuple(sorted(PROPER_ROTATIONS)) == PROPER_ROTATIONS
    point = (2.5, -3.0, 7.25)
    for rotation in PROPER_ROTATIONS:
        assert _determinant(rotation) == 1
        witness = RigidScaleWitness(rotation, (11.0, -7.0, 3.0), 2.0)
        transformed = _affine_point(
            witness.rotation,
            witness.translation,
            witness.scale,
            point,
        )
        inverse = _inverse_witness(witness)
        assert _affine_point(
            inverse.rotation,
            inverse.translation,
            inverse.scale,
            transformed,
        ) == pytest.approx(point, abs=1e-12)


@pytest.mark.parametrize(
    "witness",
    (
        RigidScaleWitness(((1, 0, 0), (0, -1, 0), (0, 0, 1)), (0.0, 0.0, 0.0), 1.0),
        RigidScaleWitness(IDENTITY_ROTATION, (0.0, float("nan"), 0.0), 1.0),
        RigidScaleWitness(IDENTITY_ROTATION, (0.0, 0.0, 0.0), 0.0),
    ),
)
def test_closed_result_validation_refuses_malformed_witnesses(
    witness: RigidScaleWitness,
) -> None:
    before_product = _take_inventory(_asymmetric_rrp())
    after_product = _take_inventory(Pos(2, 0, 0) * _asymmetric_rrp())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    relation = correspondence_changes(before_product, after_product).relations[0]
    malformed = CorrespondenceResult(1, 3, 3, (replace(relation, witness=witness),))
    with pytest.raises(CorrespondenceMatchError, match="witness"):
        _validate_result(malformed, before, after)


def test_closed_result_validation_refuses_kind_shape_drift() -> None:
    before_product = _take_inventory(_asymmetric_rrp())
    after_product = _take_inventory(Pos(2, 0, 0) * _asymmetric_rrp())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    moved = correspondence_changes(before_product, after_product).relations[0]
    malformed = CorrespondenceResult(
        1,
        3,
        3,
        (
            CorrespondenceRelation(
                ChangeKind.ADDED,
                moved.before_refs,
                moved.after_refs,
                moved.witness,
                (moved.witness,) if moved.witness is not None else (),
            ),
        ),
    )
    with pytest.raises(CorrespondenceMatchError, match="added"):
        _validate_result(malformed, before, after)


def test_matcher_dependency_and_policy_rosters_are_closed() -> None:
    from pathlib import Path

    path = Path(__file__).parents[1] / "src" / "b123d_recognisers" / "_correspondence_match.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module: {alias.name for alias in node.names}
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        in {
            "b123d_recognisers._body_geometry",
            "b123d_recognisers._correspondence",
        }
    }
    assert set(imports) == {
        "b123d_recognisers._body_geometry",
        "b123d_recognisers._correspondence",
    }
    assert imports["b123d_recognisers._body_geometry"] == {
        "ANGLE_TOL",
        "DESCRIPTOR_REL",
        "DIRECTION_TOL",
        "DescriptorQuantization",
        "FaceGeometry",
        "MatchingBoundaryGraph",
        "MatchingCurve",
        "MatchingFace",
        "MatchingWire",
    }
    assert imports["b123d_recognisers._correspondence"] == {
        "AcceptedOccurrenceSnapshot",
        "CorrespondenceSnapshot",
        "CorrespondenceSnapshotError",
        "_InventoryProduct",
        "_validate_snapshot",
        "correspondence_snapshot",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert (
        not {
            "Candidate",
            "EvidenceIndex",
            "FaceGraph",
            "SolidRef",
            "RecognitionResult",
            "ClaimLedger",
            "SPLIT",
            "MERGED",
            "hash",
            "digest",
        }
        & names
    )
    trusted_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_compare_snapshots"
        and any(
            keyword.arg == "_issuer_validated"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
    ]
    assert len(trusted_calls) == 1
    owner = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and trusted_calls[0] in tuple(ast.walk(node))
    )
    assert owner.name == "correspondence_changes"
    assert "correspondence_changes" not in __import__("b123d_recognisers").__all__
