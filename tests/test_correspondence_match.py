from __future__ import annotations

from dataclasses import replace

import pytest
from build123d import Box, Pos

from b123d_recognisers._correspondence import correspondence_snapshot
from b123d_recognisers._correspondence_match import (
    ChangeKind,
    CorrespondenceMatchError,
    _compare_snapshots,
    correspondence_changes,
)
from b123d_recognisers.result import _take_inventory
from tests.test_correspondence_snapshot import _line_rrp


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
