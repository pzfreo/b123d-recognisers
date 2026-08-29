# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from build123d import Box, Plane, Polygon, Pos, extrude

from b123d_recognisers import PairedRampStep, recognise_paired_ramp_steps
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger


def _side_cut(*, scale: float = 1.0, asymmetric: bool = False, blind: bool = False):
    stock = Box(40 * scale, 40 * scale, 30 * scale)
    upper = 11 if asymmetric else 8
    profile = Polygon((0, -8 * scale), (0, upper * scale), (-10 * scale, 0))
    opening_y = 15 * scale if blind else 20 * scale
    cutter = Pos(20 * scale, opening_y, 0) * extrude(Plane.XZ * profile, 25 * scale)
    return stock - cutter


def test_a_mirror_ramp_pair_open_to_the_stock_side_is_one_physical_cut() -> None:
    assert recognise_paired_ramp_steps(_side_cut()) == [
        PairedRampStep(axis="y", angle=51.34, length=25.0, at=(10.0, 7.5, 0.0))
    ]


def test_the_pair_claims_both_original_ramps_and_no_terminal_or_stock_face() -> None:
    part = _side_cut()
    ledger = ClaimLedger(FaceGraph(part))
    records = recognise_paired_ramp_steps(part, ledger=ledger)
    candidate = ledger.candidate_set_for(FamilyId.PAIRED_RAMP_STEPS, records).candidates[0]

    assert len(ledger.snapshot_index().defining_of(candidate)) == 2
    assert len(ledger.claims) == 1


def test_a_blind_v_recess_is_not_a_through_side_step() -> None:
    assert recognise_paired_ramp_steps(_side_cut(blind=True)) == []


def test_an_asymmetric_v_is_outside_the_first_supported_domain() -> None:
    assert recognise_paired_ramp_steps(_side_cut(asymmetric=True)) == []


def test_a_top_opening_triangular_pocket_is_not_a_side_step() -> None:
    pocket = Box(40, 40, 30) - Pos(0, 0, 15) * extrude(
        Polygon((-8, -10), (8, -10), (0, 0)), -20
    )

    assert recognise_paired_ramp_steps(pocket) == []


def test_recognition_is_scale_independent_and_dimensions_scale() -> None:
    small = recognise_paired_ramp_steps(_side_cut(scale=0.01))[0]
    large = recognise_paired_ramp_steps(_side_cut(scale=100.0))[0]

    assert small.axis == large.axis == "y"
    assert small.angle == large.angle == 51.34
    assert small.length == 0.25
    assert large.length == 2500.0
