# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import json

import pytest
from build123d import Box

from b123d_recognisers import (
    PassageCompatibilityError,
    PassageEnds,
    PassageFrame,
    PassageSection,
    PassageSectionVertex,
    SectionPassage,
    build_recognition_result,
    recognise_passages,
    recognise_section_passages,
)
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger


def _square():
    return Box(60, 40, 20) - Box(10, 10, 60)


def test_public_nested_schema_and_json_shape() -> None:
    (record,) = recognise_section_passages(_square())
    assert record == SectionPassage(
        PassageFrame(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        (-10.0, 10.0),
        PassageSection(
            (
                PassageSectionVertex((-5.0, -5.0), 0.0),
                PassageSectionVertex((5.0, -5.0), 0.0),
                PassageSectionVertex((5.0, 5.0), 0.0),
                PassageSectionVertex((-5.0, 5.0), 0.0),
            )
        ),
        PassageEnds(False, False),
    )
    payload = json.loads(json.dumps(record.to_dict()))
    assert list(payload) == ["frame", "run_interval", "section", "ends"]
    assert payload["ends"] == {"low_capped": False, "high_capped": False}


def test_rich_api_is_the_exact_passages_candidate_authority() -> None:
    part = _square()
    ledger = ClaimLedger(FaceGraph(part))
    records = recognise_section_passages(part, ledger=ledger)
    (candidate,) = ledger.candidate_set(FamilyId.PASSAGES).candidates
    assert candidate.record is records[0]
    assert len(ledger.defining_of(candidate)) == len(records[0].section.boundary) == 4


def test_legacy_ledger_refuses_before_any_geometry_work(monkeypatch) -> None:
    import b123d_recognisers.passages as module

    ledger = ClaimLedger(FaceGraph(_square()))
    monkeypatch.setattr(module, "FaceGraph", lambda *args, **kwargs: pytest.fail("geometry ran"))
    with pytest.raises(
        PassageCompatibilityError,
        match=r"recognise_passages\(\.\.\., ledger=\.\.\.\) is unavailable from 0\.4\.0",
    ):
        recognise_passages(object(), ledger=ledger)  # type: ignore[arg-type]
    assert ledger.candidate_set(FamilyId.PASSAGES).candidates == ()


def test_aggregate_has_one_rich_authority_and_legacy_projection() -> None:
    result = build_recognition_result(_square())
    assert len(result.section_passages) == len(result.passages) == 1
    assert result.passages == tuple(recognise_passages(_square()))


@pytest.mark.parametrize(
    "record",
    [
        lambda: PassageFrame(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, -1.0),
            (1.0, 0.0, 0.0),
            (0.0, -1.0, 0.0),
        ),
        lambda: PassageEnds(0, False),
        lambda: SectionPassage(
            PassageFrame(
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
            ),
            (1.0, 1.0),
            PassageSection(
                (
                    PassageSectionVertex((-1.0, -1.0), 0.0),
                    PassageSectionVertex((1.0, -1.0), 0.0),
                    PassageSectionVertex((0.0, 2.0), 0.0),
                )
            ),
            PassageEnds(False, False),
        ),
    ],
)
def test_public_schema_refuses_noncanonical_values(record) -> None:
    with pytest.raises(ValueError):
        record()
