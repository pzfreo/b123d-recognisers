from __future__ import annotations

from dataclasses import replace

import pytest
from build123d import Box, Compound, Pos

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
    _compare_snapshots,
    _determinant,
    _inverse_witness,
    _maximum_matchings,
    _validate_result,
    correspondence_changes,
)
from b123d_recognisers.result import _take_inventory
from tests.test_correspondence_snapshot import _line_rrp, _two_rrp_one_solid


def test_empty_products_have_one_successful_empty_correspondence() -> None:
    before = _take_inventory(Box(10, 10, 10))
    after = _take_inventory(Box(20, 10, 10))
    result = correspondence_changes(before, after)
    assert result.schema_version == 1
    assert result.before_schema == result.after_schema == 2
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
    before = _take_inventory(_line_rrp(5))
    after = _take_inventory(Pos(11, -7, 3) * _line_rrp(5))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.MOVED]
    (relation,) = result.relations
    assert relation.witness is not None
    assert relation.witness.scale == 1.0
    assert relation.witness.translation == pytest.approx((11.0, -7.0, 3.0), abs=1e-6)


def test_uniform_scale_precedes_its_placement_change() -> None:
    before = _take_inventory(_line_rrp(5))
    after = _take_inventory((Pos(11, -7, 3) * _line_rrp(5)).scale(2.0))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.RESIZED]
    (relation,) = result.relations
    assert relation.witness is not None
    assert relation.witness.scale == pytest.approx(2.0, rel=1e-7)


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


@pytest.mark.parametrize("scale", (1.0, 2.0))
def test_swapping_products_inverts_the_identity_rotation_witness(scale: float) -> None:
    before = _take_inventory(_line_rrp(5))
    transformed = (Pos(11, -7, 3) * _line_rrp(5)).scale(scale)
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
    before_product = _take_inventory(_line_rrp(5))
    after_product = _take_inventory(Pos(2, 0, 0) * _line_rrp(5))
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    relation = correspondence_changes(before_product, after_product).relations[0]
    malformed = CorrespondenceResult(1, 2, 2, (replace(relation, witness=witness),))
    with pytest.raises(CorrespondenceMatchError, match="witness"):
        _validate_result(malformed, before, after)


def test_closed_result_validation_refuses_kind_shape_drift() -> None:
    before_product = _take_inventory(_line_rrp(5))
    after_product = _take_inventory(Pos(2, 0, 0) * _line_rrp(5))
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    moved = correspondence_changes(before_product, after_product).relations[0]
    malformed = CorrespondenceResult(
        1,
        2,
        2,
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
