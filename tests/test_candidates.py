# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Identity and provenance contracts for issue #156's private candidate layer."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import pytest
from build123d import Box, Pos, Rot

from b123d_recognisers import recognise_angled_steps
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import Candidate, CandidateSet, Evidence, FamilyId
from b123d_recognisers._claims import ClaimLedger


@dataclass(frozen=True)
class Record:
    value: int


def test_equal_records_remain_distinct_sink_issued_candidates() -> None:
    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    first_record = Record(1)
    second_record = Record(1)

    first = ledger.propose(FamilyId.LEGACY, first_record, [ledger.graph.nodes[0]])
    second = ledger.propose(FamilyId.LEGACY, second_record, [ledger.graph.nodes[1]])

    assert first_record == second_record and first_record is not second_record
    assert first is not second and first != second
    assert ledger.defining_of(first) == frozenset({ledger.graph.nodes[0]})
    assert ledger.defining_of(second) == frozenset({ledger.graph.nodes[1]})


def test_empty_evidence_is_a_candidate_but_not_a_claim() -> None:
    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    record = Record(1)

    candidate = ledger.propose(FamilyId.LEGACY, record)

    assert candidate.evidence.defining == frozenset()
    assert ledger.defining_of(candidate) == frozenset()
    assert ledger.defining_of(record) == frozenset()
    assert ledger.claims == ()
    assert ledger.candidate_set(FamilyId.LEGACY).candidates == (candidate,)


def test_foreign_evidence_is_refused_atomically() -> None:
    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    other = FaceGraph(Box(4, 4, 4))

    with pytest.raises(ValueError, match="not this graph's nodes"):
        ledger.propose(FamilyId.LEGACY, Record(1), [other.nodes[0]])

    assert ledger.candidate_set(FamilyId.LEGACY).candidates == ()
    assert ledger.claims == ()


def test_candidate_and_candidate_set_cannot_be_constructed_directly() -> None:
    with pytest.raises(TypeError):
        Candidate(FamilyId.LEGACY, Record(1), None)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        CandidateSet(FamilyId.LEGACY, ())  # type: ignore[call-arg]


def test_a_candidate_from_another_run_is_refused() -> None:
    first = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    second = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    candidate = first.propose(FamilyId.LEGACY, Record(1), [first.graph.nodes[0]])

    with pytest.raises(ValueError, match="not issued by this run"):
        second.defining_of(candidate)


@pytest.mark.parametrize("foreign", [False, True])
def test_copying_an_issuer_token_does_not_forge_a_candidate(foreign: bool) -> None:
    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    other = FaceGraph(Box(4, 4, 4))
    valid = ledger.propose(FamilyId.LEGACY, Record(1), [ledger.graph.nodes[0]])
    forged = object.__new__(Candidate)
    object.__setattr__(forged, "family", FamilyId.LEGACY)
    object.__setattr__(forged, "record", Record(2))
    node = other.nodes[0] if foreign else ledger.graph.nodes[1]
    object.__setattr__(forged, "evidence", Evidence(frozenset({node})))
    object.__setattr__(forged, "_issuer", valid._issuer)

    with pytest.raises(ValueError, match="not issued by this run"):
        ledger.defining_of(forged)


@pytest.mark.parametrize(
    "field",
    ["foreign_evidence", "local_evidence", "evidence_contents", "family", "record"],
)
def test_an_issued_candidate_cannot_be_altered_after_issuance(field: str) -> None:
    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    other = FaceGraph(Box(4, 4, 4))
    candidate = ledger.propose(FamilyId.LEGACY, Record(1), [ledger.graph.nodes[0]])
    if field == "foreign_evidence":
        object.__setattr__(candidate, "evidence", Evidence(frozenset({other.nodes[0]})))
    elif field == "local_evidence":
        object.__setattr__(candidate, "evidence", Evidence(frozenset({ledger.graph.nodes[1]})))
    elif field == "evidence_contents":
        object.__setattr__(candidate.evidence, "defining", frozenset({other.nodes[0]}))
    elif field == "family":
        object.__setattr__(candidate, "family", FamilyId.ANGLED_STEPS)
    else:
        object.__setattr__(candidate, "record", Record(2))

    with pytest.raises(ValueError, match="no longer matches its issued state"):
        ledger.defining_of(candidate)
    with pytest.raises(ValueError, match="no longer matches its issued state"):
        ledger.candidate_set(FamilyId.LEGACY)


def test_direct_sink_issuance_updates_candidate_and_legacy_views() -> None:
    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    record = Record(1)
    candidate = ledger.sink.propose(
        FamilyId.ANGLED_STEPS,
        record,
        defining=[ledger.graph.nodes[0]],
    )

    assert ledger.candidate_set(FamilyId.ANGLED_STEPS).candidates == (candidate,)
    assert ledger.defining_of(candidate) == frozenset({ledger.graph.nodes[0]})
    assert tuple(claim.claimant for claim in ledger.claims) == (record,)
    assert ledger.claims_of(ledger.graph.nodes[0]) == ledger.claims


def test_the_same_record_object_can_back_distinct_proposals() -> None:
    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    record = Record(1)
    first = ledger.propose(FamilyId.LEGACY, record, [ledger.graph.nodes[0]])
    second = ledger.propose(FamilyId.LEGACY, record, [ledger.graph.nodes[1]])

    assert first is not second
    assert ledger.candidate_set(FamilyId.LEGACY).candidates == (first, second)
    assert ledger.defining_of(first) == frozenset({ledger.graph.nodes[0]})
    assert ledger.defining_of(second) == frozenset({ledger.graph.nodes[1]})
    # The compatibility record lookup deliberately preserves ClaimLedger's previous last-wins
    # behaviour; candidate lookup is the unambiguous new path.
    assert ledger.defining_of(record) == ledger.defining_of(second)


def test_angled_steps_use_the_named_candidate_family() -> None:
    angled_step_part = Box(60, 40, 12) - Pos(-20, 20, 6) * Rot(45, 0, 0) * Box(
        30, 4 * sqrt(2), 4 * sqrt(2)
    )
    ledger = ClaimLedger(FaceGraph(angled_step_part))

    records = recognise_angled_steps(angled_step_part, ledger=ledger)
    candidate_set = ledger.candidate_set(FamilyId.ANGLED_STEPS)

    assert tuple(candidate.record for candidate in candidate_set.candidates) == tuple(records)
    assert all(candidate.evidence.defining for candidate in candidate_set.candidates)
    assert tuple(claim.claimant for claim in ledger.claims) == tuple(records)
