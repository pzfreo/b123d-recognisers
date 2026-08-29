# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from build123d import (
    Axis,
    Box,
    Compound,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    Rot,
    Shell,
    chamfer,
    extrude,
)

from b123d_recognisers import (
    PairedRampStep,
    build_recognition_result,
    feature_census,
    recognise_paired_ramp_steps,
)
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._dispositions import Outcome
from b123d_recognisers.result import _take_inventory


def _side_cut(
    *,
    scale: float = 1.0,
    asymmetric: bool = False,
    blind: bool = False,
    cycle: int = 0,
):
    stock = Box(40 * scale, 40 * scale, 30 * scale)
    upper = 11 if asymmetric else 8
    points = [(0, -8 * scale), (0, upper * scale), (-10 * scale, 0)]
    points = points[cycle:] + points[:cycle]
    profile = Polygon(*points)
    opening_y = 15 * scale if blind else 20 * scale
    cutter = Pos(20 * scale, opening_y, 0) * extrude(Plane.XZ * profile, 25 * scale)
    return stock - cutter


def test_a_mirror_ramp_pair_open_to_the_stock_side_is_one_physical_cut() -> None:
    assert recognise_paired_ramp_steps(_side_cut()) == [
        PairedRampStep(axis="y", angle=51.34, length=25.0, at=(10.0, 7.5, 0.0))
    ]


def test_the_pair_claims_both_original_ramps_and_its_required_terminal() -> None:
    part = _side_cut()
    ledger = ClaimLedger(FaceGraph(part))
    records = recognise_paired_ramp_steps(part, ledger=ledger)
    candidate = ledger.candidate_set_for(FamilyId.PAIRED_RAMP_STEPS, records).candidates[0]

    assert len(ledger.snapshot_index().defining_of(candidate)) == 3
    assert len(ledger.claims) == 1


def test_aggregate_candidate_result_and_census_are_one_accepted_occurrence() -> None:
    part = _side_cut()
    product = _take_inventory(part)
    candidate_set = product.physical.candidate_set(FamilyId.PAIRED_RAMP_STEPS)

    assert len(candidate_set.candidates) == 1
    dispositions = product.reconciliation.for_family(FamilyId.PAIRED_RAMP_STEPS)
    assert [item.outcome for item in dispositions] == [Outcome.ACCEPTED]
    assert len(product.evidence.defining_of(candidate_set.candidates[0])) == 3
    assert product.result.paired_ramp_steps == tuple(recognise_paired_ramp_steps(part))
    assert build_recognition_result(part).paired_ramp_steps == product.result.paired_ramp_steps
    assert feature_census(part)["paired_ramp_step"] == 1


def test_a_blind_v_recess_is_not_a_through_side_step() -> None:
    assert recognise_paired_ramp_steps(_side_cut(blind=True)) == []


def test_an_asymmetric_v_is_outside_the_first_supported_domain() -> None:
    assert recognise_paired_ramp_steps(_side_cut(asymmetric=True)) == []


def test_one_or_two_unrelated_chamfers_do_not_form_a_paired_cut() -> None:
    box = Box(40, 40, 30)
    vertical = box.edges().filter_by(Axis.Z)

    assert recognise_paired_ramp_steps(chamfer(vertical[0], 3)) == []
    assert recognise_paired_ramp_steps(chamfer([vertical[0], vertical[2]], 3)) == []


def test_every_principal_run_axis_is_the_same_geometry_under_permutation() -> None:
    y_step = recognise_paired_ramp_steps(_side_cut())[0]
    x_step = recognise_paired_ramp_steps(Rot(0, 0, 90) * _side_cut())[0]
    z_step = recognise_paired_ramp_steps(Rot(90, 0, 0) * _side_cut())[0]

    assert (x_step.axis, y_step.axis, z_step.axis) == ("x", "y", "z")
    assert {x_step.angle, y_step.angle, z_step.angle} == {51.34}
    assert {x_step.length, y_step.length, z_step.length} == {25.0}


def test_translation_moves_only_the_stable_shared_ridge_anchor() -> None:
    assert recognise_paired_ramp_steps(Pos(3, 4, 5) * _side_cut()) == [
        PairedRampStep(axis="y", angle=51.34, length=25.0, at=(13.0, 11.5, 5.0))
    ]


def test_profile_traversal_start_does_not_change_the_record() -> None:
    assert recognise_paired_ramp_steps(_side_cut(cycle=1)) == recognise_paired_ramp_steps(
        _side_cut(cycle=2)
    )


def test_nonprincipal_run_is_outside_the_supported_domain() -> None:
    assert recognise_paired_ramp_steps(Rot(0, 0, 17) * _side_cut()) == []


def test_an_added_material_rib_is_not_a_removed_ramp_pair() -> None:
    rib = Box(40, 40, 30) + Pos(20, 20, 0) * extrude(
        Plane.XZ * Polygon((0, -8), (0, 8), (10, 0)), 25
    )

    assert recognise_paired_ramp_steps(rib) == []


def test_an_open_shell_cannot_supply_same_valid_solid_authority() -> None:
    assert recognise_paired_ramp_steps(Shell(list(_side_cut().faces()))) == []


def test_two_solids_are_scoped_independently_without_cross_body_pairing() -> None:
    compound = Compound([_side_cut(), Pos(100, 0, 0) * _side_cut()])

    assert len(recognise_paired_ramp_steps(compound)) == 2


def test_a_terminal_interrupted_by_another_feature_is_refused() -> None:
    interrupted = _side_cut() - Pos(15, -5, 0) * Rot(90, 0, 0) * Cylinder(1, 6)

    assert recognise_paired_ramp_steps(interrupted) == []


def test_recognition_is_scale_independent_and_dimensions_scale() -> None:
    small = recognise_paired_ramp_steps(_side_cut(scale=0.01))[0]
    large = recognise_paired_ramp_steps(_side_cut(scale=100.0))[0]

    assert small.axis == large.axis == "y"
    assert small.angle == large.angle == 51.34
    assert small.length == 0.25
    assert large.length == 2500.0


def test_record_supports_a_concrete_paired_angle_and_run_dimension_projection() -> None:
    step = recognise_paired_ramp_steps(_side_cut())[0]

    assert {
        "leader": step.at,
        "paired_angles": (step.angle, step.angle),
        "run": (step.axis, step.length),
    } == {
        "leader": (10.0, 7.5, 0.0),
        "paired_angles": (51.34, 51.34),
        "run": ("y", 25.0),
    }
