"""Shared F5b oracle for physical-family attribution fixtures."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger


def attributed_run(
    part,
    family: FamilyId,
    recognise: Callable[..., Sequence],
    *,
    kwargs: Mapping[str, Any] | None = None,
):
    """Prove writer parity and the identity/provenance lifecycle for one real fixture."""

    call_kwargs = dict(kwargs or {})
    plain = tuple(recognise(part, **call_kwargs))
    ledger = ClaimLedger(FaceGraph(part))
    measured = tuple(recognise(part, ledger=ledger, **call_kwargs))
    assert [type(record) for record in measured] == [type(record) for record in plain]
    assert measured == plain
    assert [record.to_dict() for record in measured] == [record.to_dict() for record in plain]

    candidates = ledger.candidate_set(family).candidates
    assert len(candidates) == len(measured)
    for candidate, record in zip(candidates, measured, strict=True):
        assert candidate.family is family
        assert candidate.record is record
        defining = ledger.defining_of(candidate)
        assert defining
        assert ledger.graph.common_valid_solid(defining) is not None
    return ledger, list(measured)


def unattributed_run(
    part,
    family: FamilyId,
    recognise: Callable[..., Sequence],
    *,
    kwargs: Mapping[str, Any] | None = None,
):
    """Prove a negative fixture issues neither output nor an orphan family Candidate."""

    ledger = ClaimLedger(FaceGraph(part))
    assert recognise(part, ledger=ledger, **dict(kwargs or {})) == []
    assert ledger.candidate_set(family).candidates == ()
    return ledger
