"""Issue #236 Pocket evidence lifecycle and closed failure boundaries."""

from __future__ import annotations

from copy import deepcopy

import pytest
from build123d import Box, Compound, Cylinder, Pos

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_features import _discover_pockets, _PocketAttributionError


def _obround(length: float, width: float, depth: float):
    end = Cylinder(width / 2, depth)
    return Box(length, width, depth) + Pos(-length / 2, 0, 0) * end + Pos(
        length / 2, 0, 0
    ) * end


@pytest.mark.parametrize(
    ("part", "planar", "curved"),
    [
        (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8), 2, 0),
        (Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8), 3, 0),
        (Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10), 2, 2),
        (Box(60, 40, 12) - Pos(0, 0, 4) * _obround(3, 10, 8), 0, 2),
    ],
)
def test_route_selected_sources_are_complete_and_one_body(part, planar, curved) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 1
    assert candidates[0].record is records[0]
    nodes = ledger.defining_of(candidates[0])
    assert sum(ledger.graph.is_planar(node) for node in nodes) == planar
    assert sum(not ledger.graph.is_planar(node) for node in nodes) == curved
    assert ledger.graph.common_valid_solid(nodes) is not None


def test_equal_coincident_bodies_remain_distinct_occurrences() -> None:
    pocket = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    part = Compound([pocket, deepcopy(pocket)])
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 2
    assert all(
        candidate.record is record
        for candidate, record in zip(candidates, records, strict=True)
    )


def test_foreign_graph_refuses_without_prefix() -> None:
    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    ledger = ClaimLedger(FaceGraph(Pos(100, 0, 0) * part))
    with pytest.raises(_PocketAttributionError, match="identity"):
        _discover_pockets(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


def test_unexpected_geometry_value_error_is_not_relabelled(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    ledger = ClaimLedger(FaceGraph(part))

    def fail(*args, **kwargs):
        raise ValueError("geometry defect")

    monkeypatch.setattr(module, "_body_scoped_proposals", fail)
    with pytest.raises(ValueError, match="geometry defect"):
        _discover_pockets(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()
