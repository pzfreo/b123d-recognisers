"""F5c: Flat occurrences own only their planar truncation face."""

from __future__ import annotations

import pytest
from build123d import Align, Box, Cylinder, GeomType, Pos

from b123d_recognisers import recognise_flats
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._cylinder_substrate import analyse_cylinders
from b123d_recognisers.flats import _discover_flats

_CENTRE = (Align.CENTER, Align.CENTER, Align.CENTER)


def _lone_d():
    return Cylinder(20, 40) - Pos(50, 0, 0) * Box(80, 80, 60, align=_CENTRE)


def _double_d():
    return Cylinder(20, 40) & Box(25, 60, 60, align=_CENTRE)


@pytest.mark.parametrize("part", [_lone_d(), _double_d()])
def test_flat_writer_preserves_records_and_binds_only_each_owner_face(part) -> None:
    plain = recognise_flats(part)
    ledger = ClaimLedger(FaceGraph(part))
    measured = _discover_flats(
        part,
        cyls=analyse_cylinders(part),
        face_edges=None,
        graph=ledger.graph,
        sink=ledger.sink,
    )

    assert measured == plain
    assert [item.to_dict() for item in measured] == [item.to_dict() for item in plain]
    candidates = ledger.candidate_set(FamilyId.FLATS).candidates
    assert len(candidates) == len(measured)
    defining_sets = []
    for candidate, record in zip(candidates, measured, strict=True):
        assert candidate.record is record
        defining = ledger.defining_of(candidate)
        assert len(defining) == 1
        assert ledger.graph.common_valid_solid(defining) is not None
        (node,) = defining
        face = ledger.graph.face(node)
        assert face.geom_type == GeomType.PLANE
        center = face.center()
        assert tuple(round(value, 3) for value in (center.X, center.Y, center.Z)) == record.at
        defining_sets.append(defining)
    assert len(set(defining_sets)) == len(defining_sets)


def test_later_flat_binding_failure_publishes_no_prefix(monkeypatch) -> None:
    part = _double_d()
    ledger = ClaimLedger(FaceGraph(part))
    real_require = ledger.graph.require_node
    calls = 0

    def fail_second(face):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("later face binding failed")
        return real_require(face)

    monkeypatch.setattr(ledger.graph, "require_node", fail_second)
    with pytest.raises(ValueError, match="later face binding failed"):
        _discover_flats(
            part,
            cyls=analyse_cylinders(part),
            face_edges=None,
            graph=ledger.graph,
            sink=ledger.sink,
        )
    assert ledger.candidate_set(FamilyId.FLATS).candidates == ()


def test_flat_evidence_capabilities_must_be_supplied_together() -> None:
    part = _lone_d()
    ledger = ClaimLedger(FaceGraph(part))
    with pytest.raises(ValueError, match="requires both graph and sink"):
        _discover_flats(
            part,
            cyls=analyse_cylinders(part),
            face_edges=None,
            graph=ledger.graph,
        )
