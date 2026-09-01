"""Contracts for per-family MFCAD++ component-overlap evidence."""

from __future__ import annotations

from collections import Counter

from tools.audit_mfcadpp_component_overlap import (
    _accumulate_relation,
    _family_relations,
)


def test_family_relations_keep_competing_claims_separate() -> None:
    component = frozenset({1, 2, 3})
    claims = (
        {"family": "slots", "defining": frozenset({1, 2}), "constituent": frozenset({1, 2})},
        {
            "family": "channels",
            "defining": frozenset({1, 2}),
            "constituent": frozenset({1, 2, 3}),
        },
        {"family": "plates", "defining": frozenset({3}), "constituent": frozenset({3})},
    )

    actual = _family_relations(component, claims, ("channels", "slots"))

    assert actual["slots"]["defining"] == {
        "covered_faces": 2,
        "touching_records": 1,
        "touching_families": ["slots"],
        "full": False,
    }
    assert actual["channels"]["defining"]["covered_faces"] == 2
    assert actual["channels"]["constituent"] == {
        "covered_faces": 3,
        "touching_records": 1,
        "touching_families": ["channels"],
        "full": True,
    }


def test_relation_summary_counts_faces_touches_and_full_components() -> None:
    totals: Counter[str] = Counter()

    _accumulate_relation(
        totals,
        "defining",
        {"covered_faces": 2, "full": False},
    )
    _accumulate_relation(
        totals,
        "defining",
        {"covered_faces": 3, "full": True},
    )

    assert totals == Counter(
        {
            "defining_covered_faces": 5,
            "defining_touched_components": 2,
            "defining_full_components": 1,
        }
    )
