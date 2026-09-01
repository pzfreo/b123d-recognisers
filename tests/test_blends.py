# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Public Blend chain, provenance, transformation and reconciliation contracts."""

from __future__ import annotations

import math

import pytest
from build123d import Axis, Box, Compound, Cylinder, Pos, Rot, fillet

from b123d_recognisers import Blend, feature_census, recognise_blends
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._dispositions import Outcome, ReasonCode
from b123d_recognisers._reconcile import reconcile_blend_candidates
from b123d_recognisers.evidence import build_recognition_evidence
from b123d_recognisers.result import _take_inventory


def _external(radius: float = 2.0):
    box = Box(40, 30, 20)
    return fillet(list(box.edges().filter_by(Axis.Z)), radius)


def _internal():
    pocket = Box(40, 40, 20) - Pos(0, 0, 5) * Box(20, 20, 10)
    bottom = [
        edge
        for edge in pocket.edges()
        if abs(edge.center().Z) < 1e-6
        and abs(edge.center().X) <= 10
        and abs(edge.center().Y) <= 10
    ]
    return fillet(bottom, 2)


def _circular_blind_step():
    stock = Box(40, 30, 20)
    removal = Pos(7.5, 15, 10) * Rot(0, 90, 0) * Cylinder(4, 25)
    return stock - removal


def _annular_boss():
    return (Box(40, 40, 10) + Pos(20, 20, 10) * Cylinder(10, 8)) - (
        Pos(20, 20, 0) * Cylinder(5, 18)
    )


def _rounded_signature(part) -> list[tuple]:
    return [
        (
            record.axis,
            record.radius,
            record.at,
            record.side,
            tuple(round(value, 9) for value in record.axis_direction),
        )
        for record in recognise_blends(part)
    ]


def test_direct_convex_chains_are_superseded_by_dimension_worthy_fillets() -> None:
    part = _external()
    direct = recognise_blends(part)
    product = _take_inventory(part)
    proposed = product.physical.candidate_set(FamilyId.BLENDS).candidates

    assert len(direct) == len(proposed) == 4
    assert all(record.side == "convex" for record in direct)
    assert product.result.blends == ()
    assert feature_census(part)["blend"] == 0
    decisions = product.reconciliation.for_family(FamilyId.BLENDS)
    assert len(decisions) == 4
    assert all(item.outcome is Outcome.REJECTED for item in decisions)
    assert all(item.reason is ReasonCode.BLEND_SUPERSEDED_BY_FILLET for item in decisions)
    assert all(item.related for item in decisions)


def test_only_an_accepted_fillet_can_supersede_a_blend() -> None:
    graph = FaceGraph(Box(10, 10, 10))
    ledger = ClaimLedger(graph)
    node = graph.nodes[0]
    blend = ledger.propose(FamilyId.BLENDS, object(), (node,))
    fillet = ledger.propose(FamilyId.FILLETS, object(), (node,))
    evidence = ledger.snapshot_index()
    blends = evidence.candidate_set(FamilyId.BLENDS)
    fillets = evidence.candidate_set(FamilyId.FILLETS)

    accepted_decisions = reconcile_blend_candidates(blends, fillets, evidence)
    rejected_decisions = reconcile_blend_candidates(
        blends,
        fillets,
        evidence,
        rejected_fillets=frozenset((fillet,)),
    )

    assert len(accepted_decisions) == 1
    assert accepted_decisions[0].candidate is blend
    assert accepted_decisions[0].reason is ReasonCode.BLEND_SUPERSEDED_BY_FILLET
    assert rejected_decisions == ()


