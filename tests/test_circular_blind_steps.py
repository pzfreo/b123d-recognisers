# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Circular blind-step geometry, provenance and reconciliation contracts."""

from __future__ import annotations

import math

import pytest
from build123d import (
    Axis,
    Box,
    Compound,
    Cone,
    Cylinder,
    Plane,
    Pos,
    Rot,
    Shell,
    export_step,
    fillet,
    import_step,
    mirror,
)

from b123d_recognisers import feature_census
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._cylinder_substrate import analyse_cylinders
from b123d_recognisers._dispositions import Outcome, ReasonCode
from b123d_recognisers.circular_blind_steps import (
    QUARTER_TURN_RAD_TOL,
    CircularBlindStep,
    recognise_circular_blind_steps,
)
from b123d_recognisers.result import _take_inventory


def _step(scale: float = 1.0):
    stock = Box(40 * scale, 30 * scale, 20 * scale)
    removal = (
        Pos(7.5 * scale, 15 * scale, 10 * scale)
        * Rot(0, 90, 0)
        * Cylinder(4 * scale, 25 * scale)
    )
    return stock - removal


def _cylinders(part):
    along_z, cross_axis = analyse_cylinders(part)
    return [*along_z, *cross_axis]


def test_record_locates_the_blind_terminal_opening_and_quarter_section() -> None:
    assert recognise_circular_blind_steps(_step()) == [
        CircularBlindStep(
            axis="x",
            radius=4.0,
            length=25.0,
            centreline=((-5.0, 15.0, 10.0), (20.0, 15.0, 10.0)),
            section=((11.0, 10.0), (15.0, 10.0), (15.0, 6.0)),
        )
    ]


def test_direct_and_aggregate_paths_keep_exact_two_face_provenance_and_drop_the_fillet() -> None:
    part = _step()
    graph = FaceGraph(part)
    ledger = ClaimLedger(graph)

    direct = recognise_circular_blind_steps(part, ledger=ledger)

    assert direct == recognise_circular_blind_steps(part)
    assert len(ledger.claims) == 1
    assert len(ledger.claims[0].defining) == 2
    assert {graph.face(node).geom_type.name for node in ledger.claims[0].defining} == {
        "CYLINDER",
        "PLANE",
    }
    candidate = ledger.candidate_set(FamilyId.CIRCULAR_BLIND_STEPS).candidates[0]
    assert len(candidate.evidence.surfaces) == 2

    product = _take_inventory(part)
    circular = product.physical.candidate_set(FamilyId.CIRCULAR_BLIND_STEPS).candidates
    fillets = product.physical.candidate_set(FamilyId.FILLETS).candidates
    assert len(circular) == len(fillets) == 1
    assert product.result.circular_blind_steps == tuple(direct)
    assert product.result.fillets == ()
    assert feature_census(part)["circular_blind_step"] == 1
    fillet_disposition = next(
        item for item in product.reconciliation.dispositions if item.candidate is fillets[0]
    )
    assert fillet_disposition.outcome is Outcome.REJECTED
    assert fillet_disposition.reason is ReasonCode.FILLET_SUPERSEDED_BY_CIRCULAR_BLIND_STEP
    assert fillet_disposition.related == circular


def test_scale_rotation_and_step_round_trip_preserve_the_occurrence(tmp_path) -> None:
    for scale in (0.05, 1.0, 100.0):
        record = recognise_circular_blind_steps(_step(scale))[0]
        assert record.radius == pytest.approx(4 * scale)
        assert record.length == pytest.approx(25 * scale)
        assert len(recognise_circular_blind_steps(Rot(0, 0, 90) * _step(scale))) == 1
        assert recognise_circular_blind_steps(Rot(0, 0, 90) * _step(scale))[0].axis == "y"

    path = tmp_path / "circular.step"
    export_step(_step(), path)
    assert recognise_circular_blind_steps(import_step(path)) == recognise_circular_blind_steps(
        _step()
    )


def test_quarter_turn_parameter_tolerance_accepts_inside_and_refuses_outside() -> None:
    part = _step()
    cylinders = analyse_cylinders(part)
    flat = [*cylinders[0], *cylinders[1]]
    selected = next(item for item in flat if math.isclose(item["u_extent"], math.pi / 2))

    def changed(delta: float):
        replacement = dict(selected)
        replacement["u_extent"] += delta
        return (
            [replacement if item is selected else item for item in cylinders[0]],
            [replacement if item is selected else item for item in cylinders[1]],
        )

    for sign in (-1, 1):
        assert len(
            recognise_circular_blind_steps(
                part, cyls=changed(sign * QUARTER_TURN_RAD_TOL / 2)
            )
        ) == 1
        assert (
            recognise_circular_blind_steps(
                part, cyls=changed(sign * QUARTER_TURN_RAD_TOL * 2)
            )
            == []
        )


