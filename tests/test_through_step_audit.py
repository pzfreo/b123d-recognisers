# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Deterministic authored-geometry tests for the through-step miss audit."""

from __future__ import annotations

from build123d import Box, Pos, Rot

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._dispositions import Outcome
from b123d_recognisers.result import _take_inventory
from tools.audit_mfcadpp_through_steps import describe_component


def _step():
    return Box(40, 30, 20) - Pos(15, 10, 0) * Box(20, 20, 30)


def test_accepted_authored_step_has_recognisable_audit_anatomy() -> None:
    product = _take_inventory(_step())
    accepted = [
        item
        for item in product.reconciliation.for_family(FamilyId.THROUGH_STEPS)
        if item.outcome is Outcome.ACCEPTED
    ]
    assert len(accepted) == 1
    nodes = tuple(product.evidence.defining_of(accepted[0].candidate))

    anatomy = describe_component(product.context.graph, nodes)

    assert anatomy.face_count == 2
    assert anatomy.first_failed_gate == "recognisable"
    assert anatomy.full_run_faces == 2
    assert anatomy.terminal_count == 2
    assert anatomy.exact_empty_prism is True


def test_component_descriptor_is_independent_of_supplied_node_order() -> None:
    product = _take_inventory(_step())
    disposition = next(
        item
        for item in product.reconciliation.for_family(FamilyId.THROUGH_STEPS)
        if item.outcome is Outcome.ACCEPTED
    )
    nodes = tuple(product.evidence.defining_of(disposition.candidate))

    assert describe_component(product.context.graph, nodes) == describe_component(
        product.context.graph, tuple(reversed(nodes))
    )


def test_motif_key_is_rotation_neutral() -> None:
    first = _take_inventory(_step())
    second = _take_inventory(Rot(90, 0, 0) * _step())

    def anatomy(product):
        disposition = next(
            item
            for item in product.reconciliation.for_family(FamilyId.THROUGH_STEPS)
            if item.outcome is Outcome.ACCEPTED
        )
        return describe_component(
            product.context.graph,
            tuple(product.evidence.defining_of(disposition.candidate)),
        )

    left = anatomy(first)
    right = anatomy(second)
    assert left.inferred_run_axis != right.inferred_run_axis
    assert left.key() == right.key()


def test_single_authored_face_has_no_inferred_rectangular_pair() -> None:
    part = Box(10, 20, 30)
    graph = FaceGraph(part)
    node = min(graph.nodes, key=lambda item: item.index)

    anatomy = describe_component(graph, (node,))

    assert anatomy.face_count == 1
    assert anatomy.first_failed_gate == "no_orthogonal_rectangular_pair"
    assert anatomy.inferred_run_axis is None
    assert anatomy.exact_empty_prism is None
