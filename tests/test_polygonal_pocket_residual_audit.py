# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Contract tests for the aggregate polygonal Pocket residual audit."""

from __future__ import annotations

from tools.audit_mfcadpp_polygonal_pocket_residuals import (
    _selection_hash,
    _status,
    _summarise,
)


def _row(class_id: int, faces: int, covered: int, gate: str) -> dict:
    return {
        "class_id": class_id,
        "faces": faces,
        "constituent_faces": covered,
        "coverage_status": _status(covered, faces),
        "ring_probe": {"first_failed_gate": gate},
    }


def test_status_separates_detection_from_membership() -> None:
    assert _status(0, 6) == "untouched"
    assert _status(2, 6) == "partial"
    assert _status(6, 6) == "complete"


def test_summary_keeps_each_polygonal_family_and_residual_kind_separate() -> None:
    summary = _summarise(
        [
            _row(13, 3, 0, "not_simple_cycle"),
            _row(13, 4, 2, "not_single_cap"),
            _row(14, 5, 5, "recognisable"),
            _row(15, 6, 0, "not_simple_cycle"),
        ]
    )

    assert summary["13"] == {
        "components": 2,
        "faces": 7,
        "constituent_faces": 2,
        "missing_constituent_faces": 5,
        "coverage": 2 / 7,
        "untouched_components": 1,
        "partial_components": 1,
        "complete_components": 0,
        "incomplete_first_failed_gates": {
            "not_simple_cycle": 1,
            "not_single_cap": 1,
        },
    }
    assert summary["14"]["complete_components"] == 1
    assert summary["15"]["untouched_components"] == 1


def test_selection_hash_retains_lexical_order() -> None:
    assert _selection_hash(["100", "200"]) != _selection_hash(["200", "100"])