def test_reflections_preserve_opening_direction_and_occupied_quadrant() -> None:
    original = recognise_circular_blind_steps(_step())[0]
    across_opening = recognise_circular_blind_steps(mirror(_step(), Plane.YZ))[0]
    across_section = recognise_circular_blind_steps(mirror(_step(), Plane.XZ))[0]

    assert across_opening.axis == original.axis == "x"
    assert across_opening.centreline[0][0] == -original.centreline[0][0]
    assert across_opening.centreline[1][0] == -original.centreline[1][0]
    assert across_section.section != original.section
    assert across_section.centreline[0][1] == -original.centreline[0][1]


def test_blind_bore_through_groove_half_cylinder_and_capped_cut_fail_closed() -> None:
    stock = Box(40, 30, 20)
    blind_bore = stock - Pos(0, 0, 5) * Cylinder(4, 15)
    through_corner = stock - Pos(0, 15, 10) * Rot(0, 90, 0) * Cylinder(4, 50)
    half_cylinder = stock - Pos(7.5, 0, 10) * Rot(0, 90, 0) * Cylinder(4, 25)
    capped = stock - Pos(0, 15, 10) * Rot(0, 90, 0) * Cylinder(4, 20)

    for part in (blind_bore, through_corner, half_cylinder, capped):
        assert recognise_circular_blind_steps(part) == []


def test_external_conical_oblique_and_enclosed_cylindrical_lookalikes_fail_closed() -> None:
    stock = Box(40, 30, 20)
    external = stock + Pos(7.5, 15, 10) * Rot(0, 90, 0) * Cylinder(4, 25)
    conical = stock - Pos(7.5, 15, 10) * Rot(0, 90, 0) * Cone(4, 2, 25)
    oblique = stock - Pos(7.5, 15, 10) * Rot(0, 80, 0) * Cylinder(4, 25)
    enclosed = stock - Pos(7.5, 15, 10) * Rot(0, 90, 0) * Cylinder(4, 10)

    for part in (external, conical, oblique, enclosed):
        assert recognise_circular_blind_steps(part) == []


def test_open_shell_and_foreign_cylinder_inventory_fail_before_issuance() -> None:
    part = _step()
    assert recognise_circular_blind_steps(Shell(list(part.faces()))) == []

    ledger = ClaimLedger(FaceGraph(part))
    foreign = Pos(100, 0, 0) * _step()
    with pytest.raises(ValueError, match="graph|node|own"):
        recognise_circular_blind_steps(part, cyls=analyse_cylinders(foreign), ledger=ledger)
    assert ledger.candidate_set(FamilyId.CIRCULAR_BLIND_STEPS).candidates == ()


def test_compound_order_preserves_two_distinct_occurrences() -> None:
    first = _step()
    second = Pos(100, 0, 0) * _step()
    forward = recognise_circular_blind_steps(Compound(children=[first, second]))
    reverse = recognise_circular_blind_steps(Compound(children=[second, first]))

    assert len(forward) == 2
    assert forward == reverse


def test_equal_valued_occurrences_keep_distinct_candidate_identity_and_evidence() -> None:
    part = Compound(children=[_step(), _step()])
    graph = FaceGraph(part)
    ledger = ClaimLedger(graph)

    records = recognise_circular_blind_steps(part, ledger=ledger)
    candidates = ledger.candidate_set(FamilyId.CIRCULAR_BLIND_STEPS).candidates

    assert len(records) == len(candidates) == 2
    assert records[0] == records[1]
    assert candidates[0] is not candidates[1]
    assert candidates[0].record is records[0]
    assert candidates[1].record is records[1]
    assert candidates[0].evidence.defining != candidates[1].evidence.defining


def test_late_solid_validation_failure_is_atomic(monkeypatch) -> None:
    part = _step()
    graph = FaceGraph(part)
    ledger = ClaimLedger(graph)
    original = FaceGraph.common_valid_solid
    successful = 0

    def fail_validation(self, nodes):
        nonlocal successful
        result = original(self, nodes)
        if self is graph and result is not None:
            successful += 1
            if successful == 3:
                return None
        return result

    monkeypatch.setattr(FaceGraph, "common_valid_solid", fail_validation)
    with pytest.raises(ValueError, match="valid solid"):
        recognise_circular_blind_steps(part, ledger=ledger)
    assert ledger.candidate_set(FamilyId.CIRCULAR_BLIND_STEPS).candidates == ()


def test_a_plain_fillet_survives_when_circular_step_discovery_misses() -> None:
    stock = Box(40, 30, 20)
    rounded = fillet(stock.edges().filter_by(Axis.X)[:1], 4)
    product = _take_inventory(rounded)

    assert product.result.circular_blind_steps == ()
    assert product.result.fillets
