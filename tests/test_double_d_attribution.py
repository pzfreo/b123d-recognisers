# SPDX-License-Identifier: Apache-2.0
"""Occurrence-safe defining evidence for principal-axis Double-D bores."""

from __future__ import annotations

import pytest
from build123d import Align, Box, Compound, Cylinder, GeomType, Pos, Rot

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers.profiled_bores import (
    _discover_double_d_bores,
    recognise_double_d_bores,
)
from b123d_recognisers.result import _take_inventory

_CENTRE = (Align.CENTER, Align.CENTER, Align.CENTER)


def _tool(height: float = 20, *, across: float = 7.2):
    return Cylinder(5, height, align=_CENTRE) & Box(
        across, 20, 2 * height, align=_CENTRE
    )


def _plate():
    return Box(30, 30, 10, align=_CENTRE) - _tool()


def _claimed(part):
    public = recognise_double_d_bores(part)
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_double_d_bores(part, writer=ledger.writer)
    candidates = ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, records).candidates
    assert [type(record) for record in records] == [type(record) for record in public]
    assert records == public
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    assert len(candidates) == len(records)
    assert all(
        candidate.record is record
        for candidate, record in zip(candidates, records, strict=True)
    )
    return ledger, records, candidates


def _assert_wall_role(ledger, record, candidate) -> None:
    defining = ledger.defining_of(candidate)
    assert len(defining) == 4
    faces = [ledger.graph.face(node) for node in defining]
    assert [face.geom_type for face in faces].count(GeomType.PLANE) == 2
    assert [face.geom_type for face in faces].count(GeomType.CYLINDER) == 2
    axis = next(at for at, value in enumerate(record.axis) if value)
    bounds = [ledger.graph.bounds(node)[axis] for node in defining]
    low = record.location[axis] - record.depth
    high = record.location[axis]
    assert all(pair == pytest.approx((low, high), abs=1e-6) for pair in bounds)
    assert ledger.graph.common_valid_solid(defining) is not None


@pytest.mark.parametrize("rotation", [Rot(), Rot(0, 90, 0), Rot(90, 0, 0)])
def test_each_principal_axis_issues_the_complete_wall_set(rotation) -> None:
    ledger, records, candidates = _claimed(rotation * _plate())
    assert len(records) == 1
    _assert_wall_role(ledger, records[0], candidates[0])


def test_multiple_occurrences_keep_sorted_record_identity_and_wall_ownership() -> None:
    part = Compound(
        [
            Pos(-30, 0, 0) * _plate(),
            Pos(30, 0, 0) * (Box(34, 34, 12, align=_CENTRE) - _tool(20, across=6.4)),
        ]
    )
    ledger, records, candidates = _claimed(part)
    assert len(records) == 2
    assert [record.location[0] for record in records] == [-30.0, 30.0]
    for record, candidate in zip(records, candidates, strict=True):
        _assert_wall_role(ledger, record, candidate)
    assert ledger.defining_of(candidates[0]).isdisjoint(ledger.defining_of(candidates[1]))


def test_aggregate_inventory_publishes_terminal_double_d_wall_evidence() -> None:
    product = _take_inventory(_plate())
    candidates = product.physical.candidate_set(FamilyId.DOUBLE_D_BORES).candidates
    assert tuple(candidate.record for candidate in candidates) == product.result.double_d_bores
    assert product.accepted.candidate_set(FamilyId.DOUBLE_D_BORES).candidates == candidates
    assert len(candidates) == 1
    assert len(product.evidence.defining_of(candidates[0])) == 4


@pytest.mark.parametrize(
    "part",
    [
        Box(30, 30, 10, align=_CENTRE) - Pos(0, 0, 3) * _tool(4),
        Rot(0, 15, 0) * _plate(),
    ],
)
def test_rejected_geometry_issues_no_candidate(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_double_d_bores(part, writer=ledger.writer) == []
    assert ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_late_body_validation_failure_leaves_no_prefix(monkeypatch) -> None:
    part = Pos(-20, 0, 0) * _plate() + Pos(20, 0, 0) * _plate()
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.common_valid_solid
    calls = 0

    def fail_second(nodes):
        nonlocal calls
        calls += 1
        return original(nodes) if calls == 1 else None

    monkeypatch.setattr(ledger.graph, "common_valid_solid", fail_second)
    with pytest.raises(ValueError, match="one valid owner solid"):
        _discover_double_d_bores(part, writer=ledger.writer)
    assert ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_foreign_writer_refuses_before_publication() -> None:
    part = _plate()
    foreign = ClaimLedger(FaceGraph(Pos(50, 0, 0) * _plate()))
    with pytest.raises(ValueError, match="different part|does not belong"):
        _discover_double_d_bores(part, writer=foreign.writer)
    assert foreign.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()