def test_small_convex_chains_remain_public_with_exact_face_evidence() -> None:
    part = _external(0.2)
    view = build_recognition_evidence(part)

    assert len(view.result.blends) == 4
    assert feature_census(part)["blend"] == 4
    blend_refs = [feature for feature in view.features if view.family(feature) == "blends"]
    assert len(blend_refs) == 4
    for feature in blend_refs:
        assert isinstance(view.record(feature), Blend)
        assert len(view.defining_faces(feature)) == 1
        assert view.constituent_faces(feature) == view.defining_faces(feature)
        face = view.face(next(iter(view.defining_faces(feature))))
        assert face.geom_type.name == "CYLINDER"


def test_internal_rounds_remain_private_concave_index_evidence() -> None:
    product = _take_inventory(_internal())

    assert recognise_blends(_internal()) == []
    assert product.result.blends == ()
    assert product.result.fillets == ()


def test_circular_blind_step_is_not_a_complete_blend_chain() -> None:
    product = _take_inventory(_circular_blind_step())
    blends = product.physical.candidate_set(FamilyId.BLENDS).candidates
    steps = product.physical.candidate_set(FamilyId.CIRCULAR_BLIND_STEPS).candidates

    assert blends == ()
    assert len(steps) == 1
    assert product.result.blends == ()
    assert product.reconciliation.for_family(FamilyId.BLENDS) == ()


def test_annular_boss_and_hole_decomposition_is_not_a_blend() -> None:
    product = _take_inventory(_annular_boss())

    assert product.result.blends == ()
    assert product.result.bosses
    assert product.result.holes


def test_oblique_chain_retains_canonical_free_axis_and_rigid_translation() -> None:
    rotated = Rot(20, 30, 40) * _external(0.2)
    shifted = Pos(13, -7, 5) * rotated
    before = recognise_blends(rotated)
    after = recognise_blends(shifted)

    assert len(before) == len(after) == 4
    for left, right in zip(before, after, strict=True):
        assert left.axis == right.axis
        assert left.radius == right.radius == 0.2
        assert left.side == right.side == "convex"
        assert left.axis_direction == pytest.approx(right.axis_direction, abs=1e-12)
        assert math.hypot(*left.axis_direction) == pytest.approx(1.0)
        assert right.at == pytest.approx(
            (left.at[0] + 13, left.at[1] - 7, left.at[2] + 5),
            abs=1e-3,
        )


def test_uniform_scale_preserves_occurrences_and_scales_dimensions() -> None:
    base = recognise_blends(_external(0.2))
    scaled = recognise_blends(_external(0.2).scale(10))

    assert len(base) == len(scaled) == 4
    for left, right in zip(base, scaled, strict=True):
        assert right.axis == left.axis
        assert right.side == left.side == "convex"
        assert right.axis_direction == pytest.approx(left.axis_direction, abs=1e-12)
        assert right.radius == pytest.approx(left.radius * 10)
        # Each public anchor is independently quantized to 0.001 model units.
        assert right.at == pytest.approx(tuple(value * 10 for value in left.at), abs=6e-3)


def test_compound_keeps_equal_looking_chains_body_local() -> None:
    part = Compound(children=[Pos(-60, 0, 0) * _external(0.2), Pos(60, 0, 0) * _external(0.2)])
    view = build_recognition_evidence(part)
    blend_refs = [feature for feature in view.features if view.family(feature) == "blends"]

    assert len(view.result.blends) == len(blend_refs) == 8
    assert len({frozenset(view.defining_faces(feature)) for feature in blend_refs}) == 8


def test_sharp_stock_and_full_cylinder_are_not_blends() -> None:
    assert recognise_blends(Box(40, 30, 20)) == []
    assert recognise_blends(Cylinder(10, 20)) == []


def test_face_traversal_order_does_not_change_records(monkeypatch) -> None:
    part = _external(0.2)
    baseline = _rounded_signature(part)
    assert len(baseline) == 4
    part_type = type(part)
    real_faces = part_type.faces

    def reversed_faces(self):
        faces = real_faces(self)
        return type(faces)(reversed(faces))

    monkeypatch.setattr(part_type, "faces", reversed_faces)
    assert _rounded_signature(part) == baseline
