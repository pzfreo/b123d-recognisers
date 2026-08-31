# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Authored-geometry guards for the paired-ramp miss audit."""

from __future__ import annotations

from dataclasses import asdict

from build123d import Box, Plane, Polygon, Pos, Rot, extrude

from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._dispositions import Outcome
from b123d_recognisers.result import _take_inventory
from tools.audit_mfcadpp_paired_ramp_steps import _describe_component, _rank


def _side_cut():
    stock = Box(40, 40, 30)
    cutter = Pos(20, 20, 0) * extrude(
        Plane.XZ * Polygon((0, -8), (0, 8), (-10, 0)), 25
    )
    return stock - cutter


def _accepted_anatomy(part):
    product = _take_inventory(part)
    disposition = next(
        item
        for item in product.reconciliation.for_family(FamilyId.PAIRED_RAMP_STEPS)
        if item.outcome is Outcome.ACCEPTED
    )
    nodes = tuple(product.evidence.defining_of(disposition.candidate))
    return _describe_component(product.context.graph, nodes, {})


def test_accepted_authored_pair_reaches_the_final_audit_gate() -> None:
    anatomy = _accepted_anatomy(_side_cut())

    assert anatomy.face_count == 3
    assert anatomy.bevel_faces == 2
    assert anatomy.best_pair.first_failed_gate == "recognisable"
    assert anatomy.best_pair.ramp_edge_counts == (4, 4)
    assert anatomy.best_pair.common_axis_terminal_count == 2
    assert anatomy.best_pair.internal_terminal_edges in (3, 5)
    assert anatomy.best_pair.full_shared_run is True


def test_component_descriptor_is_order_and_axis_permutation_neutral() -> None:
    first = _accepted_anatomy(_side_cut())
    second = _accepted_anatomy(Rot(0, 0, 90) * _side_cut())

    assert first.best_pair.run_axis != second.best_pair.run_axis
    assert first.key() == second.key()


def test_cluster_ranking_and_samples_are_deterministic() -> None:
    anatomy = _accepted_anatomy(_side_cut())
    rows = [
        {
            "model_id": model_id,
            "face_indices": indices,
            "face_count": anatomy.face_count,
            "anatomy_key": anatomy.key(),
            "anatomy": asdict(anatomy),
        }
        for model_id, indices in (("b", [7, 8, 9]), ("a", [1, 2, 3]), ("c", [4, 5, 6]))
    ]

    assert _rank(rows) == _rank(list(reversed(rows)))
    assert _rank(rows)[0]["samples"][0] == {
        "model_id": "a",
        "face_indices": [1, 2, 3],
    }
