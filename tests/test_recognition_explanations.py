# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Public bounded explanations over one aggregate recognition run."""

from __future__ import annotations

from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Edge,
    Face,
    Plane,
    Polygon,
    Pos,
    Rot,
    Shell,
    Solid,
    Wire,
    extrude,
)

import b123d_recognisers as r
import b123d_recognisers.explanations as explanation_module
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._diagnostics import DiagnosticCode, DiagnosticStatus
from b123d_recognisers._dispositions import Outcome, ReasonCode
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS


def _u_passage():
    with BuildPart() as tool:
        with BuildSketch(Plane.XY):
            Polygon(
                (-15, -15),
                (15, -15),
                (15, 15),
                (9, 15),
                (9, -9),
                (-9, -9),
                (-9, 15),
                (-15, 15),
            )
        extrude(amount=40, both=True)
    return Box(60, 60, 20) - tool.part


def _family(report: r.RecognitionReport, family: str) -> r.FamilyExplanation:
    return next(item for item in report.families if item.family == family)


def _side_subdivided_blind_step() -> Solid:
    part = Box(60, 40, 12) - Pos(-20, 20, 6) * Rot(45, 0, 0) * Box(
        30, 5.657, 5.657
    )
    faces = list(part.faces())
    slant = next(
        face
        for face in faces
        if abs(face.normal_at().Y) > 0.5 and abs(face.normal_at().Z) > 0.5
    )
    terminal = next(
        face
        for face in faces
        if len(face.edges()) == 3 and abs(face.normal_at().X) > 0.9
    )
    common = next(
        first
        for first in terminal.edges()
        for second in slant.edges()
        if first.is_same(second)
    )
    start, end = (vertex.center() for vertex in common.vertices())
    middle = (start + end) * 0.5
    split_edges = [Edge.make_line(start, middle), Edge.make_line(middle, end)]
    new_terminal = Face(
        Wire([edge for edge in terminal.edges() if not edge.is_same(common)] + split_edges)
    )
    new_slant = Face(
        Wire([edge for edge in slant.edges() if not edge.is_same(common)] + split_edges)
    )
    if new_terminal.normal_at().dot(terminal.normal_at()) < 0:
        new_terminal = Face(new_terminal.outer_wire().reversed())
    if new_slant.normal_at().dot(slant.normal_at()) < 0:
        new_slant = Face(new_slant.outer_wire().reversed())
    result = Solid(
        Shell(
            [
                face
                for face in faces
                if not face.is_same(slant) and not face.is_same(terminal)
            ]
            + [new_terminal, new_slant]
        )
    )
    assert result.is_valid
    return result


def test_report_preserves_result_and_closed_family_roster() -> None:
    report = r.build_recognition_report(Box(10, 10, 10))

    assert report.coverage is r.ExplanationCoverage.BOUNDED
    assert report.result == r.build_recognition_result(Box(10, 10, 10))
    assert tuple(item.family for item in report.families) == tuple(
        definition.family.value for definition in PHYSICAL_DEFINITIONS
    )
    assert all(item.evaluation is r.FamilyEvaluation.EVALUATED for item in report.families)
    assert all(
        (item.proposed, item.accepted, item.rejected, item.dispositions) == (0, 0, 0, ())
        for item in report.families
    )
    assert all(item.proposed == item.accepted + item.rejected for item in report.families)
    assert report.diagnostics == ()


def test_legacy_raw_report_name_is_an_exact_compatibility_alias() -> None:
    part = Box(10, 10, 10)

    assert r.build_recognition_report(part) == r.build_raw_recognition_report(part)


def test_reconciliation_loss_is_counted_without_identity_leakage() -> None:
    report = r.build_recognition_report(_u_passage())

    slots = _family(report, "slots")
    assert (slots.proposed, slots.accepted, slots.rejected) == (2, 0, 2)
    assert slots.dispositions == (
        r.DispositionExplanation(
            r.ReconciliationReason.SLOT_SUPERSEDED_BY_PASSAGE,
            r.RecognitionOutcome.REJECTED,
            occurrences=2,
            related_occurrences=2,
        ),
    )
    passage = _family(report, "passages")
    assert (passage.proposed, passage.accepted, passage.rejected) == (1, 1, 0)
    assert passage.dispositions[0].reason is r.ReconciliationReason.DEFAULT_ACCEPTED
    assert report.result.slots == ()
    assert len(report.result.passages) == 1
    assert all(item.proposed == item.accepted + item.rejected for item in report.families)


def test_classification_distinguishes_not_applicable_from_evaluated_empty() -> None:
    report = r.build_recognition_report(Box(10, 10, 10), rotational=True)

    assert _family(report, "plates").evaluation is r.FamilyEvaluation.NOT_APPLICABLE
    assert _family(report, "angled_steps").evaluation is r.FamilyEvaluation.NOT_APPLICABLE
    assert _family(report, "holes").evaluation is r.FamilyEvaluation.EVALUATED
    assert _family(report, "holes").proposed == 0


def test_public_closed_values_match_private_authority() -> None:
    assert {item.value for item in r.ReconciliationReason} == {
        item.value for item in ReasonCode
    }
    assert {item.value for item in r.RecognitionOutcome} == {item.value for item in Outcome}
    assert {item.value for item in r.RecognitionDiagnosticCode} == {
        item.value for item in DiagnosticCode
    }
    assert {item.value for item in r.RecognitionDiagnosticStatus} == {
        item.value for item in DiagnosticStatus
    }


def test_public_report_executes_the_inventory_once(monkeypatch) -> None:
    products = []
    original = explanation_module._take_inventory

    def counted(*args, **kwargs):
        product = original(*args, **kwargs)
        products.append(product)
        return product

    monkeypatch.setattr(explanation_module, "_take_inventory", counted)

    report = r.build_recognition_report(Box(10, 10, 10))

    assert len(products) == 1
    assert report.result is products[0].result


def test_bounded_residual_projects_publicly_and_tracks_raw_coordinates() -> None:
    part = _side_subdivided_blind_step()
    original = r.build_recognition_report(part)
    transformed = r.build_recognition_report(Pos(100, -20, 5) * part)

    assert len(original.diagnostics) == 1
    diagnostic = original.diagnostics[0]
    assert diagnostic.code is (
        r.RecognitionDiagnosticCode.UNSUPPORTED_SUBDIVIDED_ANGLED_STEP_TERMINAL
    )
    assert diagnostic.status is r.RecognitionDiagnosticStatus.UNSUPPORTED
    assert diagnostic.family == "angled_steps"
    assert diagnostic.raw_outer_edges == 4
    assert diagnostic.effective_outer_sides == 3
    assert transformed.diagnostics[0].at != diagnostic.at
    assert transformed.diagnostics[0].code is diagnostic.code
    assert tuple(
        (item.family, item.evaluation, item.proposed, item.accepted, item.rejected)
        for item in transformed.families
    ) == tuple(
        (item.family, item.evaluation, item.proposed, item.accepted, item.rejected)
        for item in original.families
    )


def test_explanation_values_do_not_expose_private_identity() -> None:
    report = r.build_recognition_report(_u_passage())
    public_values = (*report.families, *report.diagnostics)

    assert all("candidate" not in field for value in public_values for field in value.__slots__)
    assert all("evidence" not in field for value in public_values for field in value.__slots__)
    assert all("node" not in field for value in public_values for field in value.__slots__)


def test_family_lookup_uses_stable_public_family_ids() -> None:
    report = r.build_recognition_report(_u_passage())
    assert {item.family for item in report.families} == {
        family.value for family in FamilyId if family is not FamilyId.LEGACY
    }
