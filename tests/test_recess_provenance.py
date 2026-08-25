"""#234 neutral Slot/Pocket occurrence and cylindrical-cap provenance."""

from __future__ import annotations

from dataclasses import replace
from functools import partial

import pytest
from build123d import Box, Compound, Cylinder, Pos

from b123d_recognisers import recognise_pockets, recognise_slots
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._recess_core import _pocket_proposals_one, _slot_proposals_one
from b123d_recognisers._recess_obround import _extend_obround_proposals, _obround_ends
from b123d_recognisers._recess_reduce import (
    _body_scoped_proposals,
    _collapse_collinear_proposals,
    _merge_proposals,
    _RecessProposal,
)
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, IncompleteAttribution


def _obround(length: float, width: float, depth: float):
    end = Cylinder(width / 2, depth)
    return Box(length, width, depth) + Pos(-length / 2, 0, 0) * end + Pos(length / 2, 0, 0) * end


@pytest.mark.parametrize("length", [3, 30])
def test_slot_dual_read_retains_exact_cap_groups(length: float) -> None:
    part = Box(100, 60, 20) - _obround(length, 12, 20)
    graph = FaceGraph(part)
    proposals = _body_scoped_proposals([part], partial(_slot_proposals_one, graph=graph))
    assert [proposal.record.to_dict() for proposal in proposals] == [
        record.to_dict() for record in recognise_slots(part)
    ]
    (proposal,) = proposals
    assert len(proposal.caps) == 2
    assert all(group for group in proposal.caps)
    assert proposal.caps[0].isdisjoint(proposal.caps[1])
    assert all(not graph.is_planar(node) for group in proposal.caps for node in group)
    assert bool(proposal.planar) is (length == 30)


def test_stubby_pocket_dual_read_retains_caps_without_publishing_them() -> None:
    tool = _obround(6, 10, 8)
    part = Box(60, 40, 12) - Pos(0, 0, 4) * tool
    graph = FaceGraph(part)
    proposals = _body_scoped_proposals([part], partial(_pocket_proposals_one, graph=graph))
    assert [proposal.record.to_dict() for proposal in proposals] == [
        record.to_dict() for record in recognise_pockets(part)
    ]
    (proposal,) = proposals
    assert proposal.planar == frozenset()
    assert len(proposal.caps) == 2


def test_equal_occurrences_on_separate_solids_remain_distinct() -> None:
    first = Box(100, 60, 20) - _obround(3, 12, 20)
    second = Pos(200, 0, 0) * (Box(100, 60, 20) - _obround(3, 12, 20))
    part = Compound([first, second])
    graph = FaceGraph(part)
    proposals = _body_scoped_proposals(
        list(part.solids()), partial(_slot_proposals_one, graph=graph)
    )
    assert len(proposals) == 2
    assert proposals[0] is not proposals[1]
    assert proposals[0].record is not proposals[1].record
    assert proposals[0].caps[0].isdisjoint(proposals[1].caps[0])


def test_merge_and_collapse_union_occurrence_provenance() -> None:
    part = Box(120, 120, 20) - Box(60, 14, 20) - Box(14, 60, 20)
    graph = FaceGraph(part)
    raw = _slot_proposals_one(part, graph=graph)
    # The production one-solid path has already reduced these; direct synthetic proposal
    # adversaries pin the neutral reducers' identity union without rematching record values.
    left, right = graph.nodes[0], graph.nodes[1]
    record = raw[0].record
    merged = _merge_proposals(
        [_RecessProposal(record, frozenset({left})), _RecessProposal(record, frozenset({right}))]
    )
    assert len(merged) == 1 and merged[0].planar == frozenset({left, right})
    assert _collapse_collinear_proposals(raw, part) == raw


def test_competing_endpoint_cap_clusters_fail_closed(monkeypatch) -> None:
    import b123d_recognisers._recess_obround as module

    part = Box(100, 60, 20) - _obround(30, 12, 20)
    graph = FaceGraph(part)
    extended = _slot_proposals_one(part, graph=graph)[0]
    radius = extended.record.width / 2
    proposal = _RecessProposal(
        replace(
            extended.record,
            lo=extended.record.lo + radius,
            hi=extended.record.hi - radius,
            length=extended.record.length - 2 * radius,
        ),
        extended.planar,
    )
    ends = _obround_ends(part, graph)
    public_before = [record.to_dict() for record in recognise_slots(part)]
    low = min(ends, key=lambda end: end[5])
    spare = next(node for node in graph.nodes if node not in low[9])
    competing = (*low[:9], frozenset({spare}))
    monkeypatch.setattr(module, "_obround_ends", lambda _part, _graph: [*ends, competing])
    with pytest.raises(ValueError, match="compete for one endpoint"):
        _extend_obround_proposals([proposal], part, graph)
    # #234 is neutral: record-only callers retain the historical deterministic
    # first matching cap, while only the occurrence/provenance path refuses.
    assert [record.to_dict() for record in recognise_slots(part)] == public_before


def test_prerequisite_does_not_promote_or_publish_slot_pocket_evidence() -> None:
    by_family = {definition.family: definition for definition in PHYSICAL_DEFINITIONS}
    assert isinstance(by_family[FamilyId.SLOTS].attribution, IncompleteAttribution)
    assert isinstance(by_family[FamilyId.POCKETS].attribution, IncompleteAttribution)
