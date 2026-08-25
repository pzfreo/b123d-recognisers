"""#234 neutral Slot/Pocket occurrence and cylindrical-cap provenance."""

from __future__ import annotations

import inspect
from copy import deepcopy
from dataclasses import replace
from functools import partial

import pytest
from build123d import Box, Compound, Cylinder, Pos

from b123d_recognisers import recognise_pockets, recognise_slots
from b123d_recognisers._adjacency import FaceEdges, FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_core import (
    _corner_notch_proposals,
    _pocket_proposals_one,
    _slot_proposals_one,
)
from b123d_recognisers._recess_faces import _planar_faces
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


@pytest.mark.parametrize(
    ("family", "part", "expected_planar"),
    [
        ("slot", Box(80, 50, 16) - Box(28, 10, 16), 2),
        ("slot", Box(100, 100, 16) - Box(54, 12, 16) - Box(12, 54, 16), 4),
        ("pocket", Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8), 2),
        ("pocket", Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8), 3),
        ("pocket", Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10), 2),
    ],
)
def test_occurrence_matrix_preserves_public_parity_and_exact_planar_roles(
    family: str, part, expected_planar: int
) -> None:
    memo = FaceEdges()
    graph = FaceGraph(part, face_edges=memo)
    one = _slot_proposals_one if family == "slot" else _pocket_proposals_one
    public = recognise_slots if family == "slot" else recognise_pockets
    proposals = _body_scoped_proposals(
        list(part.solids()) or [part], partial(one, face_edges=memo, graph=graph)
    )
    ledger = ClaimLedger(graph)

    assert [proposal.record.to_dict() for proposal in proposals] == [
        record.to_dict() for record in public(part, face_edges=memo)
    ]
    assert public(part, face_edges=memo, ledger=ledger) == public(part, face_edges=memo)
    assert all(len(proposal.planar) == expected_planar for proposal in proposals)
    assert all(node in graph.nodes for proposal in proposals for node in proposal.planar)
    assert {claim.claimant for claim in ledger.claims} == {
        proposal.record for proposal in proposals if proposal.planar
    }
    assert all(
        claim.defining.isdisjoint(
            frozenset(node for proposal in proposals for group in proposal.caps for node in group)
        )
        for claim in ledger.claims
    )


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


def test_coincident_equal_occurrences_do_not_collapse_by_record_value() -> None:
    first = Box(100, 60, 20) - _obround(3, 12, 20)
    part = Compound([first, deepcopy(first)])
    graph = FaceGraph(part)
    proposals = _body_scoped_proposals(
        list(part.solids()), partial(_slot_proposals_one, graph=graph)
    )

    assert len(proposals) == 2
    assert proposals[0].record == proposals[1].record
    assert proposals[0].record is not proposals[1].record
    assert {node for group in proposals[0].caps for node in group}.isdisjoint(
        node for group in proposals[1].caps for node in group
    )


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


def test_merge_preserves_distinct_split_cap_patch_groups() -> None:
    part = Box(120, 60, 20) - _obround(30, 12, 20)
    graph = FaceGraph(part)
    nodes = graph.nodes[:4]
    record = _slot_proposals_one(part, graph=graph)[0].record
    merged = _merge_proposals(
        [
            _RecessProposal(record, caps=(frozenset(nodes[:2]),)),
            _RecessProposal(record, caps=(frozenset(nodes[2:]),)),
        ]
    )

    assert len(merged) == 1
    assert merged[0].caps == (frozenset(nodes[:2]), frozenset(nodes[2:]))


@pytest.mark.parametrize(
    ("part", "one"),
    [
        (Box(100, 60, 20) - _obround(30, 12, 20), _slot_proposals_one),
        (Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8), _pocket_proposals_one),
    ],
)
def test_occurrence_and_roles_are_independent_of_face_traversal(part, one) -> None:
    baseline_graph = FaceGraph(part)
    baseline = one(part, graph=baseline_graph)

    class ReorderedPart:
        def faces(self):
            return list(reversed(part.faces()))

        def solids(self):
            return part.solids()

        def bounding_box(self):
            return part.bounding_box()

        def intersect(self, other):
            return part.intersect(other)

    reordered_part = ReorderedPart()
    memo = FaceEdges()
    reordered_graph = FaceGraph(reordered_part, face_edges=memo)
    reordered = one(reordered_part, face_edges=memo, graph=reordered_graph)

    def presented(proposals, graph):
        return [
            (
                proposal.record.to_dict(),
                sorted(graph.bounds(node) for node in proposal.planar),
                sorted(sorted(graph.bounds(node) for node in group) for group in proposal.caps),
            )
            for proposal in proposals
        ]

    assert presented(reordered, reordered_graph) == presented(baseline, baseline_graph)


def test_corner_notch_provenance_has_no_value_keyed_intermediate() -> None:
    part = Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8)
    graph = FaceGraph(part)
    proposals = _corner_notch_proposals(
        _planar_faces(part, None, graph),
        part.bounding_box(),
    )

    assert len(proposals) == 1 and len(proposals[0].planar) == 3
    source = inspect.getsource(_pocket_proposals_one)
    assert "_Claims" not in source
    assert "_corner_notch_proposals" in source


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
